import unittest

from kit.dispatch import DefinitelyNotSent
from kit.feed import Event, apply_event
from kit.intake import Intake
from kit.outbox import drain
from kit.policy import Policy
from tests.helpers import FakeTransport, fresh_db


class IntakeTests(unittest.TestCase):
    def talk(self, bot, text, msg, user=7):
        return bot.handle(1, user, msg, text)

    def test_happy_path_end_to_end(self):
        conn, _ = fresh_db(); t = FakeTransport(); bot = Intake(conn, t, clock=lambda: 100)
        self.assertIn("YES or NO", self.talk(bot, "please get AB-123", 1)[0])
        self.assertEqual(t.calls, [])                       # nothing sent before YES
        self.assertIn("submitted", self.talk(bot, "yes", 2)[0])
        self.assertEqual(t.calls, [{"item": "AB-123"}])
        self.assertEqual(self.talk(bot, "yes", 3), [])      # a second YES does nothing
        self.assertEqual(apply_event(conn, 9, 1, Event("AB-123", "ADDED")), "APPLIED")
        sent = []
        drain(conn, lambda c, r, tx: sent.append((c, r, tx)))
        self.assertEqual(sent, [(1, 2, "AB-123 is now available.")])  # threaded to the YES message

    def test_decline_creates_nothing(self):
        conn, _ = fresh_db(); t = FakeTransport(); bot = Intake(conn, t, clock=lambda: 100)
        self.talk(bot, "AB-123", 1)
        self.assertIn("Cancelled", self.talk(bot, "no", 2)[0])
        self.assertEqual(self.talk(bot, "yes", 3), [])
        self.assertEqual((t.calls, conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]), ([], 0))

    def test_uncertain_and_unsent_transport_outcomes_are_reported_honestly(self):
        for exc, word in ((ConnectionError(), "uncertain"), (DefinitelyNotSent(), "could not be reached")):
            conn, _ = fresh_db(); bot = Intake(conn, FakeTransport(exc), clock=lambda: 100)
            self.talk(bot, "AB-123", 1)
            self.assertIn(word, self.talk(bot, "yes", 2)[0])

    def test_policy_limit_message(self):
        conn, _ = fresh_db(); bot = Intake(conn, FakeTransport(), Policy(pending_limit=1), clock=lambda: 100)
        self.talk(bot, "AB-111", 1); self.talk(bot, "yes", 2)
        self.talk(bot, "AB-222", 3)
        self.assertIn("too many open", self.talk(bot, "yes", 4)[0])

    def test_already_available_is_prevented(self):
        conn, _ = fresh_db(); t = FakeTransport(); bot = Intake(conn, t, clock=lambda: 100)
        conn.execute("INSERT INTO item_state VALUES('AB-123','AVAILABLE',0)")
        self.talk(bot, "AB-123", 1)
        self.assertIn("already available", self.talk(bot, "yes", 2)[0])
        self.assertEqual(t.calls, [])


if __name__ == "__main__":
    unittest.main()
