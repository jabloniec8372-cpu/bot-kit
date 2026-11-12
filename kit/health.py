"""Tiny heartbeat file so one process can report its health to another (or to /status).

A fresh heartbeat only proves the local loop is alive. Missing, corrupt or old
state is reported as UNKNOWN or STALE, never silently as OK.
"""
import json
import os
import time


def write(path, phase, error=None, clock=time.time):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"phase": phase, "heartbeat": clock(), "error": (error or "")[:200]}, f)
    os.replace(tmp, path)


def report(path, stale_after=120, clock=time.time):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        age = clock() - float(d["heartbeat"])
    except (OSError, ValueError, KeyError, TypeError):
        return "UNKNOWN: no readable health snapshot"
    if age > stale_after:
        return f"STALE: last heartbeat {int(age)}s ago (phase {d.get('phase')})"
    err = f", last error: {d['error']}" if d.get("error") else ""
    return f"OK: phase {d.get('phase')}, heartbeat {int(age)}s ago{err}"
