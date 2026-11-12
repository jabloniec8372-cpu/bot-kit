import unittest

from kit.policy import Policy, add_strike, unblock, waive_strike
from kit.requests import create_request
from tests.helpers import fresh_db


class PolicyTests(unittest.TestCase):
    def test_pending_limit(self):
        conn, _ = fresh_db(); p = Policy(pending_limit=2, rolling_limit=99)
        for i in range(2):
            self.assertEqual(create_request(conn, 1, 5, i, f"AB-10{i}", p, lambda: 10).kind, "CREATED")
        r = create_request(conn, 1, 5, 9, "AB-109", p, lambda: 10)
        self.assertEqual((r.kind, r.reason), ("DENIED", "PENDING_LIMIT"))

    def test_rolling_limit_expires(self):
        conn, _ = fresh_db(); p = Policy(pending_limit=99, rolling_limit=2, rolling_window=100)
        create_request(conn, 1, 5, 1, "AB-101", p, lambda: 10)
        create_request(conn, 1, 5, 2, "AB-102", p, lambda: 20)
        self.assertEqual(create_request(conn, 1, 5, 3, "AB-103", p, lambda: 30).reason, "RATE_LIMIT")
        self.assertEqual(create_request(conn, 1, 5, 4, "AB-104", p, lambda: 200).kind, "CREATED")

    def test_replay_is_idempotent_and_not_counted(self):
        conn, _ = fresh_db(); p = Policy(pending_limit=1)
        a = create_request(conn, 1, 5, 1, "AB-101", p, lambda: 10)
        b = create_request(conn, 1, 5, 1, "AB-101", p, lambda: 11)
        self.assertEqual((b.kind, b.request_id), ("REPLAY", a.request_id))

    def test_strikes_block_waive_and_new_cycle(self):
        conn, _ = fresh_db(); p = Policy(strike_limit=2)
        add_strike(conn, 5, "a", p)
        sid = conn.execute("SELECT id FROM strikes").fetchone()[0]
        waive_strike(conn, sid)
        self.assertFalse(add_strike(conn, 5, "b", p))      # 1 unwaived of 2
        self.assertTrue(add_strike(conn, 5, "c", p))       # 2 unwaived -> blocked
        self.assertEqual(create_request(conn, 1, 5, 1, "AB-101", p).reason, "BLOCKED")
        unblock(conn, 5)
        self.assertEqual(create_request(conn, 1, 5, 2, "AB-102", p).kind, "CREATED")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM strikes").fetchone()[0], 3)  # history kept

    def test_prevented_creates_no_request_and_no_strike(self):
        conn, _ = fresh_db()
        conn.execute("INSERT INTO item_state VALUES('AB-101','AVAILABLE',0)")
        self.assertEqual(create_request(conn, 1, 5, 1, "AB-101").kind, "PREVENTED")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM strikes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prevented").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
