"""YES/NO confirmation correlated by (chat_id, user_id), with expiry.

At most one active confirmation per customer. A declined or expired
confirmation can never be revived by a later bare YES.
"""
from .db import now, tx

YES = {"YES", "Y", "TAK"}
NO = {"NO", "N", "NIE"}


def open_confirmation(conn, chat_id, user_id, item_key, ttl=900, clock=now):
    t = clock()
    with tx(conn):
        conn.execute("UPDATE confirmations SET state='SUPERSEDED' "
                     "WHERE chat_id=? AND user_id=? AND state='ACTIVE'", (chat_id, user_id))
        cur = conn.execute("INSERT INTO confirmations(chat_id,user_id,item_key,state,created_at,expires_at) "
                           "VALUES(?,?,?,?,?,?)", (chat_id, user_id, item_key, "ACTIVE", t, t + ttl))
        return cur.lastrowid


def answer(conn, chat_id, user_id, text, clock=now):
    """Returns (verdict, item_key): CONFIRMED / DECLINED / EXPIRED / NONE (nothing to answer)."""
    word = text.strip().upper().rstrip(".!")
    if word not in YES and word not in NO:
        return "NONE", None
    with tx(conn):
        row = conn.execute("SELECT * FROM confirmations WHERE chat_id=? AND user_id=? AND state='ACTIVE'",
                           (chat_id, user_id)).fetchone()
        if not row:
            return "NONE", None
        if clock() > row["expires_at"]:
            conn.execute("UPDATE confirmations SET state='EXPIRED' WHERE id=?", (row["id"],))
            return "EXPIRED", None
        new = "CONFIRMED" if word in YES else "DECLINED"
        conn.execute("UPDATE confirmations SET state=? WHERE id=?", (new, row["id"]))
        return new, row["item_key"]
