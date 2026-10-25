"""Consistent SQLite backup, including committed WAL data. Run as the app owner."""

import argparse, sqlite3, os
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("source")
p.add_argument("destination")
a = p.parse_args()
source = Path(a.source).resolve()
dest = Path(a.destination).resolve()
if source == dest or dest.exists():
    raise SystemExit("Choose a new destination; existing files are never overwritten.")
if not source.is_file():
    raise SystemExit("Source database does not exist.")
dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)
with (
    sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as src,
    sqlite3.connect(dest) as dst,
):
    src.backup(dst)
print("Database backup completed.")
