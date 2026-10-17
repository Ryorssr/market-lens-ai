#!/usr/bin/env python3
"""Refresh market data for GitHub Pages, retaining good data on partial failure."""
import csv
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from start_server import fetch_fx, fetch_news

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)
TREASURY_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"

def fetch_treasury():
    req = Request(TREASURY_CSV, headers={"User-Agent": "MarketLensPersonalPrototype/0.7"})
    with urlopen(req, timeout=20) as response:
        body = response.read(3_000_000).decode("utf-8-sig")
    rows = []
    for row in csv.DictReader(io.StringIO(body)):
        raw = row.get("DGS10", "")
        date = row.get("DATE") or row.get("observation_date")
        if not date or not raw or raw == ".":
            continue
        try:
            val = float(raw)
            datetime.strptime(date, "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if math.isfinite(val) and 0 <= val < 30:
            rows.append((date, val))
    rows.sort(key=lambda x: x[0], reverse=True)
    if len(rows) < 2:
        raise ValueError("FRED DGS10 observations unavailable")
    latest, previous = rows[0], rows[1]
    if (datetime.now(timezone.utc).date() - datetime.strptime(latest[0], "%Y-%m-%d").date()).days > 10:
        raise ValueError("FRED DGS10 data is more than 10 days old")
    value, change = latest[1], latest[1] - previous[1]
    return {"date": latest[0], "previous_date": previous[0],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "indicators": [{"id": "us10y", "name": "米10年国債利回り",
                            "value": round(value, 4), "change": round(change, 4),
                            "pct": None, "unit": "%", "date": latest[0],
                            "type": "米財務省証券10年・日次（差は%ポイント）",
                            "source": "Federal Reserve H.15 via FRED",
                            "source_url": "https://fred.stlouisfed.org/series/DGS10"}]}

def write(name, payload):
    path = DATA / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)

def main():
    failed = []
    for name, fetcher in (("fx.json", fetch_fx), ("news.json", fetch_news),
                          ("treasury.json", fetch_treasury)):
        try:
            payload = fetcher()
            if not isinstance(payload, dict):
                raise ValueError("Invalid data format")
            if name == "fx.json" and (not payload.get("date") or len(payload.get("indicators", [])) != 4):
                raise ValueError("Incomplete ECB FX data")
            if name == "news.json" and not payload.get("items"):
                raise ValueError("No official news items")
            if name == "treasury.json" and len(payload.get("indicators", [])) != 1:
                raise ValueError("Incomplete treasury data")
            payload["status"] = "ok"
            write(name, payload)
            print(f"Updated {name} at {datetime.now(timezone.utc).isoformat()}", flush=True)
        except Exception as exc:
            failed.append(name)
            print(f"FAILED {name}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
