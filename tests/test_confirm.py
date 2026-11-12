import unittest

from kit.confirm import answer, open_confirmation
from tests.helpers import fresh_db


class ConfirmTests(unittest.TestCase):
    def test_yes_confirms_once(self):
        conn, _ = fresh_db(); open_confirmation(conn, 1, 7, "AB-123", clock=lambda: 100)
        self.assertEqual(answer(conn, 1, 7, "yes", clock=lambda: 101), ("CONFIRMED", "AB-123"))
        self.assertEqual(answer(conn, 1, 7, "yes", clock=lambda: 102), ("NONE", None))

    def test_no_declines_and_later_yes_cannot_revive(self):
        conn, _ = fresh_db(); open_confirmation(conn, 1, 7, "AB-123", clock=lambda: 100)
        self.assertEqual(answer(conn, 1, 7, "No", clock=lambda: 101)[0], "DECLINED")
        self.assertEqual(answer(conn, 1, 7, "YES", clock=lambda: 102)[0], "NONE")

    def test_expiry(self):
        conn, _ = fresh_db(); open_confirmation(conn, 1, 7, "AB-123", ttl=60, clock=lambda: 100)
        self.assertEqual(answer(conn, 1, 7, "YES", clock=lambda: 161)[0], "EXPIRED")

    def test_other_user_or_chat_cannot_answer(self):
        conn, _ = fresh_db(); open_confirmation(conn, 1, 7, "AB-123", clock=lambda: 100)
        self.assertEqual(answer(conn, 1, 8, "YES", clock=lambda: 101)[0], "NONE")
        self.assertEqual(answer(conn, 2, 7, "YES", clock=lambda: 101)[0], "NONE")

    def test_new_item_supersedes_old(self):
        conn, _ = fresh_db()
        open_confirmation(conn, 1, 7, "AB-111", clock=lambda: 100)
        open_confirmation(conn, 1, 7, "AB-222", clock=lambda: 101)
        self.assertEqual(answer(conn, 1, 7, "YES", clock=lambda: 102), ("CONFIRMED", "AB-222"))

    def test_non_answers_are_ignored(self):
        conn, _ = fresh_db(); open_confirmation(conn, 1, 7, "AB-123", clock=lambda: 100)
        self.assertEqual(answer(conn, 1, 7, "maybe", clock=lambda: 101)[0], "NONE")
        self.assertEqual(answer(conn, 1, 7, "YES", clock=lambda: 102)[0], "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
