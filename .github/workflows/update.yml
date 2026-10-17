#!/usr/bin/env python3
"""Generate static data files for GitHub Pages; preserve last good data."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from start_server import fetch_fx, fetch_news

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)


def write(name, payload):
    path = DATA / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main():
    failed = []
    for name, fetcher in (("fx.json", fetch_fx), ("news.json", fetch_news)):
        try:
            payload = fetcher()
            if not isinstance(payload, dict):
                raise ValueError("Invalid data format")
            if name == "fx.json" and (not payload.get("date") or len(payload.get("indicators", [])) != 4):
                raise ValueError("Incomplete ECB FX data")
            if name == "news.json" and not payload.get("items"):
                raise ValueError("No official news items")
            payload["status"] = "ok"
            write(name, payload)
            print(f"Updated {name} at {datetime.now(timezone.utc).isoformat()}", flush=True)
        except Exception as exc:
            failed.append(name)
            print(f"FAILED {name}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
