#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Събира пазарни данни за първите N криптовалути по пазарна капитализация.

Източник: CoinGecko public API (/coins/markets + /global). Не изисква ключ.
Ако е наличен COINGECKO_API_KEY, се използва demo/pro endpoint-ът.

Резултат:
  * crypto/data/snapshots/<YYYY-MM-DD>.json  -- пълен снимков файл за седмицата
  * crypto/data/history.csv                  -- дълга времева серия (append-only)

Скриптът НИКОГА не измисля данни. При липса на мрежа/отговор той се проваля
с ненулев изход, за да не се генерира доклад с празни или фалшиви числа.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "crypto" / "data"
SNAP_DIR = DATA_DIR / "snapshots"
HISTORY_CSV = DATA_DIR / "history.csv"

PUBLIC_BASE = "https://api.coingecko.com/api/v3"
PRO_BASE = "https://pro-api.coingecko.com/api/v3"

PCT_WINDOWS = "1h,24h,7d,14d,30d,200d,1y"

HISTORY_FIELDS = [
    "snapshot_date",
    "fetched_at_utc",
    "rank",
    "id",
    "symbol",
    "name",
    "price_usd",
    "market_cap_usd",
    "fully_diluted_valuation_usd",
    "total_volume_usd",
    "circulating_supply",
    "total_supply",
    "max_supply",
    "pct_1h",
    "pct_24h",
    "pct_7d",
    "pct_14d",
    "pct_30d",
    "pct_200d",
    "pct_1y",
    "ath_usd",
    "ath_change_pct",
    "ath_date",
    "atl_usd",
    "atl_change_pct",
]


class FetchError(RuntimeError):
    """Мрежова или API грешка, при която не бива да се продължава."""


def _headers() -> dict[str, str]:
    hdrs = {
        "Accept": "application/json",
        "User-Agent": "Tsd81-weekly-crypto-analysis/1.0 (+https://github.com/Tsd81/Tsd81)",
    }
    key = os.environ.get("COINGECKO_API_KEY", "").strip()
    if key:
        header_name = (
            "x-cg-pro-api-key"
            if os.environ.get("COINGECKO_PLAN", "demo").lower() == "pro"
            else "x-cg-demo-api-key"
        )
        hdrs[header_name] = key
    return hdrs


def _base_url() -> str:
    key = os.environ.get("COINGECKO_API_KEY", "").strip()
    plan = os.environ.get("COINGECKO_PLAN", "demo").lower()
    return PRO_BASE if (key and plan == "pro") else PUBLIC_BASE


