"""SQLite helpers: one connection factory, a re-entrant transaction, a read-only opener."""
import contextlib
import sqlite3
import time


def connect(path):
    conn = sqlite3.connect(path, isolation_level=None)  # explicit transactions only
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def connect_ro(path):
    """Read-only connection: any write attempt raises sqlite3.OperationalError."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextlib.contextmanager
def tx(conn):
    """BEGIN IMMEDIATE ... COMMIT; joins an already open transaction instead of nesting."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def now():
    return int(time.time())
