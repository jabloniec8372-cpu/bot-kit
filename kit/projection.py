"""One-way, full-refresh projection of SQLite to business-friendly files.

Opens the database READ-ONLY and never reads anything back, so editing the
exported sheet can never change bot state. Swap CSV for the Sheets API by
replacing write_csv; the read model stays the same.
"""
import csv
import os

STATUSES = ("ADDED", "REJECTED", "PENDING")


def dashboard(conn):
    counts = {s: 0 for s in STATUSES}
    for r in conn.execute("SELECT status, COUNT(*) AS n FROM requests GROUP BY status"):
        if r["status"] in counts:
            counts[r["status"]] = r["n"]
    prevented = conn.execute("SELECT COUNT(*) FROM prevented").fetchone()[0]
    rows = [("REQUESTS", sum(counts.values()))] + [(s, counts[s]) for s in STATUSES]
    return rows + [("", ""), ("PREVENTED", prevented)]


def request_rows(conn):
    q = ("SELECT r.id, r.item_key, r.user_id, r.status, r.created_at, "
         "COALESCE(s.state,'') AS submission FROM requests r "
         "LEFT JOIN submissions s ON s.request_id=r.id ORDER BY r.id")
    return [tuple(r) for r in conn.execute(q)]


def _write(path, header, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if header:
            w.writerow(header)
        w.writerows(rows)
    os.replace(tmp, path)  # readers never see a half-written file


def write_csv(conn, outdir):
    os.makedirs(outdir, exist_ok=True)
    p1, p2 = os.path.join(outdir, "dashboard.csv"), os.path.join(outdir, "requests.csv")
    _write(p1, None, dashboard(conn))
    _write(p2, ("id", "item", "user", "status", "created_at", "submission"), request_rows(conn))
    return p1, p2
