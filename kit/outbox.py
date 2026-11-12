"""Durable at-most-once notifications (transactional outbox).

READY -> DISPATCHING (committed BEFORE the send) -> SENT
                                   \-> DELIVERY_UNKNOWN (send raised; never auto-retried)
Rows left in DISPATCHING or DELIVERY_UNKNOWN are for an operator to review, so a
customer can never get the same message twice.
"""
from .db import now, tx


def enqueue(conn, request_id, kind, chat_id, reply_to, text, clock=now):
    """Idempotent per (request_id, kind). Joins the caller's transaction if one is open."""
    with tx(conn):
        cur = conn.execute("INSERT OR IGNORE INTO outbox(request_id,kind,chat_id,reply_to,text,updated_at) "
                           "VALUES(?,?,?,?,?,?)", (request_id, kind, chat_id, reply_to, text, clock()))
        return cur.rowcount == 1


def drain(conn, sender, clock=now):
    """sender(chat_id, reply_to, text) must return normally only if delivery succeeded."""
    sent = 0
    ids = [r["id"] for r in conn.execute("SELECT id FROM outbox WHERE state='READY' ORDER BY id")]
    for oid in ids:
        with tx(conn):
            cur = conn.execute("UPDATE outbox SET state='DISPATCHING', updated_at=? WHERE id=? AND state='READY'",
                               (clock(), oid))
            if cur.rowcount != 1:
                continue  # another worker claimed it
            row = conn.execute("SELECT chat_id,reply_to,text FROM outbox WHERE id=?", (oid,)).fetchone()
        try:
            sender(row["chat_id"], row["reply_to"], row["text"])
            final = "SENT"
            sent += 1
        except Exception:
            final = "DELIVERY_UNKNOWN"
        with tx(conn):
            conn.execute("UPDATE outbox SET state=?, updated_at=? WHERE id=?", (final, clock(), oid))
    return sent
