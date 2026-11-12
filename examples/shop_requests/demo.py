"""Runs the whole system in one process with fake I/O, so you can watch it work.

    python -m examples.shop_requests.demo

In production the four stages below are four separate supervised processes
(see deploy/*.service); they only share the SQLite file.
"""
import os
import tempfile

from kit import db, health, schema
from kit.feed import ParseError, apply_event, parse
from kit.intake import Intake
from kit.outbox import drain
from kit.policy import Policy
from kit.projection import dashboard, write_csv


class FakeShopApi:
    """Stands in for the external system that takes requests (a form, a partner API...)."""
    def submit(self, payload):
        print(f"   [shop API] received {payload}")


def say(who, text):
    print(f"{who:>9}: {text}")


def main():
    workdir = tempfile.mkdtemp(prefix="botkit-demo-")
    conn = db.connect(os.path.join(workdir, "bot.sqlite3"))
    schema.init(conn)
    bot = Intake(conn, FakeShopApi(), Policy(strike_limit=2))
    chat, anna, msg = 100, 1, 0

    def customer(text, user=anna):
        nonlocal msg
        msg += 1
        say(f"user {user}", text)
        for reply in bot.handle(chat, user, msg, text):
            say("bot", reply)

    print("\n== 1. Intake process: confirmation, then one safe submission")
    customer("Hi, could you get SKU-1001 for me?")
    customer("yes")
    customer("yes")  # accidental double YES: nothing happens

    print("\n== 2. Status watcher process: strict parsing of the partner's feed")
    for n, text in enumerate(["SKU-1001 ... maybe done?", "Item: SKU-1001\nStatus: ADDED"], start=1):
        try:
            print(f"   feed #{n}: {apply_event(conn, 9, n, parse(text))}")
        except ParseError as e:
            print(f"   feed #{n}: rejected by parser ({e})")
    print(f"   feed #2 delivered again: {apply_event(conn, 9, 2, parse('Item: SKU-1001\nStatus: ADDED'))}")

    print("\n== 3. Notifier process: at-most-once delivery")
    drain(conn, lambda c, reply_to, t: say("bot->chat", f"(reply to msg {reply_to}) {t}"))

    print("\n== 4. Prevention: the item is known now, so no second request is made")
    customer("SKU-1001 please", user=2)
    customer("yes", user=2)

    print("\n== 5. Projection process: read-only export for the business owner")
    ro = db.connect_ro(os.path.join(workdir, "bot.sqlite3"))
    for k, v in dashboard(ro):
        print(f"   {k:<10} {v}")
    print("   files:", ", ".join(write_csv(ro, os.path.join(workdir, "export"))))

    health.write(os.path.join(workdir, "health.json"), "demo-finished")
    print("\n   health:", health.report(os.path.join(workdir, "health.json")))


if __name__ == "__main__":
    main()
