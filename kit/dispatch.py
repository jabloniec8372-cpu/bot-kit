"""Crash-safe, at-most-once submission to an external system.

Rule: write the intent to disk BEFORE calling the outside world, and never
repeat a call whose outcome we cannot prove. States:

  ATTEMPTING          intent recorded, call in flight (or process died mid-call)
  CONFIRMED_SUBMITTED the remote side provably accepted it
  OUTCOME_UNKNOWN     the call failed ambiguously; it MAY have been accepted
  NOT_SENT            the call provably never left (only this state may be retried)

A stranded ATTEMPTING row (crash) is treated like OUTCOME_UNKNOWN: no auto-retry.
"""
from .db import now, tx


class DefinitelyNotSent(Exception):
    """Raise from a transport when the request provably never reached the remote side."""


def submit_once(conn, request_id, transport, payload, clock=now):
    """Returns (state, sent_now). transport.submit(payload) returns on confirmed acceptance."""
    with tx(conn):
        row = conn.execute("SELECT state FROM submissions WHERE request_id=?", (request_id,)).fetchone()
        if row and row["state"] != "NOT_SENT":
            return row["state"], False  # already claimed: never POST again
        if row:
            conn.execute("UPDATE submissions SET state='ATTEMPTING', updated_at=? WHERE request_id=?",
                         (clock(), request_id))
        else:
            conn.execute("INSERT INTO submissions(request_id, state, updated_at) VALUES(?,?,?)",
                         (request_id, "ATTEMPTING", clock()))
    # the claim is committed here; only now do we touch the outside world
    try:
        transport.submit(payload)
        state = "CONFIRMED_SUBMITTED"
    except DefinitelyNotSent:
        state = "NOT_SENT"
    except Exception:
        state = "OUTCOME_UNKNOWN"
    with tx(conn):
        conn.execute("UPDATE submissions SET state=?, updated_at=? WHERE request_id=?",
                     (state, clock(), request_id))
    return state, True
