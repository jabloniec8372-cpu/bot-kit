"""Fail-closed parsing and idempotent application of status messages from an external feed.

The item key is the ONLY correlation key. Anything ambiguous is rejected, not guessed.
"""
import re
from dataclasses import dataclass
from typing import Optional

from .db import now, tx
from .outbox import enqueue
from .policy import Policy, add_strike

ITEM = re.compile(r"\b([A-Z]{2,4}-\d{3,6})\b")
STATUS = re.compile(r"^\s*status\s*:\s*(added|rejected)\b(?:\s*[/:-]\s*(.+))?$", re.I | re.M)


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Event:
    item_key: str
    status: str  # ADDED | REJECTED
    reason: Optional[str] = None


def parse(text):
    items = set(ITEM.findall(text))
    if len(items) != 1:
        raise ParseError("need exactly one item key")
    found = STATUS.findall(text)
    kinds = {s.upper() for s, _ in found}
    if len(kinds) != 1:
        raise ParseError("need exactly one terminal status")
    reason = next((r.strip()[:80].lower() for _, r in found if r and r.strip()), None)
    return Event(items.pop(), kinds.pop(), reason)


def apply_event(conn, source_id, msg_id, event, policy=Policy(), clock=now):
    """One transaction: ledger row + request transition + item state + strike + outbox.

    Returns REPLAY | NO_MATCH | AMBIGUOUS | APPLIED. Terminal states are never overwritten.
    """
    with tx(conn):
        if conn.execute("SELECT 1 FROM source_ledger WHERE source_id=? AND msg_id=?", (source_id, msg_id)).fetchone():
            return "REPLAY"
        cands = conn.execute(
            "SELECT r.id, r.user_id, r.chat_id, r.msg_id FROM requests r "
            "JOIN submissions s ON s.request_id=r.id "
            "WHERE r.item_key=? AND r.status='PENDING' AND s.state='CONFIRMED_SUBMITTED'",
            (event.item_key,)).fetchall()
        outcome = "NO_MATCH" if not cands else "AMBIGUOUS" if len(cands) > 1 else "APPLIED"
        available = event.status == "ADDED" or (event.reason or "").startswith("already")
        if available:  # shared catalog knowledge, independent of who asked
            conn.execute("INSERT INTO item_state(item_key,state,updated_at) VALUES(?,?,?) "
                         "ON CONFLICT(item_key) DO UPDATE SET state='AVAILABLE', updated_at=excluded.updated_at",
                         (event.item_key, "AVAILABLE", clock()))
        if outcome == "APPLIED":
            r = cands[0]
            conn.execute("UPDATE requests SET status=? WHERE id=?", (event.status, r["id"]))
            if event.status == "ADDED":
                text = f"{event.item_key} is now available."
            else:
                text = f"{event.item_key} was rejected" + (f": {event.reason}." if event.reason else ".")
                if (event.reason or "").startswith("already"):
                    add_strike(conn, r["user_id"], f"already-exists:{event.item_key}", policy, clock)
            enqueue(conn, r["id"], "RESULT", r["chat_id"], r["msg_id"], text, clock)
        conn.execute("INSERT INTO source_ledger(source_id,msg_id,outcome) VALUES(?,?,?)",
                     (source_id, msg_id, outcome))
        return outcome
