#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Регресионен тест на конвейера върху СИНТЕТИЧНИ данни.

Конвейерът се изпълнява без надзор в GitHub Actions, затова се проверява, че:
  * анализът смята съотношенията и времевите редове коректно;
  * структурните сигнали се задействат на правилните прагове;
  * изданието се вмъква в master файла и е идемпотентно при повторен пуск.

Работи в отделна временна директория — НЕ пипа реалните данни и master файла.
Синтетичните числа тук са фикстури за тест, не пазарни данни.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analysis
import build_edition

REAL_ROOT = Path(__file__).resolve().parents[2]

# Отклонение в седмичната доходност по актив — дава разсейване на кохортата,
# за да може да се тества откриването на статистически отскок.
SPREAD = {
    "SOL": 11.8, "ZEC": 2.1, "XMR": 16.5, "LINK": 1.0, "ADA": -9.6, "XLM": -9.1,
    "BCH": -7.3, "XRP": -6.1, "DOGE": -7.5, "BTC": 1.7, "ETH": 1.9, "BNB": -0.1,
    "TRX": -0.9, "HYPE": 1.2, "LEO": 2.4, "WBT": 0.4, "RAIN": 4.0,
    "BNT9": 78.0,  # очакван отскок над кохортата
}

FIXTURES = [
    # id, symbol, name, price, mcap, fdv, volume, circ, total
    ("bitcoin", "BTC", "Bitcoin", 79027.0, 1.59e12, 1.66e12, 6.31e9, 19.9e6, 21e6),
    ("ethereum", "ETH", "Ethereum", 2509.72, 3.029e11, 3.029e11, 3.63e9, 120e6, 120e6),
    ("tether", "USDT", "Tether", 0.9998, 1.834e11, 1.834e11, 9.0e10, 183e9, 183e9),
    ("solana", "SOL", "Solana", 106.61, 6.24e10, 7.4e10, 1.33e9, 585e6, 694e6),
    ("hyperliquid", "HYPE", "Hyperliquid", 83.30, 2.49e10, 8.3e10, 2.778e8, 299e6, 1e9),
    ("leo-token", "LEO", "LEO Token", 9.71, 8.93e9, 8.93e9, 1.442e5, 920e6, 920e6),
    ("whitebit", "WBT", "WhiteBIT Token", 72.91, 2.14e10, 2.9e10, 3.68e7, 293e6, 400e6),
    ("zcash", "ZEC", "Zcash", 871.94, 1.47e10, 1.83e10, 4.71e9, 16.9e6, 21e6),
    ("rain", "RAIN", "Rain", 0.01738, 1.23e10, 4.9e10, 1.64e7, 708e9, 2.8e12),
    ("dogecoin", "DOGE", "Dogecoin", 0.08634, 1.48e10, 1.48e10, 2.163e8, 171e9, None),
    ("cardano", "ADA", "Cardano", 0.2051, 7.69e9, 9.23e9, 1.208e8, 37e9, 45e9),
    ("monero", "XMR", "Monero", 490.94, 9.23e9, 9.23e9, 9.93e7, 18.8e6, None),
    ("chainlink", "LINK", "Chainlink", 11.66, 8.72e9, 1.166e10, 1.5e8, 748e6, 1e9),
    ("usd-coin", "USDC", "USDC", 0.9998, 7.39e10, 7.39e10, 1.1e10, 73.9e9, 73.9e9),
    ("ripple", "XRP", "XRP", 1.43, 8.94e10, 1.43e11, 9.582e8, 62.5e9, 100e9),
    ("binancecoin", "BNB", "BNB", 701.40, 9.34e10, 9.34e10, 2.767e8, 133e6, 133e6),
    ("tron", "TRX", "TRON", 0.3407, 3.24e10, 3.24e10, 1.237e8, 95e9, None),
    ("stellar", "XLM", "Stellar", 0.1817, 6.30e9, 9.09e9, 8.95e7, 34.7e9, 50e9),
    ("bitcoin-cash", "BCH", "Bitcoin Cash", 254.05, 5.10e9, 5.33e9, 4.73e7, 20e6, 21e6),
    ("brand-new-token", "BNT9", "Brand New Token", 4.20, 4.9e9, 2.1e10, 8.0e8, 1.16e9, 5e9),
]


