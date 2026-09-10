"""Live quote fetching for the Boggle portfolio notebook.

Yahoo Finance chart API via stdlib urllib — no API key, no third-party client.
Quotes are cached to data/quotes_cache.json; pass max_age_minutes=0 to force refresh.
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
CACHE = DATA / "quotes_cache.json"
UA = {"User-Agent": "Mozilla/5.0"}
_CA = os.environ.get("BOGGLE_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE")
_CTX = ssl.create_default_context(cafile=_CA) if _CA else ssl.create_default_context()


def _fetch_one(sym: str, retries: int = 3) -> dict:
    """Return {'price': float, 'currency': str, 'time': iso, 'error': str|None} for one symbol."""
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(sym)}?range=5d&interval=1d"
    )
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20, context=_CTX) as r:
                j = json.load(r)
            res = (j.get("chart") or {}).get("result")
            if not res:
                return {"price": None, "error": "no result"}
            m = res[0]["meta"]
            px = m.get("regularMarketPrice")
            ts = m.get("regularMarketTime")
            return {
                "price": px,
                "currency": m.get("currency"),
                "exchange": m.get("exchangeName"),
                "time": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
                "error": None if px is not None else "no price in meta",
            }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"price": None, "error": "404 not found"}
            last = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(1.5 * (i + 1))
    return {"price": None, "error": last}


def get_quotes(symbols, max_age_minutes: int = 20, workers: int = 8, verbose: bool = True) -> dict:
    """Fetch (or reuse cached) last prices for `symbols`. Returns {symbol: record}."""
    symbols = [s for s in dict.fromkeys(symbols) if s]
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text())
        except json.JSONDecodeError:
            cache = {}

    now = time.time()
    stale = [
        s
        for s in symbols
        if s not in cache
        or cache[s].get("price") is None
        or now - cache[s].get("_fetched", 0) > max_age_minutes * 60
    ]
    if verbose:
        print(f"{len(symbols)} symbols; {len(stale)} to fetch, {len(symbols) - len(stale)} from cache")

    if stale:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for sym, rec in zip(stale, ex.map(_fetch_one, stale)):
                rec["_fetched"] = time.time()
                cache[sym] = rec
        DATA.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True))

    failed = [s for s in symbols if cache.get(s, {}).get("price") is None]
    if verbose and failed:
        print(f"no live price for {len(failed)}: {', '.join(failed[:12])}{' …' if len(failed) > 12 else ''}")
    return {s: cache[s] for s in symbols if s in cache}


HIST_CACHE = DATA / "history_cache.json"


def _fetch_history(sym: str, period1: int, interval: str = "1wk", retries: int = 3) -> dict:
    """Weekly (or other interval) closes for one symbol: {'YYYY-MM-DD': close}."""
    p2 = int(time.time()) + 86400
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(sym)}?period1={period1}&period2={p2}&interval={interval}"
    )
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25, context=_CTX) as r:
                j = json.load(r)
            res = (j.get("chart") or {}).get("result")
            if not res:
                return {"bars": {}, "error": "no result"}
            r0 = res[0]
            off = r0["meta"].get("gmtoffset", 0)
            closes = r0["indicators"]["quote"][0].get("close") or []
            bars = {}
            for k, t in enumerate(r0.get("timestamp") or []):
                c = closes[k] if k < len(closes) else None
                if c is None:
                    continue
                bars[datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d")] = c
            return {"bars": bars, "error": None}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"bars": {}, "error": "404 not found"}
            last = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(1.5 * (i + 1))
    return {"bars": {}, "error": last}


def get_history(symbols, start="2025-12-05", interval="1wk", max_age_hours=12,
                workers=8, verbose=True) -> "dict[str, dict]":
    """Historical closes per symbol from `start`. Cached in data/history_cache.json.

    Returns {symbol: {'YYYY-MM-DD': close, ...}}.  Yahoo closes are split-adjusted to
    today's share count, matching the DOD prices in data/dod_prices.csv.
    """
    symbols = [s for s in dict.fromkeys(symbols) if s]
    period1 = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    key = f"{start}|{interval}"

    cache = {}
    if HIST_CACHE.exists():
        try:
            cache = json.loads(HIST_CACHE.read_text())
        except json.JSONDecodeError:
            cache = {}
    cache.setdefault(key, {})
    book = cache[key]

    now = time.time()
    stale = [s for s in symbols
             if s not in book or not book[s].get("bars") or now - book[s].get("_fetched", 0) > max_age_hours * 3600]
    if verbose:
        print(f"history: {len(symbols)} symbols, {len(stale)} to fetch ({interval} from {start})")

    if stale:
        fetch = lambda s: _fetch_history(s, period1, interval)  # noqa: E731
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for sym, rec in zip(stale, ex.map(fetch, stale)):
                rec["_fetched"] = time.time()
                book[sym] = rec
        DATA.mkdir(exist_ok=True)
        HIST_CACHE.write_text(json.dumps(cache, separators=(",", ":"), sort_keys=True))

    empty = [s for s in symbols if not book.get(s, {}).get("bars")]
    if verbose and empty:
        print(f"no history for {len(empty)}: {', '.join(empty[:12])}{' …' if len(empty) > 12 else ''}")
    return {s: book[s]["bars"] for s in symbols if book.get(s, {}).get("bars")}
