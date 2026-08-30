#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Аналитично ядро към методиката CRYPTO TOP-40.

Изчислява ЕДИНСТВЕНО количествените показатели от РАЗДЕЛ 1.2 и структурните
сигнали, които могат да се изведат от пазарни данни:

  * клас на актива (РАЗДЕЛ 1.1)
  * FDV/MC, обем/капитализация, разстояние от ATH
  * времеви редове спрямо предходни седмици (РАЗДЕЛ 4)
  * аномалии в ликвидността по правилото от 3.3 (под 0,5% = не е ликвиден)
  * статистически отскоци спрямо кохортата на топ 40

Каквото е количествено, се смята тук. Каквото изисква преценка —
рейтингът за достоверност (2.3), червените флагове (2.2) и скорът за
потенциал (1.3) — НЕ се смята автоматично: то се попълва от аналитика
по протокола. Скрипт не бива да раздава рейтинг „ПОТВЪРДЕНО“.
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "crypto" / "data"
SNAP_DIR = DATA_DIR / "snapshots"
HISTORY_CSV = DATA_DIR / "history.csv"
CLASSIFICATION = DATA_DIR / "classification.json"

STABLECOIN_SYMBOLS = {
    "USDT", "USDC", "DAI", "FDUSD", "USDE", "USDS", "PYUSD", "TUSD", "BUSD",
    "USDD", "FRAX", "BUIDL", "USD1", "RLUSD", "USDG", "USDF", "USDP", "XAUT", "PAXG",
}

# Прагове от методиката (РАЗДЕЛ 1.2 и 3.3).
THIN_MARKET = 0.005          # обем/кап под 0,5% -> не се третира като ликвиден
ILLIQUID_CRITICAL = 0.0005   # под 0,05% -> практически няма вторичен пазар
HIGH_TURNOVER = 0.25         # над 25% дневен оборот -> спекулативна фаза
EXTREME_TURNOVER = 1.00      # над 100% -> проверка за изкуствен обем

SEVERITY_ORDER = {"high": 0, "warn": 1, "info": 2}
SEVERITY_MARK = {"high": "⛔", "warn": "⚠️", "info": "•"}


def n(value, digits: int = 2, *, signed: bool = False) -> str:
    """Число с десетична запетая. Форматира се тук, при източника, а НЕ чрез
    подмяна в готовия текст — иначе препратките като „РАЗДЕЛ 1.1“ се развалят."""
    if value is None:
        return "—"
    return (f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}").replace(".", ",")


def pct(value, digits: int = 2, *, signed: bool = False) -> str:
    return "—" if value is None else n(value * 100 if abs(value) <= 1.5 else value, digits, signed=signed) + "%"


# ------------------------------------------------------------- зареждане

def load_classification() -> dict[str, str]:
    if not CLASSIFICATION.exists():
        return {}
    return (json.loads(CLASSIFICATION.read_text(encoding="utf-8")) or {}).get("map", {})


def load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_snapshot_path() -> Path | None:
    if not SNAP_DIR.exists():
        return None
    files = sorted(SNAP_DIR.glob("*.json"))
    return files[-1] if files else None


def _to_float(val):
    if val in (None, "", "None"):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


TEXT_FIELDS = {"snapshot_date", "fetched_at_utc", "id", "symbol", "name", "ath_date"}


def load_history() -> list[dict]:
    if not HISTORY_CSV.exists():
        return []
    rows = []
    with HISTORY_CSV.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            for key in list(row):
                if key not in TEXT_FIELDS:
                    row[key] = _to_float(row[key])
            rows.append(row)
    return rows


def history_by_coin(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["id"], []).append(row)
    for series in grouped.values():
        series.sort(key=lambda r: r["snapshot_date"])
    return grouped


# ------------------------------------------------------------ показатели