def http_get_json(path: str, params: dict[str, object], *, attempts: int = 5):
    """GET с експоненциален backoff. Уважава 429 (rate limit) на CoinGecko."""
    url = f"{_base_url()}{path}?{urllib.parse.urlencode(params)}"
    delay = 3.0
    last_err: Exception | None = None

    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_err = exc
            # 429 = rate limit, 5xx = временен проблем -> повтори
            if exc.code not in (429, 500, 502, 503, 504):
                raise FetchError(f"HTTP {exc.code} за {path}: {exc.reason}") from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
            print(f"  ! HTTP {exc.code} ({path}), опит {attempt}/{attempts}, чакам {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            delay = min(delay * 2, 60)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
            print(f"  ! {type(exc).__name__} ({path}), опит {attempt}/{attempts}, чакам {delay:.0f}s", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 60)

    raise FetchError(f"Неуспешно извличане на {path} след {attempts} опита: {last_err}")


def fetch_markets(top_n: int, vs_currency: str, buffer: int = 10) -> list[dict]:
    """Взима top_n + buffer монети (буферът покрива размествания в ранга)."""
    per_page = min(250, top_n + buffer)
    data = http_get_json(
        "/coins/markets",
        {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": PCT_WINDOWS,
            "locale": "en",
        },
    )
    if not isinstance(data, list) or not data:
        raise FetchError("CoinGecko /coins/markets върна празен или неочакван отговор")
    return data


def fetch_global() -> dict:
    data = http_get_json("/global", {})
    if not isinstance(data, dict) or "data" not in data:
        raise FetchError("CoinGecko /global върна неочакван отговор")
    return data["data"]


def normalise(coin: dict, rank_fallback: int) -> dict:
    """Свежда записа на CoinGecko до стабилна вътрешна схема."""

    def num(key: str):
        val = coin.get(key)
        return val if isinstance(val, (int, float)) else None

    return {
        "rank": coin.get("market_cap_rank") or rank_fallback,
        "id": coin.get("id"),
        "symbol": (coin.get("symbol") or "").upper(),
        "name": coin.get("name"),
        "price_usd": num("current_price"),
        "market_cap_usd": num("market_cap"),
        "fully_diluted_valuation_usd": num("fully_diluted_valuation"),
        "total_volume_usd": num("total_volume"),
        "circulating_supply": num("circulating_supply"),
        "total_supply": num("total_supply"),
        "max_supply": num("max_supply"),
        "pct_1h": num("price_change_percentage_1h_in_currency"),
        "pct_24h": num("price_change_percentage_24h_in_currency"),
        "pct_7d": num("price_change_percentage_7d_in_currency"),
        "pct_14d": num("price_change_percentage_14d_in_currency"),
        "pct_30d": num("price_change_percentage_30d_in_currency"),
        "pct_200d": num("price_change_percentage_200d_in_currency"),
        "pct_1y": num("price_change_percentage_1y_in_currency"),
        "ath_usd": num("ath"),
        "ath_change_pct": num("ath_change_percentage"),
        "ath_date": coin.get("ath_date"),
        "atl_usd": num("atl"),
        "atl_change_pct": num("atl_change_percentage"),
    }


def write_snapshot(snapshot: dict, snapshot_date: str) -> Path:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / f"{snapshot_date}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_history(coins: list[dict], snapshot_date: str, fetched_at: str) -> int:
    """Дописва седмичните редове. Идемпотентно: пренаписва реда за същата дата."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if HISTORY_CSV.exists():
        with HISTORY_CSV.open(encoding="utf-8", newline="") as fh:
            existing = [r for r in csv.DictReader(fh) if r.get("snapshot_date") != snapshot_date]

    new_rows = []
    for coin in coins:
        row = {"snapshot_date": snapshot_date, "fetched_at_utc": fetched_at}
        row.update({k: coin.get(k) for k in HISTORY_FIELDS if k not in row})
        new_rows.append(row)

    with HISTORY_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HISTORY_FIELDS)
        writer.writeheader()
        for row in existing + new_rows:
            writer.writerow({k: row.get(k, "") for k in HISTORY_FIELDS})

    return len(new_rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Събира top-N крипто пазарни данни от CoinGecko")
    ap.add_argument("--top", type=int, default=40, help="брой валути (по подразбиране 40)")
    ap.add_argument("--vs", default="usd", help="валута за котиране (по подразбиране usd)")
    ap.add_argument("--date", default=None, help="дата на снимката YYYY-MM-DD (по подразбиране днес UTC)")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    snapshot_date = args.date or now.strftime("%Y-%m-%d")
    fetched_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"→ Извличам top-{args.top} по пазарна капитализация ({args.vs.upper()})...")
    raw = fetch_markets(args.top, args.vs)
    coins = [normalise(c, i + 1) for i, c in enumerate(raw)][: args.top]

    if len(coins) < args.top:
        raise FetchError(f"Получени са само {len(coins)} валути вместо {args.top}")

    print("→ Извличам глобални пазарни показатели...")
    glob = fetch_global()

    snapshot = {
        "meta": {
            "snapshot_date": snapshot_date,
            "fetched_at_utc": fetched_at,
            "iso_week": now.strftime("%G-W%V"),
            "source": "CoinGecko API v3",
            "endpoints": ["/coins/markets", "/global"],
            "vs_currency": args.vs,
            "top_n": args.top,
            "note": "Автоматично събрани първични данни. Без ръчна намеса.",
        },
        "global": {
            "total_market_cap_usd": (glob.get("total_market_cap") or {}).get("usd"),
            "total_volume_24h_usd": (glob.get("total_volume") or {}).get("usd"),
            "market_cap_change_pct_24h": glob.get("market_cap_change_percentage_24h_usd"),
            "btc_dominance_pct": (glob.get("market_cap_percentage") or {}).get("btc"),
            "eth_dominance_pct": (glob.get("market_cap_percentage") or {}).get("eth"),
            "active_cryptocurrencies": glob.get("active_cryptocurrencies"),
        },
        "coins": coins,
    }

    snap_path = write_snapshot(snapshot, snapshot_date)
    rows = append_history(coins, snapshot_date, fetched_at)

    print(f"✓ Снимка: {snap_path.relative_to(ROOT)}")
    print(f"✓ История: {HISTORY_CSV.relative_to(ROOT)} (+{rows} реда за {snapshot_date})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FetchError as exc:
        print(f"ГРЕШКА: {exc}", file=sys.stderr)
        print("Докладът НЕ се генерира — по-добре липсващ отчет, отколкото отчет с непроверени числа.", file=sys.stderr)
        sys.exit(1)
