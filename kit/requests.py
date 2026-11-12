"""Atomic request admission: idempotency, policy, catalog check and insert in ONE transaction."""
from dataclasses import dataclass
from typing import Optional

from .db import now, tx
from .policy import Policy


@dataclass
class Result:
    kind: str  # CREATED | REPLAY | DENIED | PREVENTED | DUPLICATE_PENDING
    request_id: Optional[int] = None
    reason: Optional[str] = None


def create_request(conn, chat_id, user_id, msg_id, item_key, policy=Policy(), clock=now):
    t = clock()
    with tx(conn):
        ex = conn.execute("SELECT id FROM requests WHERE chat_id=? AND msg_id=?", (chat_id, msg_id)).fetchone()
        if ex:  # same Telegram message delivered twice: harmless
            return Result("REPLAY", ex["id"])
        ok, reason = policy.check(conn, user_id, t)
        if not ok:
            return Result("DENIED", reason=reason)
        st = conn.execute("SELECT state FROM item_state WHERE item_key=?", (item_key,)).fetchone()
        if st and st["state"] == "AVAILABLE":
            # stopped before the outside world was touched: counted, but never a strike
            conn.execute("INSERT INTO prevented(user_id,item_key,created_at) VALUES(?,?,?)",
                         (user_id, item_key, t))
            return Result("PREVENTED")
        dup = conn.execute("SELECT 1 FROM requests WHERE item_key=? AND status='PENDING'", (item_key,)).fetchone()
        if dup:
            return Result("DUPLICATE_PENDING")
        cur = conn.execute("INSERT INTO requests(chat_id,user_id,msg_id,item_key,created_at) VALUES(?,?,?,?,?)",
                           (chat_id, user_id, msg_id, item_key, t))
        return Result("CREATED", cur.lastrowid)