def safe_div(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def asset_class(coin: dict, classification: dict[str, str]) -> str:
    cls = classification.get(coin.get("id", ""))
    if cls:
        return cls
    if (coin.get("symbol") or "").upper() in STABLECOIN_SYMBOLS:
        return "D"
    return "G"


def is_pegged(coin: dict) -> bool:
    """Клас D — не се анализира за поскъпване, а за отклонение от котвата."""
    return coin.get("asset_class") == "D"


def enrich(coin: dict, total_mcap: float | None, classification: dict[str, str]) -> dict:
    out = dict(coin)
    out["asset_class"] = asset_class(coin, classification)
    out["volume_to_mcap"] = safe_div(coin.get("total_volume_usd"), coin.get("market_cap_usd"))
    out["fdv_to_mcap"] = safe_div(coin.get("fully_diluted_valuation_usd"), coin.get("market_cap_usd"))
    out["mcap_share_pct"] = (
        (coin["market_cap_usd"] / total_mcap * 100)
        if coin.get("market_cap_usd") and total_mcap else None
    )
    out["circulating_ratio"] = safe_div(
        coin.get("circulating_supply"), coin.get("max_supply") or coin.get("total_supply")
    )
    out["analysable"] = out["asset_class"] in ("A", "B", "C", "E")
    return out


# --------------------------------------------------------------- динамика

def compute_deltas(coin: dict, series: list[dict], current_date: str) -> dict:
    past = [r for r in series if r["snapshot_date"] < current_date]
    result: dict = {
        "weeks_tracked": len(series),
        "first_tracked_date": series[0]["snapshot_date"] if series else None,
    }

    def pct_change(old, new):
        if old in (None, 0) or new is None:
            return None
        return (new - old) / old * 100

    for label, back in (("w1", 1), ("w4", 4), ("w12", 12)):
        ref = past[-back] if len(past) >= back else None
        result[f"price_change_{label}_pct"] = pct_change(ref["price_usd"], coin.get("price_usd")) if ref else None
        result[f"mcap_change_{label}_pct"] = pct_change(ref["market_cap_usd"], coin.get("market_cap_usd")) if ref else None
        result[f"rank_change_{label}"] = (
            int(ref["rank"] - coin["rank"]) if ref and ref.get("rank") and coin.get("rank") else None
        )
        result[f"ref_date_{label}"] = ref["snapshot_date"] if ref else None

    first = series[0] if series else None
    result["price_change_since_start_pct"] = (
        pct_change(first["price_usd"], coin.get("price_usd"))
        if first and first["snapshot_date"] < current_date else None
    )

    ratios = [
        r["total_volume_usd"] / r["market_cap_usd"]
        for r in past[-8:]
        if r.get("total_volume_usd") and r.get("market_cap_usd")
    ]
    result["volume_to_mcap_median_8w"] = statistics.median(ratios) if len(ratios) >= 3 else None

    prices = [r["price_usd"] for r in past[-12:] if r.get("price_usd")]
    returns = [
        (prices[i] - prices[i - 1]) / prices[i - 1] * 100
        for i in range(1, len(prices)) if prices[i - 1]
    ]
    result["weekly_volatility_pct"] = statistics.pstdev(returns) if len(returns) >= 3 else None

    return result


# ------------------------------------------------- структурни сигнали

def _mad_stats(values: list[float]):
    clean = [v for v in values if v is not None]
    if len(clean) < 8:
        return None
    med = statistics.median(clean)
    sigma = statistics.median([abs(v - med) for v in clean]) * 1.4826
    return (med, sigma) if sigma > 0 else None


def cohort_statistics(coins: list[dict]) -> dict:
    stats = {}
    for field in ("pct_7d", "pct_24h", "pct_30d"):
        res = _mad_stats([c.get(field) for c in coins if not is_pegged(c)])
        if res:
            stats[field] = res
    return stats


def compute_signals(coin: dict, deltas: dict, cohort: dict) -> list[dict]:
    """Структурни сигнали от пазарни данни. Не са доказателство за манипулация —
    те насочват кои активи да минат през протокола на РАЗДЕЛ 2."""
    signals: list[dict] = []

    def add(code, severity, text):
        signals.append({"code": code, "severity": severity, "text": text})

    vtm = coin.get("volume_to_mcap")
    pegged = is_pegged(coin)

    # --- Ликвидност (3.3) ---
    if vtm is not None and not pegged:
        if vtm < ILLIQUID_CRITICAL:
            add("illiquid_critical", "high",
                f"Обем/капитализация {n(vtm * 100, 4)}% — практически няма вторичен пазар. "
                f"Публикуваната капитализация е счетоводна величина, а не стойност, която може "
                f"да бъде реализирана.")
        elif vtm < THIN_MARKET:
            add("thin_market", "high",
                f"Обем/капитализация {n(vtm * 100, 3)}% — под прага от 0,5%. Активът не се третира "
                f"като ликвиден; цената е лесно управляема с относително малък капитал.")
        elif vtm >= EXTREME_TURNOVER:
            add("extreme_turnover", "high",
                f"Дневен оборот {n(vtm * 100, 0)}% от капитализацията — целият пазарен размер се "
                f"преобръща за денонощие. Изисква проверка по кои борси е концентриран обемът "
                f"(модел 4 от 2.4 — изкупен обем).")
        elif vtm >= HIGH_TURNOVER:
            add("high_turnover", "warn",
                f"Дневен оборот {n(vtm * 100, 0)}% от капитализацията — характерно за спекулативна "
                f"или разпределителна фаза.")

    # --- Разводняване (1.2, т.3) ---
    fdv_ratio = coin.get("fdv_to_mcap")
    if fdv_ratio is not None and not pegged:
        if fdv_ratio >= 3.0:
            add("dilution_high", "high",
                f"FDV/MC = {n(fdv_ratio, 1)}× — над две трети от предлагането още не е в обращение. "
                f"Структурен натиск надолу и стимул за позитивен информационен поток преди отключвания "
                f"(времеви флаг от 2.2).")
        elif fdv_ratio >= 1.5:
            add("dilution_moderate", "warn",
                f"FDV/MC = {n(fdv_ratio, 2)}× — значителна част от предлагането предстои да бъде отключена.")

    # --- Клас D: отклонение от котвата ---
    if pegged and coin.get("price_usd") is not None and (coin.get("symbol") or "").upper() not in ("XAUT", "PAXG"):
        dev = abs(coin["price_usd"] - 1.0)
        if dev > 0.02:
            add("depeg", "high",
                f"Отклонение от котвата: {n(coin['price_usd'], 4)} USD ({n(dev * 100, 2)}%) — сигнал за "
                f"напрежение върху обезпечението или ликвидността на емитента.")
        elif dev > 0.005:
            add("depeg", "warn",
                f"Леко отклонение от котвата: {n(coin['price_usd'], 4)} USD ({n(dev * 100, 2)}%).")

    # --- Обем спрямо собствената норма ---
    med_vtm = deltas.get("volume_to_mcap_median_8w")
    if vtm is not None and med_vtm and not pegged:
        if vtm >= med_vtm * 3:
            add("volume_spike", "high",
                f"Оборотът е {n(vtm / med_vtm, 1)}× над собствената 8-седмична медиана. Рязък скок в обема "
                f"има причина — тя трябва да бъде идентифицирана и проверена по РАЗДЕЛ 2.")
        elif vtm >= med_vtm * 2:
            add("volume_spike", "warn",
                f"Оборотът е {n(vtm / med_vtm, 1)}× над 8-седмичната медиана на актива.")

    # --- Движение без обем ---
    pct24 = coin.get("pct_24h")
    if pct24 is not None and vtm and med_vtm and abs(pct24) >= 8 and vtm < med_vtm:
        add("move_without_volume", "high",
            f"Цената се е раздвижила с {n(pct24, 1, signed=True)}% за 24 ч при оборот ПОД собствената норма "
            f"({n(vtm * 100, 2)}% срещу медиана {n(med_vtm * 100, 2)}%). Голямо движение в тънка книга "
            f"с поръчки — най-уязвимият сценарий.")

    # --- Отскок спрямо кохортата ---
    stats_7d = cohort.get("pct_7d")
    pct7 = coin.get("pct_7d")
    if stats_7d and pct7 is not None and not pegged:
        med, sigma = stats_7d
        z = (pct7 - med) / sigma
        if z >= 3:
            add("outperformance_outlier", "high",
                f"Седмична доходност {n(pct7, 1, signed=True)}% — на {n(z, 1)} робастни σ над медианата "
                f"на топ 40 ({n(med, 1, signed=True)}%). Изисква документирана причина; при липса се "
                f"записва като наратив.")
        elif z >= 2:
            add("outperformance_outlier", "warn",
                f"Седмична доходност {n(pct7, 1, signed=True)}% — на {n(z, 1)} σ над медианата на кохортата.")
        elif z <= -3:
            add("underperformance_outlier", "high",
                f"Седмична доходност {n(pct7, 1, signed=True)}% — на {n(abs(z), 1)} робастни σ ПОД медианата "
                f"на топ 40 ({n(med, 1, signed=True)}%). Проверка за негативно събитие или координирано "
                f"негативно съдържание; липсата на документирана причина е самостоятелен сигнал.")
        elif z <= -2:
            add("underperformance_outlier", "warn",
                f"Седмична доходност {n(pct7, 1, signed=True)}% — на {n(abs(z), 1)} σ под медианата на кохортата.")

    # --- Класация ---
    rank_delta = deltas.get("rank_change_w1")
    if rank_delta is not None and abs(rank_delta) >= 5:
        add("rank_jump", "info",
            f"Изместване с {abs(rank_delta)} позиции {'нагоре' if rank_delta > 0 else 'надолу'} "
            f"в класацията за една седмица.")

    # --- Прозрачност на предлагането ---
    if coin.get("circulating_supply") is None or (
        coin.get("max_supply") is None and coin.get("total_supply") is None
    ):
        add("supply_opacity", "warn",
            "Липсват публични данни за част от параметрите на предлагането. Без тях капитализацията "
            "и FDV не могат да бъдат независимо преизчислени (ограничение по РАЗДЕЛ 6, т.4).")

    # --- Информационен профил (3.5) ---
    if coin.get("asset_class") == "G":
        add("unverified_profile", "high",
            "Активът няма установен клас по РАЗДЕЛ 1.1 — нов, непрозрачен или все още непроверен. "
            "Влиза автоматично в раздел 3.5 „Активи с недостатъчен информационен профил“.")

    if deltas.get("weeks_tracked", 0) <= 1:
        add("new_entrant", "info",
            "Първо появяване в проследяваната група — няма собствена история за сравнение. "
            "Изводите за него са с понижена увереност.")

    ath_chg = coin.get("ath_change_pct")
    if ath_chg is not None and ath_chg >= -5 and not pegged:
        add("at_ath", "info",
            f"Цената е на {n(abs(ath_chg), 1)}% от историческия връх. Новини при ATH изискват "
            f"по-строга проверка — това е зоната с най-силен стимул за позициониране.")

    signals.sort(key=lambda s: SEVERITY_ORDER[s["severity"]])
    return signals


def attention_score(signals: list[dict]) -> int:
    """0-100: колко приоритетно е активът да мине през протокола на РАЗДЕЛ 2.
    Това НЕ е скорът за потенциал (1.3) и НЕ е рейтинг за достоверност (2.3)."""
    weight = {"high": 25, "warn": 12, "info": 4}
    return int(min(100, sum(weight[s["severity"]] for s in signals)))


def attention_band(score: int) -> str:
    if score >= 50:
        return "ПРИОРИТЕТ"
    if score >= 25:
        return "ПРОВЕРКА"
    if score >= 10:
        return "НАБЛЮДЕНИЕ"
    return "—"


# ------------------------------------------------------------- обобщение

def analyse(snapshot: dict) -> dict:
    classification = load_classification()
    history = load_history()
    grouped = history_by_coin(history)
    total_mcap = (snapshot.get("global") or {}).get("total_market_cap_usd")
    current_date = snapshot["meta"]["snapshot_date"]

    coins = [enrich(c, total_mcap, classification) for c in snapshot["coins"]]
    cohort = cohort_statistics(coins)

    for coin in coins:
        deltas = compute_deltas(coin, grouped.get(coin["id"], []), current_date)
        coin["deltas"] = deltas
        coin["signals"] = compute_signals(coin, deltas, cohort)
        coin["attention_score"] = attention_score(coin["signals"])
        coin["attention_band"] = attention_band(coin["attention_score"])

    dates = sorted({r["snapshot_date"] for r in history})
    prev_date = next((d for d in reversed(dates) if d < current_date), None)
    prev_rows = [r for r in history if r["snapshot_date"] == prev_date] if prev_date else []
    prev_ids = {r["id"] for r in prev_rows}
    current_ids = {c["id"] for c in coins}

    by_class: dict[str, int] = {}
    for coin in coins:
        by_class[coin["asset_class"]] = by_class.get(coin["asset_class"], 0) + 1

    return {
        "meta": snapshot["meta"],
        "global": snapshot.get("global", {}),
        "coins": coins,
        "cohort_stats": cohort,
        "class_counts": by_class,
        "analysable_count": sum(1 for c in coins if c["analysable"]),
        "history_dates": dates,
        "previous_date": prev_date,
        "entered": sorted(
            (c["symbol"] for c in coins if c["id"] not in prev_ids), key=str
        ) if prev_date else [],
        "exited": sorted(
            (r["symbol"] for r in prev_rows if r["id"] not in current_ids), key=str
        ) if prev_date else [],
    }
