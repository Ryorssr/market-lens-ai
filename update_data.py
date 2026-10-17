#!/usr/bin/env python3
"""Refresh static market data; preserve previously successful files."""
import csv
import io
import json
import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from start_server import fetch_fx, fetch_news

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)


def get_text(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (Market Lens AI)"})
    with urlopen(request, timeout=12) as response:
        return response.read(2_000_000).decode("utf-8-sig")


def fetch_treasury():
    today = datetime.now(timezone.utc).date()
    observations = []
    errors = []

    # Primary: official US Treasury yield-curve XML, current and previous month.
    for month in (today, today.replace(day=1) - timedelta(days=1)):
        ym = month.strftime("%Y%m")
        url = ("https://home.treasury.gov/resource-center/data-chart-center/"
               "interest-rates/pages/xml?data=daily_treasury_yield_curve"
               "&field_tdr_date_value_month=" + ym)
        try:
            root = ET.fromstring(get_text(url))
            for entry in root.iter():
                if entry.tag.rsplit("}", 1)[-1] != "properties":
                    continue
                fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
                          for child in entry}
                date_str = fields.get("NEW_DATE", "")[:10]
                raw = fields.get("BC_10YEAR", "")
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    yield_pct = float(raw)
                    if math.isfinite(yield_pct) and 0 <= yield_pct < 30:
                        observations.append((date, yield_pct))
                except (ValueError, TypeError):
                    continue
        except Exception as exc:
            errors.append(f"Treasury {ym}: {type(exc).__name__}: {exc}")

    source = "U.S. Department of the Treasury"
    source_url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"

    # Fallback: request only the recent FRED CSV observations, not the full history.
    if len(set(d for d, _ in observations)) < 2:
        start = (today - timedelta(days=45)).isoformat()
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urlencode(
            {"id": "DGS10", "cosd": start})
        try:
            for row in csv.DictReader(io.StringIO(get_text(url))):
                date_str = row.get("DATE") or row.get("observation_date") or ""
                raw = row.get("DGS10", "")
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    yield_pct = float(raw)
                    if math.isfinite(yield_pct) and 0 <= yield_pct < 30:
                        observations.append((date, yield_pct))
                except (ValueError, TypeError):
                    continue
            if observations:
                source = "U.S. Treasury / FRED DGS10"
                source_url = "https://fred.stlouisfed.org/series/DGS10"
        except Exception as exc:
            errors.append(f"FRED: {type(exc).__name__}: {exc}")

    daily = dict(observations)
    recent = sorted(daily.items(), reverse=True)
    if len(recent) < 2:
        raise ValueError("No usable Treasury observations. " + "; ".join(errors))
    (latest_date, value), (previous_date, previous_value) = recent[:2]
    if (today - latest_date).days > 10:
        raise ValueError(f"Treasury data is stale: {latest_date}")

    return {
        "date": latest_date.isoformat(),
        "previous_date": previous_date.isoformat(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "indicators": [{
            "id": "us10y", "name": "米10年国債利回り",
            "value": round(value, 4),
            "change": round(value - previous_value, 4),
            "pct": None, "unit": "%", "date": latest_date.isoformat(),
            "type": "米国10年国債利回り・日次（差は%ポイント）",
            "source": source, "source_url": source_url
        }]
    }


def write(name, payload):
    path = DATA / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(path)


def main():
    failed = []
    for name, fetcher in (("fx.json", fetch_fx), ("news.json", fetch_news),
                          ("treasury.json", fetch_treasury)):
        try:
            payload = fetcher()
            if not isinstance(payload, dict):
                raise ValueError("Invalid data format")
            if name == "fx.json" and (
                not payload.get("date") or len(payload.get("indicators", [])) != 4
            ):
                raise ValueError("Incomplete ECB FX data")
            if name == "news.json" and not payload.get("items"):
                raise ValueError("No official news items")
            if name == "treasury.json" and len(payload.get("indicators", [])) != 1:
                raise ValueError("Incomplete treasury data")
            payload["status"] = "ok"
            write(name, payload)
            print(f"Updated {name} at {datetime.now(timezone.utc).isoformat()}",
                  flush=True)
        except Exception as exc:
            failed.append(name)
            print(f"FAILED {name}: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
