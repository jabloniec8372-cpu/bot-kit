import unittest

from kit.feed import Event, ParseError, apply_event, parse
from tests.helpers import fresh_db


def submitted(conn, item="AB-123", user=5, msg=1):
    rid = conn.execute("INSERT INTO requests(chat_id,user_id,msg_id,item_key,created_at) VALUES(1,?,?,?,0)",
                       (user, msg, item)).lastrowid
    conn.execute("INSERT INTO submissions VALUES(?, 'CONFIRMED_SUBMITTED', 0)", (rid,))
    return rid


class ParserTests(unittest.TestCase):
    def test_good_messages(self):
        self.assertEqual(parse("Item: AB-123\nStatus: ADDED"), Event("AB-123", "ADDED", None))
        e = parse("AB-123 again AB-123\nStatus: REJECTED / Already Exists")
        self.assertEqual((e.status, e.reason), ("REJECTED", "already exists"))

    def test_fail_closed(self):
        for bad in ("Status: ADDED", "AB-123 CD-456\nStatus: ADDED", "AB-123\nStatus: ADDED\nStatus: REJECTED",
                    "AB-123\nno status here", "ab-123\nStatus: ADDED"):
            with self.assertRaises(ParseError, msg=bad):
                parse(bad)


class ApplyTests(unittest.TestCase):
    def test_applied_once_and_replay_safe(self):
        conn, _ = fresh_db(); rid = submitted(conn)
        ev = Event("AB-123", "ADDED")
        self.assertEqual(apply_event(conn, 9, 100, ev), "APPLIED")
        self.assertEqual(apply_event(conn, 9, 100, ev), "REPLAY")
        self.assertEqual(conn.execute("SELECT status FROM requests WHERE id=?", (rid,)).fetchone()[0], "ADDED")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT state FROM item_state").fetchone()[0], "AVAILABLE")

    def test_terminal_state_is_never_overwritten(self):
        conn, _ = fresh_db(); rid = submitted(conn)
        apply_event(conn, 9, 100, Event("AB-123", "ADDED"))
        self.assertEqual(apply_event(conn, 9, 101, Event("AB-123", "REJECTED")), "NO_MATCH")
        self.assertEqual(conn.execute("SELECT status FROM requests WHERE id=?", (rid,)).fetchone()[0], "ADDED")

    def test_unsubmitted_or_unknown_requests_are_excluded(self):
        conn, _ = fresh_db()
        rid = conn.execute("INSERT INTO requests(chat_id,user_id,msg_id,item_key,created_at) VALUES(1,5,1,'AB-123',0)").lastrowid
        conn.execute("INSERT INTO submissions VALUES(?, 'OUTCOME_UNKNOWN', 0)", (rid,))
        self.assertEqual(apply_event(conn, 9, 1, Event("AB-123", "ADDED")), "NO_MATCH")

    def test_two_pending_candidates_are_ambiguous(self):
        conn, _ = fresh_db(); submitted(conn, msg=1); submitted(conn, user=6, msg=2)
        self.assertEqual(apply_event(conn, 9, 1, Event("AB-123", "ADDED")), "AMBIGUOUS")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM requests WHERE status='PENDING'").fetchone()[0], 2)

    def test_already_exists_rejection_gives_strike(self):
        conn, _ = fresh_db(); submitted(conn)
        apply_event(conn, 9, 1, Event("AB-123", "REJECTED", "already exists"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM strikes WHERE user_id=5").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT state FROM item_state").fetchone()[0], "AVAILABLE")

    def test_plain_rejection_gives_no_strike(self):
        conn, _ = fresh_db(); submitted(conn)
        apply_event(conn, 9, 1, Event("AB-123", "REJECTED", "not available"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM strikes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM item_state").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
