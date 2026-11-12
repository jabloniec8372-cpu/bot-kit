"""Scaffold a new bot repo from the chosen modules.

    python new_bot.py my-bot --modules intake,feed,outbox,projection,health [--out ..]

Copies only the selected modules (plus their dependencies) and their tests, and
writes README, requirements.txt, .gitignore, .env.example. The result is
self-contained and its tests pass on their own.
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEPS = {
    "intake": {"confirm", "dispatch", "feed", "policy", "requests"},
    "requests": {"policy"},
    "feed": {"policy", "outbox"},
}
CORE = {"db", "schema"}
TESTS = {
    "dispatch": "test_dispatch.py", "confirm": "test_confirm.py", "policy": "test_policy.py",
    "feed": "test_feed.py", "outbox": "test_outbox.py", "intake": "test_intake.py",
    "projection": "test_projection_health.py", "health": "test_projection_health.py",
    "requests": "test_policy.py",
}
# tests may need modules the module itself does not: keep generated repos green
TEST_NEEDS = {"test_feed.py": {"policy", "outbox"}, "test_policy.py": {"requests"},
              "test_intake.py": {"intake"}, "test_projection_health.py": {"projection", "health"}}
ALL = set(TESTS)


def resolve(names):
    todo, out = list(names), set()
    while todo:
        n = todo.pop()
        if n not in ALL:
            sys.exit(f"unknown module: {n} (choose from {', '.join(sorted(ALL))})")
        if n not in out:
            out.add(n)
            todo.extend(DEPS.get(n, ()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--modules", default=",".join(sorted(ALL)))
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    mods = resolve([m for m in a.modules.split(",") if m])
    dest = os.path.join(a.out, a.name)
    if os.path.exists(dest):
        sys.exit(f"{dest} already exists; refusing to overwrite")
    os.makedirs(os.path.join(dest, "kit"))
    os.makedirs(os.path.join(dest, "tests"))
    for m in sorted(mods | CORE):
        shutil.copy(os.path.join(HERE, "kit", m + ".py"), os.path.join(dest, "kit", m + ".py"))
    shutil.copy(os.path.join(HERE, "kit", "__init__.py"), os.path.join(dest, "kit", "__init__.py"))
    for f in ("__init__.py", "helpers.py"):
        shutil.copy(os.path.join(HERE, "tests", f), os.path.join(dest, "tests", f))
    for t in sorted({TESTS[m] for m in mods}):
        if TEST_NEEDS.get(t, set()) <= mods or t == "test_projection_health.py" and {"projection", "health"} <= mods:
            shutil.copy(os.path.join(HERE, "tests", t), os.path.join(dest, "tests", t))
    with open(os.path.join(dest, "README.md"), "w") as f:
        f.write(f"# {a.name}\n\nBuilt from bot-kit modules: {', '.join(sorted(mods))}.\n\n"
                "    python -m unittest discover -s tests -t .\n")
    with open(os.path.join(dest, "requirements.txt"), "w") as f:
        f.write("# standard library only; add your chat library here, e.g. python-telegram-bot\n")
    with open(os.path.join(dest, ".gitignore"), "w") as f:
        f.write(".env\n*.sqlite3*\n*.session\n__pycache__/\n.venv/\ndata/\n")
    with open(os.path.join(dest, ".env.example"), "w") as f:
        f.write("BOT_TOKEN=\nDATABASE_PATH=data/bot.sqlite3\nHEALTH_STATE_PATH=data/health.json\n")
    print(f"created {dest} with modules: {', '.join(sorted(mods))}")


if __name__ == "__main__":
    main()