def make_snapshot(snap_date: date, price_multiplier: float, btc_volume_multiplier: float) -> dict:
    """btc_volume_multiplier се прилага само към BTC — така скокът в обема се
    тества изолирано, без да размества оборота на останалите активи."""
    coins = []
    for rank, (cid, sym, name, price, mcap, fdv, vol, circ, total) in enumerate(FIXTURES, start=1):
        stable = sym in ("USDT", "USDC")
        mult = 1.0 if stable else price_multiplier
        coins.append({
            "rank": rank, "id": cid, "symbol": sym, "name": name,
            "price_usd": price * mult,
            "market_cap_usd": mcap * mult,
            "fully_diluted_valuation_usd": fdv * mult if fdv else None,
            "total_volume_usd": vol * (btc_volume_multiplier if sym == "BTC" else 1.0),
            "circulating_supply": circ, "total_supply": total, "max_supply": total,
            "pct_1h": 0.1, "pct_24h": (mult - 1) * 60,
            "pct_7d": None if stable else (mult - 1) * 100 + SPREAD.get(sym, 0.0),
            "pct_14d": None, "pct_30d": (mult - 1) * 150, "pct_200d": None, "pct_1y": None,
            "ath_usd": price * 1.5, "ath_change_pct": -33.0,
            "ath_date": "2026-08-27T00:00:00.000Z",
            "atl_usd": price * 0.1, "atl_change_pct": 900.0,
        })
    return {
        "meta": {
            "snapshot_date": snap_date.isoformat(),
            "fetched_at_utc": f"{snap_date.isoformat()}T06:07:00Z",
            "iso_week": snap_date.strftime("%G-W%V"),
            "source": "СИНТЕТИЧНИ ТЕСТОВИ ДАННИ", "endpoints": ["selftest"],
            "vs_currency": "usd", "top_n": len(FIXTURES),
            "note": "Фикстура за регресионен тест. Не са пазарни данни.",
        },
        "global": {
            "total_market_cap_usd": 2.6e12 * price_multiplier,
            "total_volume_24h_usd": 1.4e11,
            "market_cap_change_pct_24h": (price_multiplier - 1) * 50,
            "btc_dominance_pct": 61.2, "eth_dominance_pct": 11.6,
            "active_cryptocurrencies": 18000,
        },
        "coins": coins,
    }


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  {'✓' if condition else '✗'} {label}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def run() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="crypto-selftest-"))
    failures = 0
    try:
        data = tmp / "crypto" / "data"
        (data / "snapshots").mkdir(parents=True)
        shutil.copy(REAL_ROOT / "crypto" / "data" / "classification.json", data / "classification.json")
        master = tmp / "crypto" / "CRYPTO-TOP40-MONITORING.md"
        shutil.copy(REAL_ROOT / "crypto" / "CRYPTO-TOP40-MONITORING.md", master)

        # пренасочваме модулите към временната директория
        for mod in (analysis,):
            mod.DATA_DIR, mod.SNAP_DIR = data, data / "snapshots"
            mod.HISTORY_CSV = data / "history.csv"
            mod.CLASSIFICATION = data / "classification.json"
        build_edition.MASTER = master

        sys.path.insert(0, str(REAL_ROOT / "crypto" / "scripts"))
        import fetch_market_data as fetcher
        fetcher.DATA_DIR, fetcher.SNAP_DIR = data, data / "snapshots"
        fetcher.HISTORY_CSV = data / "history.csv"

        # --- три последователни седмици ---
        # Пет седмици: медианата на оборота изисква поне 3 предходни снимки,
        # затова сигналите volume_spike / move_without_volume оживяват от 4-тата.
        base = date(2026, 8, 3)
        weeks = [
            (base, 0.86, 1.0),
            (base + timedelta(days=7), 0.90, 1.0),
            (base + timedelta(days=14), 0.93, 1.0),
            (base + timedelta(days=21), 0.95, 1.0),
            (base + timedelta(days=28), 1.00, 3.5),
        ]
        for snap_date, pm, vm in weeks:
            snap = make_snapshot(snap_date, pm, vm)
            fetcher.write_snapshot(snap, snap_date.isoformat())
            fetcher.append_history(snap["coins"], snap_date.isoformat(), snap["meta"]["fetched_at_utc"])

        print("\n1) Анализ на последната седмица")
        latest = analysis.load_snapshot(data / "snapshots" / f"{weeks[-1][0].isoformat()}.json")
        result = analysis.analyse(latest)
        by_sym = {c["symbol"]: c for c in result["coins"]}

        failures += not check("40-те реда се анализират", len(result["coins"]) == len(FIXTURES))
        failures += not check("историята дава 5 седмици",
                              by_sym["BTC"]["deltas"]["weeks_tracked"] == 5,
                              str(by_sym["BTC"]["deltas"]["weeks_tracked"]))
        w1 = by_sym["BTC"]["deltas"]["price_change_w1_pct"]
        failures += not check("седмичната промяна е ~+5,26%", w1 and abs(w1 - 5.263) < 0.01, f"{w1}")
        w4 = by_sym["BTC"]["deltas"]["price_change_w4_pct"]
        failures += not check("4-седмичната промяна е ~+16,3%", w4 and abs(w4 - 16.279) < 0.01, f"{w4}")

        print("\n2) Класификация")
        failures += not check("BTC е клас A", by_sym["BTC"]["asset_class"] == "A")
        failures += not check("USDT е клас D", by_sym["USDT"]["asset_class"] == "D")
        failures += not check("HYPE е клас C", by_sym["HYPE"]["asset_class"] == "C")
        failures += not check("непознат актив пада в клас G", by_sym["BNT9"]["asset_class"] == "G")
        failures += not check("аналитичният обхват изключва D и F",
                              result["analysable_count"] == sum(
                                  1 for c in result["coins"] if c["asset_class"] in "ABCE"))

        print("\n3) Структурни сигнали")
        codes = {s: {f["code"] for f in by_sym[s]["signals"]} for s in by_sym}
        failures += not check("LEO е маркиран като критично неликвиден",
                              "illiquid_critical" in codes["LEO"], str(codes["LEO"]))
        failures += not check("WBT е маркиран като тънък пазар",
                              "thin_market" in codes["WBT"], str(codes["WBT"]))
        failures += not check("HYPE е маркиран за разводняване (FDV/MC 3,3×)",
                              "dilution_high" in codes["HYPE"], str(codes["HYPE"]))
        failures += not check("ZEC (32% оборот) е маркиран като висок, не екстремен",
                              codes["ZEC"] >= {"high_turnover"}
                              and "extreme_turnover" not in codes["ZEC"], str(codes["ZEC"]))
        failures += not check("статистическият отскок над кохортата се хваща",
                              "outperformance_outlier" in codes["BNT9"], str(codes["BNT9"]))
        failures += not check("изоставането под кохортата се хваща",
                              any("underperformance_outlier" in codes[s2]
                                  for s2 in ("ADA", "XLM", "DOGE")),
                              str({k: codes[k] for k in ("ADA", "XLM", "DOGE")}))
        failures += not check("скокът в обема се хваща спрямо 8-седмичната медиана",
                              "volume_spike" in codes["BTC"], str(codes["BTC"]))
        failures += not check("клас G влиза автоматично в 3.5",
                              "unverified_profile" in codes["BNT9"], str(codes["BNT9"]))
        failures += not check("стабилна монета не получава сигнал за доходност",
                              not {"outperformance_outlier", "extreme_turnover"} & codes["USDT"],
                              str(codes["USDT"]))
        failures += not check("неликвидният LEO влиза в обхвата за проверка",
                              by_sym["LEO"]["attention_band"] in ("ПРОВЕРКА", "ПРИОРИТЕТ"),
                              by_sym["LEO"]["attention_band"])
        failures += not check("чист актив без сигнали не влиза в проверка",
                              by_sym["ETH"]["attention_score"] < by_sym["LEO"]["attention_score"],
                              f"ETH={by_sym['ETH']['attention_score']} "
                              f"LEO={by_sym['LEO']['attention_score']}")

        print("\n4) Изграждане на изданието")
        sys.argv = ["build_edition.py"]
        rc = build_edition.main()
        failures += not check("build_edition завършва успешно", rc == 0)

        last_date = weeks[-1][0]
        iso = last_date.strftime("%G-W%V")
        wlabel = build_edition.iso_week_label(last_date)
        price_label = f"| {wlabel} ({last_date.strftime('%d.%m')}) |"
        text = master.read_text(encoding="utf-8")
        failures += not check("изданието е вмъкнато", f"<!-- EDITION:{iso} -->" in text)
        failures += not check("изданието е НАД базовото от С35",
                              text.index(f"EDITION:{iso}") < text.index("СЕДМИЦА 35/2026"))
        failures += not check("редът за цени е добавен в 4.1", price_label in text)
        failures += not check("редът за класация е добавен в 4.2", f"| {wlabel} |" in text)
        failures += not check("маркерите са запазени",
                              text.count("<!-- EDITIONS:START -->") == 1
                              and text.count("<!-- TS-PRICES:END -->") == 1)
        failures += not check("базовото издание от С35 е непокътнато",
                              "Cypherpunk Technologies" in text and "$79 027" in text)
        failures += not check("има места за ръчно попълване", build_edition.PLACEHOLDER in text)
        failures += not check("LEO е в таблицата с аномалии", "Практически няма вторичен пазар" in text)
        prio = text.split("3.3а. Приоритети")[1].split("## 3.4.")[0]
        failures += not check("приоритетите за РАЗДЕЛ 2 сочат неликвидните активи",
                              "LEO" in prio and "WBT" in prio)

        print("\n5) Идемпотентност (повторен пуск за същата седмица)")
        build_edition.main()
        text2 = master.read_text(encoding="utf-8")
        failures += not check("изданието не се дублира", text2.count(f"<!-- EDITION:{iso} -->") == 1)
        failures += not check("редът в 4.1 не се дублира", text2.count(price_label) == 1)
        failures += not check("редът в 4.2 не се дублира", text2.count(f"| {wlabel} |") == 1)

        print("\n6) Идемпотентност на историята")
        snap = make_snapshot(weeks[-1][0], 1.00, 3.5)
        fetcher.append_history(snap["coins"], weeks[-1][0].isoformat(), "повторен пуск")
        rows = analysis.load_history()
        same_week = [r for r in rows if r["snapshot_date"] == weeks[-1][0].isoformat()]
        failures += not check("повторният пуск не дублира редове в history.csv",
                              len(same_week) == len(FIXTURES), f"{len(same_week)}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"РЕЗУЛТАТ: {failures} неуспешни проверки")
        return 1
    print("РЕЗУЛТАТ: всички проверки минават")
    return 0


if __name__ == "__main__":
    sys.exit(run())
