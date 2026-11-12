"""Customer policy: pending cap, rolling rate limit, strikes with admin overrides.

Evidence is never deleted. Admins waive individual strikes or start a fresh cycle.
"""
from dataclasses import dataclass

from .db import now, tx


@dataclass(frozen=True)
class Policy:
    pending_limit: int = 3
    rolling_limit: int = 5
    rolling_window: int = 86400
    strike_limit: int = 3

    def check(self, conn, user_id, t):
        """Returns (ok, reason). Call inside the same transaction that creates the request."""
        row = conn.execute("SELECT blocked FROM user_policy WHERE user_id=?", (user_id,)).fetchone()
        if row and row["blocked"]:
            return False, "BLOCKED"
        pending = conn.execute("SELECT COUNT(*) FROM requests WHERE user_id=? AND status='PENDING'",
                               (user_id,)).fetchone()[0]
        if pending >= self.pending_limit:
            return False, "PENDING_LIMIT"
        recent = conn.execute("SELECT COUNT(*) FROM requests WHERE user_id=? AND created_at>?",
                              (user_id, t - self.rolling_window)).fetchone()[0]
        if recent >= self.rolling_limit:
            return False, "RATE_LIMIT"
        return True, None


def add_strike(conn, user_id, reason, policy=Policy(), clock=now):
    """Records a strike; blocks the user when unwaived strikes in the cycle reach the limit."""
    with tx(conn):
        conn.execute("INSERT OR IGNORE INTO user_policy(user_id) VALUES(?)", (user_id,))
        cycle = conn.execute("SELECT cycle FROM user_policy WHERE user_id=?", (user_id,)).fetchone()[0]
        conn.execute("INSERT INTO strikes(user_id,cycle,reason,created_at) VALUES(?,?,?,?)",
                     (user_id, cycle, reason, clock()))
        n = conn.execute("SELECT COUNT(*) FROM strikes WHERE user_id=? AND cycle=? AND waived=0",
                         (user_id, cycle)).fetchone()[0]
        blocked = n >= policy.strike_limit
        if blocked:
            conn.execute("UPDATE user_policy SET blocked=1 WHERE user_id=?", (user_id,))
        return blocked


def waive_strike(conn, strike_id):
    with tx(conn):
        conn.execute("UPDATE strikes SET waived=1 WHERE id=?", (strike_id,))


def unblock(conn, user_id, new_cycle=True):
    """Admin action. A new cycle means old strikes stay as history but no longer count."""
    with tx(conn):
        conn.execute("INSERT OR IGNORE INTO user_policy(user_id) VALUES(?)", (user_id,))
        conn.execute("UPDATE user_policy SET blocked=0, cycle=cycle+? WHERE user_id=?",
                     (1 if new_cycle else 0, user_id))
