#!/usr/bin/env python3
"""Generate static data files for GitHub Pages. No secrets or external packages."""
import json
from datetime import datetime, timezone
from pathlib import Path
from start_server import fetch_fx, fetch_news

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

def write(name, obj):
    path = DATA / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)

if __name__ == '__main__':
    succeeded = 0
    for name, fn in [('fx.json', fetch_fx), ('news.json', fetch_news)]:
        try:
            payload = fn()
            payload['status'] = 'ok'
            write(name, payload)
            succeeded += 1
            print(f'Updated {name} at {datetime.now(timezone.utc).isoformat()}')
        except Exception as exc:
            # Preserve last known-good data, so failures do not fabricate new prices/news.
            print(f'FAILED {name}: {exc}')
    if succeeded == 0:
        raise SystemExit('No data sources updated. Existing data preserved.')
