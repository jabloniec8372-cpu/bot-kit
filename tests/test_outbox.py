import unittest

from kit.outbox import drain, enqueue
from tests.helpers import fresh_db


class OutboxTests(unittest.TestCase):
    def test_enqueue_is_idempotent(self):
        conn, _ = fresh_db()
        self.assertTrue(enqueue(conn, 1, "RESULT", 10, 5, "hi"))
        self.assertFalse(enqueue(conn, 1, "RESULT", 10, 5, "hi again"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 1)

    def test_sent_once(self):
        conn, _ = fresh_db(); enqueue(conn, 1, "RESULT", 10, 5, "hi"); got = []
        self.assertEqual(drain(conn, lambda c, r, t: got.append((c, r, t))), 1)
        self.assertEqual(drain(conn, lambda c, r, t: got.append("dup")), 0)
        self.assertEqual(got, [(10, 5, "hi")])

    def test_failed_send_is_unknown_and_not_retried(self):
        conn, _ = fresh_db(); enqueue(conn, 1, "RESULT", 10, 5, "hi")

        def boom(c, r, t):
            raise TimeoutError()
        self.assertEqual(drain(conn, boom), 0)
        self.assertEqual(conn.execute("SELECT state FROM outbox").fetchone()[0], "DELIVERY_UNKNOWN")
        got = []
        drain(conn, lambda c, r, t: got.append(1))
        self.assertEqual(got, [])

    def test_claim_is_committed_before_send(self):
        conn, _ = fresh_db(); enqueue(conn, 1, "RESULT", 10, 5, "hi"); seen = []
        drain(conn, lambda c, r, t: seen.append(conn.execute("SELECT state FROM outbox").fetchone()[0]))
        self.assertEqual(seen, ["DISPATCHING"])


if __name__ == "__main__":
    unittest.main()
