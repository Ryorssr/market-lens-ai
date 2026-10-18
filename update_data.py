#!/usr/bin/env python3
"""Market Lens AI: update official FX, Treasury and news data with actual histories."""
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
from start_server import fetch_fx, fetch_news, ECB_URL

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(parents=True, exist_ok=True)


def get_text(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Market Lens AI)'})
    with urlopen(req, timeout=15) as response:
        return response.read(2_000_000).decode('utf-8-sig')


def history_windows(points):
    """points: ascending list of (ISO date, numeric value). No synthetic values."""
    latest = datetime.strptime(points[-1][0], '%Y-%m-%d').date()
    periods = {'1W': 7, '1M': 31, '3M': 93, '1Y': 366, '5Y': 1827}
    result = {}
    for key, days in periods.items():
        subset = [round(value, 6) for date, value in points
                  if datetime.strptime(date, '%Y-%m-%d').date() >= latest - timedelta(days=days)]
        if len(subset) >= 2:
            result[key] = subset
    return result


def fetch_fx_history():
    root = ET.fromstring(get_text(ECB_URL))
    points = {c: [] for c in ('USD', 'EUR', 'GBP', 'AUD')}
    for el in root.iter():
        day = el.attrib.get('time')
        if not day:
            continue
        rates = {}
        for child in el:
            code = child.attrib.get('currency')
            if code in ('JPY', 'USD', 'GBP', 'AUD'):
                try:
                    rates[code] = float(child.attrib.get('rate', ''))
                except ValueError:
                    pass
        if len(rates) != 4 or not all(math.isfinite(v) and v > 0 for v in rates.values()):
            continue
        for c in points:
            points[c].append((day, rates['JPY'] if c == 'EUR' else rates['JPY'] / rates[c]))
    names = {'USD': 'usdjpy', 'EUR': 'eurjpy', 'GBP': 'gbpjpy', 'AUD': 'audjpy'}
    out = {}
    for currency, key in names.items():
        rows = sorted(dict(points[currency]).items())
        if len(rows) < 2:
            raise ValueError('Insufficient ECB historical data: ' + currency)
        out[key] = history_windows(rows)
    return out


def fetch_fx_with_history():
    payload = fetch_fx()
    history = fetch_fx_history()
    for row in payload['indicators']:
        row['history'] = history[row['id']]
    return payload


def fetch_treasury():
    today = datetime.now(timezone.utc).date()
    observations = []
    errors = []
    # Up to 4 monthly official Treasury feeds give 3M chart coverage.
    for offset in range(4):
        first = today.replace(day=1)
        month = (first - timedelta(days=1)).replace(day=1)
        for _ in range(offset - 1):
            month = (month - timedelta(days=1)).replace(day=1)
        if offset == 0:
            month = first
        ym = month.strftime('%Y%m')
        url = ('https://home.treasury.gov/resource-center/data-chart-center/'
               'interest-rates/pages/xml?data=daily_treasury_yield_curve'
               '&field_tdr_date_value_month=' + ym)
        try:
            root = ET.fromstring(get_text(url))
            for entry in root.iter():
                if entry.tag.rsplit('}', 1)[-1] != 'properties':
                    continue
                fields = {child.tag.rsplit('}', 1)[-1]: (child.text or '').strip()
                          for child in entry}
                try:
                    day = datetime.strptime(fields.get('NEW_DATE', '')[:10], '%Y-%m-%d').date()
                    value = float(fields.get('BC_10YEAR', ''))
                    if math.isfinite(value) and 0 <= value < 30:
                        observations.append((day.isoformat(), value))
                except (ValueError, TypeError):
                    continue
        except Exception as exc:
            errors.append(f'Treasury {ym}: {exc}')
    source = 'U.S. Department of the Treasury'
    source_url = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates'
    if len(dict(observations)) < 2:
        url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?' + urlencode(
            {'id': 'DGS10', 'cosd': (today - timedelta(days=110)).isoformat()})
        try:
            for row in csv.DictReader(io.StringIO(get_text(url))):
                day = row.get('DATE') or row.get('observation_date') or ''
                try:
                    datetime.strptime(day, '%Y-%m-%d')
                    value = float(row.get('DGS10', ''))
                    if math.isfinite(value) and 0 <= value < 30:
                        observations.append((day, value))
                except (ValueError, TypeError):
                    continue
            if len(dict(observations)) >= 2:
                source = 'FRED DGS10 (U.S. Treasury / FRB H.15)'
                source_url = 'https://fred.stlouisfed.org/series/DGS10'
        except Exception as exc:
            errors.append(f'FRED: {exc}')
    points = sorted(dict(observations).items())
    if len(points) < 2:
        raise ValueError('No usable Treasury observations: ' + '; '.join(errors))
    date, value = points[-1]
    previous_date, previous = points[-2]
    if (today - datetime.strptime(date, '%Y-%m-%d').date()).days > 10:
        raise ValueError('Treasury data stale: ' + date)
    return {
        'date': date, 'previous_date': previous_date,
        'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'indicators': [{
            'id': 'us10y', 'name': '米10年国債利回り',
            'value': round(value, 4), 'change': round(value - previous, 4),
            'pct': None, 'unit': '%', 'date': date,
            'type': '米国10年国債利回り・日次（差は%ポイント）',
            'source': source, 'source_url': source_url,
            'history': history_windows(points)
        }]
    }


def write(name, payload):
    path = DATA / name
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def main():
    failed = []
    for name, fetcher in (('fx.json', fetch_fx_with_history),
                          ('news.json', fetch_news), ('treasury.json', fetch_treasury)):
        try:
            payload = fetcher()
            if not isinstance(payload, dict):
                raise ValueError('Invalid payload')
            if name == 'fx.json' and len(payload.get('indicators', [])) != 4:
                raise ValueError('Incomplete FX data')
            if name == 'news.json' and not payload.get('items'):
                raise ValueError('No news items')
            if name == 'treasury.json' and len(payload.get('indicators', [])) != 1:
                raise ValueError('Incomplete Treasury data')
            payload['status'] = 'ok'
            write(name, payload)
            print('Updated ' + name, flush=True)
        except Exception as exc:
            failed.append(name)
            print(f'FAILED {name}: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
