"""One schema for all modules. SQLite is the only source of truth."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests(
  id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
  msg_id INTEGER NOT NULL, item_key TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING', created_at INTEGER NOT NULL,
  UNIQUE(chat_id, msg_id));
CREATE TABLE IF NOT EXISTS submissions(
  request_id INTEGER PRIMARY KEY REFERENCES requests(id),
  state TEXT NOT NULL, updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS confirmations(
  id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
  item_key TEXT NOT NULL, state TEXT NOT NULL,
  created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS item_state(
  item_key TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS user_policy(
  user_id INTEGER PRIMARY KEY, cycle INTEGER NOT NULL DEFAULT 1,
  blocked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS strikes(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, cycle INTEGER NOT NULL,
  reason TEXT NOT NULL, waived INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS prevented(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, item_key TEXT NOT NULL,
  created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS source_ledger(
  source_id INTEGER NOT NULL, msg_id INTEGER NOT NULL, outcome TEXT NOT NULL,
  PRIMARY KEY(source_id, msg_id));
CREATE TABLE IF NOT EXISTS outbox(
  id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL, kind TEXT NOT NULL,
  chat_id INTEGER NOT NULL, reply_to INTEGER, text TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'READY', updated_at INTEGER NOT NULL,
  UNIQUE(request_id, kind));
"""


def init(conn):
    conn.executescript(SCHEMA)
