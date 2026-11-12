import os
import tempfile

from kit import db, schema


def fresh_db():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "t.sqlite3")
    conn = db.connect(path)
    schema.init(conn)
    return conn, path


class FakeTransport:
    def __init__(self, exc=None):
        self.calls, self.exc = [], exc

    def submit(self, payload):
        self.calls.append(payload)
        if self.exc:
            raise self.exc
