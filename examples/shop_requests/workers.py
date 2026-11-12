"""Long-running worker loops. Each one is meant to run as its own supervised process.

    python -m examples.shop_requests.workers notifier   --db data/bot.sqlite3
    python -m examples.shop_requests.workers projection --db data/bot.sqlite3 --out data/export

The notifier prints instead of calling a chat API: replace `send` with your
adapter (e.g. python-telegram-bot's bot.send_message). A failure in one cycle
is recorded in the health file and retried next cycle; it never kills the loop.
"""
import argparse
import signal
import threading
import time

from kit import db, health
from kit.outbox import drain
from kit.projection import write_csv


def send(chat_id, reply_to, text):
    print(f"-> chat {chat_id} (reply to {reply_to}): {text}", flush=True)


def run(cycle, interval, health_path, name, stop):
    while not stop.is_set():
        try:
            cycle()
            health.write(health_path, f"{name}:ok")
        except Exception as e:  # one bad cycle must not take the process down
            health.write(health_path, f"{name}:error", error=repr(e))
        stop.wait(interval)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("worker", choices=["notifier", "projection"])
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default="data/export")
    ap.add_argument("--interval", type=float, default=5)
    ap.add_argument("--health", default="data/health.json")
    a = ap.parse_args(argv)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    if a.worker == "notifier":
        conn = db.connect(a.db)
        cycle = lambda: drain(conn, send)
    else:
        cycle = lambda: write_csv(db.connect_ro(a.db), a.out)
    run(cycle, a.interval, a.health, a.worker, stop)


if __name__ == "__main__":
    main()
