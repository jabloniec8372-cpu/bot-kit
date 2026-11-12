import csv
import os
import sqlite3
import tempfile
import unittest

from kit import health
from kit.db import connect_ro
from kit.projection import dashboard, write_csv
from tests.helpers import fresh_db


class ProjectionTests(unittest.TestCase):
    def test_dashboard_and_csv_from_read_only_connection(self):
        conn, path = fresh_db()
        for i, st in enumerate(["ADDED", "ADDED", "REJECTED", "PENDING"]):
            conn.execute("INSERT INTO requests(chat_id,user_id,msg_id,item_key,status,created_at) VALUES(1,5,?,?,?,0)",
                         (i, f"AB-10{i}", st))
        conn.execute("INSERT INTO prevented(user_id,item_key,created_at) VALUES(5,'AB-999',0)")
        ro = connect_ro(path)
        self.assertEqual(dashboard(ro), [("REQUESTS", 4), ("ADDED", 2), ("REJECTED", 1), ("PENDING", 1),
                                         ("", ""), ("PREVENTED", 1)])
        out = tempfile.mkdtemp()
        p1, p2 = write_csv(ro, out)
        with open(p2) as f:
            self.assertEqual(len(list(csv.reader(f))), 5)  # header + 4
        with self.assertRaises(sqlite3.OperationalError):
            ro.execute("DELETE FROM requests")  # sheet/export side can never change state


class HealthTests(unittest.TestCase):
    def test_unknown_ok_stale(self):
        p = os.path.join(tempfile.mkdtemp(), "h.json")
        self.assertTrue(health.report(p).startswith("UNKNOWN"))
        health.write(p, "listening", clock=lambda: 1000)
        self.assertTrue(health.report(p, clock=lambda: 1010).startswith("OK"))
        self.assertTrue(health.report(p, stale_after=60, clock=lambda: 2000).startswith("STALE"))
        with open(p, "w") as f:
            f.write("{broken")
        self.assertTrue(health.report(p).startswith("UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
