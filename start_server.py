#!/usr/bin/env python3
"""Market Lens AI personal demo server. Uses ECB public reference FX XML."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
import xml.etree.ElementTree as ET
import json
import os
import hashlib
import re
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time
from pathlib import Path
from datetime import datetime, timezone
from functools import lru_cache

ROOT = Path(__file__).resolve().parent
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
PORT = int(os.environ.get("PORT", "8765"))

@lru_cache(maxsize=1)
def _dummy():
    return None

def fetch_fx():
    req = Request(ECB_URL, headers={"User-Agent": "MarketLensPersonalPrototype/0.4"})
    with urlopen(req, timeout=12) as resp:
        xml = resp.read(1_000_000)
    root = ET.fromstring(xml)
    days = []
    for el in root.iter():
        date = el.attrib.get("time")
        if date:
            rates = {}
            for child in el:
                code = child.attrib.get("currency")
                rate = child.attrib.get("rate")
                if code in ("JPY","USD","GBP","AUD") and rate:
                    rates[code] = float(rate)
            if len(rates) == 4 and all(v > 0 for v in rates.values()):
                days.append((date, rates))
    days.sort(reverse=True)
    if len(days) < 2:
        raise ValueError("ECBデータに比較可能な2営業日がありません")
    current_date, current = days[0]
    prev_date, previous = days[1]
    def cross(r, currency):
        return r["JPY"] if currency == "EUR" else r["JPY"] / r[currency]
    names = {"USD": ("usdjpy","ドル／円"), "EUR": ("eurjpy","ユーロ／円"),
             "GBP": ("gbpjpy","ポンド／円"), "AUD": ("audjpy","豪ドル／円")}
    rows = []
    for c, (ident, name) in names.items():
        value, prior = cross(current,c), cross(previous,c)
        change = value-prior
        rows.append({"id":ident,"name":name,"value":round(value,6),
                     "change":round(change,6),"pct":round(change/prior*100,5),
                     "unit":"円","type":"ECB参考レート（クロス計算）" if c!="EUR" else "ECB参考レート",
                     "date":current_date,"source":"European Central Bank",
                     "source_url":ECB_URL})
    return {"date":current_date,"previous_date":prev_date,"indicators":rows,
            "source":"European Central Bank","source_url":ECB_URL,
            "retrieved_at":datetime.now(timezone.utc).isoformat()}

# RSS sources are official public institution feeds. A failed source is reported, not replaced by fabricated headlines.
FEEDS = [
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html"),
]
RULES = [
 (r"interest rate|policy rate|federal funds|monetary policy|rate decision|rate cut|rate hike|金利|利上げ|利下げ", "金利・中央銀行", 4),
 (r"inflation|consumer price|cpi|pce|price stability|インフレ|物価", "物価・インフレ", 3),
 (r"financial stability|banking crisis|liquidity|emergency|bank failure|金融危機", "金融システム", 4),
 (r"employment|unemployment|jobs|payroll|雇用", "雇用", 3),
 (r"foreign exchange|exchange rate|currency|yen|dollar|為替|円安|円高", "為替", 3),
 (r"economic projections|economic outlook|recession|gdp|growth|景気|経済見通し", "景気", 2),
 (r"press conference|governing council|fomc|statement", "金融政策", 2),
]
news_cache={"until":0,"payload":None}
news_lock=Lock()

def parse_feed(source,url):
    req=Request(url,headers={"User-Agent":"MarketLensPersonalPrototype/0.5 (+personal RSS reader)","Accept":"application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urlopen(req,timeout=9) as response:
        raw=response.read(900_000)
    root=ET.fromstring(raw)
    items=[]
    for entry in root.iter():
        if entry.tag.rsplit('}',1)[-1] not in ("item","entry"):
            continue
        fields={}
        for child in entry:
            tag=child.tag.rsplit('}',1)[-1]
            if tag in ("title","link","pubDate","published","updated","summary","description"):
                val=(child.text or "").strip()
                if tag=="link" and not val:val=child.attrib.get("href","")
                fields[tag]=val
        title=re.sub(r"<[^>]+>","",fields.get("title","")).strip()[:220]
        link=fields.get("link","")
        if not title or not link.startswith("https://"):
            continue
        stamp=fields.get("pubDate") or fields.get("published") or fields.get("updated") or ""
        try:
            dt=parsedate_to_datetime(stamp)
            published=dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            sort=dt.timestamp()
        except Exception:
            try:
                dt=datetime.fromisoformat(stamp.replace("Z","+00:00"))
                sort=dt.timestamp();published=dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                published="";sort=0
        text=title+" "+re.sub(r"<[^>]+>","",fields.get("summary") or fields.get("description") or "")[:500]
        score=0;topics=[]
        for pattern,topic,weight in RULES:
            if re.search(pattern,text,re.I):score+=weight;topics.append(topic)
        items.append({"id":hashlib.sha256(link.encode()).hexdigest()[:20],"title":title,"link":link,"source":source,
                      "published":published,"_sort":sort,"priority":"high" if score>=3 else "normal",
                      "topic":"・".join(topics[:2]) if topics else "経済・金融"})
    return items[:40]

def fetch_news():
    now=time.time()
    with news_lock:
        if news_cache["payload"] is not None and now<news_cache["until"]:
            return news_cache["payload"]
        all_items=[];errors=[]
        with ThreadPoolExecutor(max_workers=len(FEEDS)) as pool:
            futures=[pool.submit(parse_feed,*feed) for feed in FEEDS]
            for (source,_),future in zip(FEEDS,futures):
                try:all_items.extend(future.result(timeout=12))
                except Exception as exc:errors.append(source+": "+str(exc)[:100])
        if not all_items:
            raise ValueError("ニュースソースを取得できませんでした。"+"; ".join(errors))
        unique={item["id"]:item for item in all_items}
        ordered=sorted(unique.values(),key=lambda x:x["_sort"],reverse=True)[:60]
        for item in ordered:item.pop("_sort",None)
        result={"retrieved_at":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "items":ordered,"sources":[s for s,_ in FEEDS],"errors":errors,
                "classification":"keyword-only; potential relevance, not confirmed market impact"}
        news_cache.update(until=now+300,payload=result)
        return result

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_GET(self):
        if self.path.split("?")[0] in ("/api/fx","/api/news"):
            try:
                result=fetch_news() if self.path.split("?")[0]=="/api/news" else fetch_fx()
                body=json.dumps(result,ensure_ascii=False).encode("utf-8")
                status=200
            except (URLError, TimeoutError, ValueError, ET.ParseError, OSError) as exc:
                body=json.dumps({"error":str(exc)},ensure_ascii=False).encode("utf-8")
                status=503
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()
    def end_headers(self):
        self.send_header("X-Frame-Options","DENY")
        super().end_headers()

if __name__=="__main__":
    print(f"Market Lens AI: http://127.0.0.1:{PORT}")
    print("ECB FX and official RSS news; charts, equities and AI remain demo.")
    ThreadingHTTPServer(("127.0.0.1",PORT),Handler).serve_forever()
