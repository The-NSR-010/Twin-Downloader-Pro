from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal

PROXYSCRAPE_JSON = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/all/data.json"
TEST_URL = "https://example.com/"

@dataclass
class ProxyRecord:
    url: str
    protocol: str = "http"
    country: str = "—"
    city: str = "—"
    anonymity: str = "—"
    uptime: str = "—"
    provider_latency_ms: int | None = None
    measured_latency_ms: int | None = None
    alive: bool = False
    source: str = "ProxyScrape"

    @property
    def latency_text(self):
        v=self.measured_latency_ms if self.measured_latency_ms is not None else self.provider_latency_ms
        return f"{v} ms" if v is not None else "—"


def _json(url: str, timeout: float = 20):
    req=urllib.request.Request(url,headers={"User-Agent":"MediaDownloaderStudio/0.4"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8","replace"))


def fetch_proxies(limit=60,country="",protocol="http"):
    country=country.strip().lower()
    protocol=protocol.strip().lower() or "http"
    if country and len(country)!=2:
        raise ValueError("Country must be a 2-letter ISO code, e.g. IN, US or DE.")
    # Use country/protocol shards where possible: smaller, faster and deterministic.
    if country:
        url=f"https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/countries/{country}/{protocol}/data.json"
    else:
        url=f"https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/protocols/{protocol}/data.json"
    try:
        rows=_json(url)
    except Exception:
        # fallback to all-proxy metadata feed
        rows=_json(PROXYSCRAPE_JSON)
    if not isinstance(rows,list):
        raise RuntimeError("Proxy provider returned an unexpected response.")
    out=[]
    for row in rows:
        if not isinstance(row,dict): continue
        p=str(row.get("protocol") or protocol).lower()
        if protocol and p!=protocol: continue
        cc=str(row.get("country_code") or row.get("country") or "—").upper()
        if country and cc.lower()!=country: continue
        ip=str(row.get("ip") or "").strip(); port=str(row.get("port") or "").strip()
        if not ip or not port: continue
        out.append(ProxyRecord(
            url=f"{p}://{ip}:{port}", protocol=p, country=cc,
            city=str(row.get("city") or "—"), anonymity=str(row.get("anonymity") or "—"),
            uptime=(f"{row.get('uptime_percent')}%" if row.get("uptime_percent") is not None else "—"),
            provider_latency_ms=int(row["latency_ms"]) if str(row.get("latency_ms","")).isdigit() else None))
        if len(out)>=limit: break
    return out


def test_proxy(record: ProxyRecord, timeout=5.0):
    if not record.protocol.startswith(("http","https")):
        record.alive=False; return record
    handler=urllib.request.ProxyHandler({"http":record.url,"https":record.url})
    opener=urllib.request.build_opener(handler)
    req=urllib.request.Request(TEST_URL,headers={"User-Agent":"MediaDownloaderStudio/0.4"})
    start=time.perf_counter()
    try:
        with opener.open(req,timeout=timeout) as r:
            r.read(64); record.alive=200 <= getattr(r,"status",200) < 500
    except Exception:
        record.alive=False
    record.measured_latency_ms=int((time.perf_counter()-start)*1000) if record.alive else None
    return record


def test_many(records,workers=16):
    out=[]
    with ThreadPoolExecutor(max_workers=max(1,min(workers,32))) as pool:
        fs=[pool.submit(test_proxy,r) for r in records]
        for f in as_completed(fs):
            try: out.append(f.result())
            except Exception: pass
    out.sort(key=lambda r:(not r.alive,r.measured_latency_ms if r.measured_latency_ms is not None else 10**9))
    return out


class ProxyScanWorker(QThread):
    status=Signal(str); ready=Signal(object); failed=Signal(str)
    def __init__(self,limit=30,country="",protocol="http"):
        super().__init__(); self.limit=limit; self.country=country; self.protocol=protocol
    def run(self):
        try:
            self.status.emit("Fetching public proxy metadata…")
            records=fetch_proxies(self.limit,self.country,self.protocol)
            if not records: raise RuntimeError("No public proxies matched the selected country/protocol.")
            self.status.emit(f"Testing {len(records)} candidates from this computer…")
            self.ready.emit(test_many(records))
        except Exception as exc:
            self.failed.emit(str(exc))
