import unittest

from kit.dispatch import DefinitelyNotSent, submit_once
from tests.helpers import FakeTransport, fresh_db


def add_request(conn):
    return conn.execute("INSERT INTO requests(chat_id,user_id,msg_id,item_key,created_at) VALUES(1,1,1,'AB-123',0)").lastrowid


class DispatchTests(unittest.TestCase):
    def test_confirmed_and_never_repeated(self):
        conn, _ = fresh_db(); rid = add_request(conn); t = FakeTransport()
        self.assertEqual(submit_once(conn, rid, t, {"x": 1}), ("CONFIRMED_SUBMITTED", True))
        self.assertEqual(submit_once(conn, rid, t, {"x": 1}), ("CONFIRMED_SUBMITTED", False))
        self.assertEqual(len(t.calls), 1)

    def test_ambiguous_failure_is_unknown_and_not_retried(self):
        conn, _ = fresh_db(); rid = add_request(conn); t = FakeTransport(ConnectionError("reset"))
        self.assertEqual(submit_once(conn, rid, t, {})[0], "OUTCOME_UNKNOWN")
        submit_once(conn, rid, t, {})
        self.assertEqual(len(t.calls), 1)

    def test_stranded_attempting_is_not_resubmitted(self):
        conn, _ = fresh_db(); rid = add_request(conn); t = FakeTransport()
        conn.execute("INSERT INTO submissions(request_id,state,updated_at) VALUES(?, 'ATTEMPTING', 0)", (rid,))
        self.assertEqual(submit_once(conn, rid, t, {}), ("ATTEMPTING", False))
        self.assertEqual(t.calls, [])

    def test_not_sent_may_be_retried(self):
        conn, _ = fresh_db(); rid = add_request(conn)
        self.assertEqual(submit_once(conn, rid, FakeTransport(DefinitelyNotSent()), {})[0], "NOT_SENT")
        t = FakeTransport()
        self.assertEqual(submit_once(conn, rid, t, {})[0], "CONFIRMED_SUBMITTED")
        self.assertEqual(len(t.calls), 1)

    def test_intent_is_on_disk_before_the_call(self):
        conn, _ = fresh_db(); rid = add_request(conn); seen = []

        class Spy:
            def submit(self, payload):
                seen.append(conn.execute("SELECT state FROM submissions WHERE request_id=?", (rid,)).fetchone()[0])
        submit_once(conn, rid, Spy(), {})
        self.assertEqual(seen, ["ATTEMPTING"])


if __name__ == "__main__":
    unittest.main()
