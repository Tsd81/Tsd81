#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерира черновата на седмичното издание и я вмъква в master файла.

Автоматично се попълва САМО количествената част (3.2, 3.3, части от 3.1 и
структурния прочит). Разделите, които изискват преценка по РАЗДЕЛ 2 —
проверката на новини, рейтингите и изводите — излизат с маркер
[ЗА ПОПЪЛВАНЕ] и се дописват от аналитика.

Изданието се вмъква НАЙ-ОТГОРЕ в РАЗДЕЛ 3 (между EDITIONS маркерите), а в
РАЗДЕЛ 4 се добавя по един ред за цените и за промените в класацията.
Повторен пуск за същата седмица ПРЕЗАПИСВА нейното издание, вместо да дублира.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analysis  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "crypto" / "CRYPTO-TOP40-MONITORING.md"

TRACKED_IN_TIMESERIES = ["BTC", "ETH", "SOL", "XRP", "BNB", "HYPE", "ZEC"]
PLACEHOLDER = "**[ЗА ПОПЪЛВАНЕ]**"


# ------------------------------------------------------- форматиране

def _bg(text: str) -> str:
    """Десетичен разделител — запетая, както в останалата част на файла."""
    return text.replace(".", ",")


def fmt_price(val) -> str:
    if val is None:
        return "—"
    if val >= 1000:
        return "$" + f"{val:,.0f}".replace(",", " ")
    if val >= 1:
        return "$" + _bg(f"{val:.2f}")
    if val >= 0.01:
        return "$" + _bg(f"{val:.4f}")
    return "$" + _bg(f"{val:.6f}")


def fmt_money(val) -> str:
    """Три значещи цифри, както в базовото издание: $1,59T · $302,9 млрд. · $144,2 хил."""
    if val is None:
        return "—"
    for divisor, unit in ((1e12, "T"), (1e9, " млрд."), (1e6, " млн."), (1e3, " хил.")):
        if val >= divisor:
            scaled = val / divisor
            return "$" + _bg(f"{scaled:.{2 if scaled < 10 else 1}f}") + unit
    return "$" + _bg(f"{val:.0f}")


def vtm_digits(val) -> int:
    """Единна точност за обем/капитализация в цялото издание."""
    if val is None:
        return 2
    if val < 0.001:
        return 4
    return 3 if val < 0.01 else 2


def fmt_pct(val, *, signed: bool = True) -> str:
    if val is None:
        return "—"
    return _bg(f"{val:+.1f}%" if signed else f"{val:.1f}%")


def fmt_ratio_pct(val, digits: int = 2) -> str:
    if val is None:
        return "—"
    return _bg(f"{val * 100:.{digits}f}%")


def fmt_x(val) -> str:
    return "—" if val is None else _bg(f"{val:.2f}×")


def iso_week_label(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.week}/{iso.year}"


def week_range(d: date) -> str:
    start = d - timedelta(days=6)
    return f"{start.day:02d}.{start.month:02d}–{d.day:02d}.{d.month:02d}.{d.year}"


# --------------------------------------------------------- секции

def build_macro(result: dict) -> str:
    g = result.get("global") or {}
    rows = [
        "| Фактор | Състояние | Достоверност |",
        "|---|---|---|",
        f"| Обща пазарна капитализация | {fmt_money(g.get('total_market_cap_usd'))} "
        f"({fmt_pct(g.get('market_cap_change_pct_24h'))} за 24 ч) | ✅ Пазарни данни |",
        f"| Доминация BTC / ETH | {fmt_pct(g.get('btc_dominance_pct'), signed=False)} / "
        f"{fmt_pct(g.get('eth_dominance_pct'), signed=False)} | ✅ Пазарни данни |",
        f"| Общ 24ч обем | {fmt_money(g.get('total_volume_24h_usd'))} | ✅ Пазарни данни |",
        f"| BTC ETF потоци | {PLACEHOLDER} | |",
        f"| Fed / макро | {PLACEHOLDER} | |",
        f"| Fear & Greed | {PLACEHOLDER} | |",
        f"| Ливъридж и фъндинг | {PLACEHOLDER} | |",
    ]
    return "\n".join(rows) + (
        f"\n\n**Прочит:** {PLACEHOLDER} — обобщение в 2–4 изречения кой е двигателят на седмицата "
        f"и кой е основният риск за следващата.\n"
    )


def signal_marks(coin: dict) -> str:
    if not coin["signals"]:
        return ""
    top = coin["signals"][0]
    mark = analysis.SEVERITY_MARK[top["severity"]]
    extra = f" ×{len(coin['signals'])}" if len(coin["signals"]) > 1 else ""
    return f"{mark}{extra}"


def build_main_table(result: dict) -> str:
    header = (
        "| # | Актив | Клас | Цена | Пазарна кап. | FDV | FDV/MC | 24ч обем | Об./Кап. | "
        "7д % | 30д % | От ATH | Сигн. |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [header]
    for c in result["coins"]:
        pegged = analysis.is_pegged(c)
        vtm = c.get("volume_to_mcap")
        vtm_cell = fmt_ratio_pct(vtm, vtm_digits(vtm))
        if vtm is not None and vtm < analysis.THIN_MARKET and not pegged:
            vtm_cell = f"**{vtm_cell}**"
        lines.append(
            f"| {c['rank']} | {c['symbol']} | {c['asset_class']} | {fmt_price(c.get('price_usd'))} | "
            f"{fmt_money(c.get('market_cap_usd'))} | {fmt_money(c.get('fully_diluted_valuation_usd'))} | "
            f"{fmt_x(c.get('fdv_to_mcap'))} | {fmt_money(c.get('total_volume_usd'))} | {vtm_cell} | "
            f"{'—' if pegged else fmt_pct(c.get('pct_7d'))} | "
            f"{'—' if pegged else fmt_pct(c.get('pct_30d'))} | "
            f"{'—' if pegged else fmt_pct(c.get('ath_change_pct'))} | {signal_marks(c)} |"
        )
    return "\n".join(lines)


def build_structural_read(result: dict) -> str:
    coins = result["coins"]
    counts = result["class_counts"]
    g = result.get("global") or {}
    total = len(coins)
    pegged = counts.get("D", 0)
    meme = counts.get("F", 0)
    unverified = counts.get("G", 0)

    decliners = sorted(
        (c for c in coins if not analysis.is_pegged(c) and (c.get("pct_7d") or 0) < 0),
        key=lambda c: c.get("pct_7d") or 0,
    )
    gainers = sorted(
        (c for c in coins if not analysis.is_pegged(c) and c.get("pct_7d") is not None),
        key=lambda c: c["pct_7d"], reverse=True,
    )

    def coin_list(items, limit=5):
        return ", ".join(f"{c['symbol']} ({fmt_pct(c.get('pct_7d'))})" for c in items[:limit]) or "—"

    btc = next((c for c in coins if c["symbol"] == "BTC"), None)

    return "\n".join([
        f"- **{pegged} от {total} са стабилни/обвързани монети** (клас D) — "
        f"{fmt_pct(pegged / total * 100, signed=False)} от списъка без потенциал за поскъпване по дефиниция. "
        f"Меме/наративни (F): {meme}. Непроверени (G): {unverified}. "
        f"**Реален аналитичен обхват: {result['analysable_count']} актива.**",
        f"- **Доминация BTC:** {fmt_pct(g.get('btc_dominance_pct'), signed=False)}"
        + (f" при капитализация {fmt_money(btc.get('market_cap_usd'))} от общо "
           f"{fmt_money(g.get('total_market_cap_usd'))}." if btc else "."),
        f"- **Най-силни за седмицата:** {coin_list(gainers)}",
        f"- **Най-слаби за седмицата:** {coin_list(decliners)}",
        f"- **{len(decliners)} актива са надолу за седмицата** от "
        f"{sum(1 for c in coins if not analysis.is_pegged(c))} нестабилни.",
        f"- **Прочит на модела:** {PLACEHOLDER} — кой клас води, кой изостава и защо.",
    ])


def build_liquidity(result: dict) -> str:
    flagged = [
        c for c in result["coins"]
        if not analysis.is_pegged(c) and c.get("volume_to_mcap") is not None
        and (c["volume_to_mcap"] < analysis.THIN_MARKET or c["volume_to_mcap"] >= analysis.HIGH_TURNOVER)
    ]
    if not flagged:
        return ("Няма актив с обем/капитализация под 0,5% или над 25% за тази седмица.\n\n"
                "**Правило за портфейл:** актив с обем/капитализация под 0,5% не се третира като "
                "ликвиден. Публикуваната капитализация не е стойност, която може да се реализира.\n")

    flagged.sort(key=lambda c: c["volume_to_mcap"])
    lines = ["| Актив | Обем/капитализация | Оценка |", "|---|---|---|"]
    for c in flagged:
        vtm = c["volume_to_mcap"]
        if vtm < analysis.ILLIQUID_CRITICAL:
            verdict = ("⛔ Практически няма вторичен пазар. Капитализацията е счетоводна величина — "
                       "не може да се излезе от позиция.")
        elif vtm < analysis.THIN_MARKET:
            verdict = "⚠️ Тънък пазар. Цената е лесно управляема с малък капитал."
        elif vtm >= analysis.EXTREME_TURNOVER:
            verdict = ("⛔ Оборот над 100% от капитализацията за денонощие — проверка за изкуствен обем "
                       "(модел 4 от 2.4).")
        else:
            verdict = "Обратната крайност — висок оборот, характерен за спекулативна/разпределителна фаза."
        lines.append(f"| {c['symbol']} | **{fmt_ratio_pct(vtm, vtm_digits(vtm))}** | {verdict} |")

    return "\n".join(lines) + (
        "\n\n**Правило за портфейл:** актив с обем/капитализация под 0,5% не се третира като ликвиден. "
        "Публикуваната капитализация не е стойност, която може да се реализира.\n"
    )


def build_priority(result: dict) -> str:
    """Кои активи задължително минават през протокола на РАЗДЕЛ 2 тази седмица."""
    ranked = sorted(result["coins"], key=lambda c: c["attention_score"], reverse=True)
    ranked = [c for c in ranked if c["attention_score"] >= 25][:8]
    if not ranked:
        return "Няма актив със структурен сигнал над прага за задължителна проверка тази седмица.\n"

    out = [
        "Активите по-долу са с най-висок структурен сигнал и **минават задължително** през "
        "протокола на РАЗДЕЛ 2, независимо дали седмицата е изглеждала спокойна.\n",
    ]
    for c in ranked:
        out.append(f"**{c['symbol']}** (клас {c['asset_class']}, сигнал {c['attention_score']}/100 — "
                   f"{c['attention_band']}):")
        for s in c["signals"][:4]:
            out.append(f"- {analysis.SEVERITY_MARK[s['severity']]} {s['text']}")
        out.append("")
    return "\n".join(out)


def build_unverified(result: dict) -> str:
    unknown = [c for c in result["coins"] if c["asset_class"] == "G"]
    intro = ("Тези активи са в топ 40, но нямат установен клас или достатъчна проверима информация. "
             "**Това само по себе си е сигнал за риск** — актив за милиарди долари без ясен "
             "информационен профил е или много нов, или непрозрачен.\n")
    if not unknown:
        return intro + "\nЗа тази седмица няма актив без установен клас.\n"
    lines = [intro, "| Актив | Капитализация | Обем/кап. | Какво липсва |", "|---|---|---|---|"]
    for c in unknown:
        lines.append(
            f"| **{c['symbol']}** | {fmt_money(c.get('market_cap_usd'))} | "
            f"{fmt_ratio_pct(c.get('volume_to_mcap'), vtm_digits(c.get('volume_to_mcap')))} | {PLACEHOLDER} — емитент, структура на "
            f"предлагането, откъде идва капитализацията |"
        )
    lines.append(f"\n**Действие за следващото издание:** {PLACEHOLDER}")
    return "\n".join(lines)


def build_rank_changes(result: dict) -> str:
    moves = [
        c for c in result["coins"]
        if (c["deltas"].get("rank_change_w1") or 0) and abs(c["deltas"]["rank_change_w1"]) >= 3
    ]
    moves.sort(key=lambda c: abs(c["deltas"]["rank_change_w1"]), reverse=True)
    entered = ", ".join(result["entered"]) or "—"
    exited = ", ".join(result["exited"]) or "—"
    lines = [
        f"**Влезли в топ 40:** {entered}",
        f"**Излезли от топ 40:** {exited}",
        "",
    ]
    if moves:
        lines.append("| Актив | Промяна в ранга | Нов ранг | Цена 7д |")
        lines.append("|---|---|---|---|")
        for c in moves[:10]:
            delta = c["deltas"]["rank_change_w1"]
            lines.append(
                f"| {c['symbol']} | {'▲' if delta > 0 else '▼'} {abs(delta)} | {c['rank']} | "
                f"{fmt_pct(c.get('pct_7d'))} |"
            )
    else:
        lines.append("Няма изместване с 3 или повече позиции спрямо предходната седмица.")
    return "\n".join(lines)


# ------------------------------------------------------- издание

def build_edition(result: dict, snap_date: date, week_label: str) -> str:
    meta = result["meta"]
    base = not result.get("previous_date")

    return f"""<!-- EDITION:{meta['iso_week']} -->
---

# 📅 СЕДМИЦА {week_label} — {week_range(snap_date)}

**Дата на снимката:** {snap_date.strftime('%d.%m.%Y')}
**Източник на пазарните данни:** {meta.get('source')} ({', '.join(meta.get('endpoints', []))}), \
събрани автоматично на {meta.get('fetched_at_utc')}
**Статус:** {'БАЗОВО ИЗДАНИЕ — няма предходна седмица за сравнение.' if base else
             f"Сравнение спрямо снимката от {result['previous_date']}."}
**Проверка по РАЗДЕЛ 2:** {PLACEHOLDER} — незавършена, докато не се попълнят 3.4, 3.6 и 3.7.

## 3.1. Макро фон на седмицата

{build_macro(result)}

## 3.2. Таблица топ 40 ({snap_date.strftime('%d.%m.%Y')})

{build_main_table(result)}

Легенда за колоната „Сигн.“: ⛔ висок структурен сигнал · ⚠️ среден · • нисък. Числото след знака е \
общият брой сигнали за актива. Подробностите са в 3.3а.

### Структурен прочит на таблицата

{build_structural_read(result)}

### Промени в класацията

{build_rank_changes(result)}

## 3.3. Аномалии в ликвидността (изисква внимание)

{build_liquidity(result)}

## 3.3а. Приоритети за проверка по РАЗДЕЛ 2

{build_priority(result)}

## 3.4. Проверка на информацията

{PLACEHOLDER} — 3–5 новини, движили цени тази седмица. За всяка: твърдение, рейтинг по 2.3 с % \
увереност, ниво на източника по 2.1, задействани червени флагове по 2.2 и заключение.

| Твърдение | Актив | Рейтинг (увереност) | Ниво на източника | Флагове |
|---|---|---|---|---|
| {PLACEHOLDER} | | | | |

## 3.5. Активи с недостатъчен информационен профил

{build_unverified(result)}

## 3.6. Задълбочен анализ на актив от седмицата

{PLACEHOLDER} — един актив с най-висок структурен сигнал или най-съществена новина. Показатели по \
1.2, катализатор, рейтинг за достоверност, прочит.

## 3.7. Изводи за седмицата

{PLACEHOLDER} — 3–5 номерирани извода. Задължително включи: кой е двигателят на движението \
(макро или крипто), кои активи са структурно неликвидни и коя новина пазарът е ценообразувал \
без потвърждение.

## 3.8. Какво НЕ беше възможно да се провери

{PLACEHOLDER} — изрично изброяване, съгласно РАЗДЕЛ 6, т.6. Липсата на информация се записва, \
не се пропуска.
"""


def timeseries_price_row(result: dict, week_label: str, snap_date: date) -> str:
    by_symbol = {c["symbol"]: c for c in result["coins"]}
    cells = []
    for sym in TRACKED_IN_TIMESERIES:
        coin = by_symbol.get(sym)
        cells.append(
            _bg(f"{coin['price_usd']:,.2f}").replace(",", " ") if coin and coin.get("price_usd") else "—"
        )
    total = fmt_money((result.get("global") or {}).get("total_market_cap_usd"))
    label = f"{week_label} ({snap_date.strftime('%d.%m')})"
    return f"| {label} | " + " | ".join(cells) + f" | {total} |"


def timeseries_rank_row(result: dict, week_label: str) -> str:
    entered = ", ".join(result["entered"]) or "—"
    exited = ", ".join(result["exited"]) or "—"
    moves = [
        (c["symbol"], c["deltas"]["rank_change_w1"])
        for c in result["coins"]
        if (c["deltas"].get("rank_change_w1") or 0) and abs(c["deltas"]["rank_change_w1"]) >= 3
    ]
    moves.sort(key=lambda m: abs(m[1]), reverse=True)
    notable = ", ".join(f"{s} {'▲' if d > 0 else '▼'}{abs(d)}" for s, d in moves[:5]) or "—"
    return f"| {week_label} | {entered} | {exited} | {notable} |"


# ------------------------------------------------------- вмъкване

def splice(text: str, marker: str, payload: str, *, prepend: bool) -> str:
    start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    pattern = re.compile(re.escape(start) + r"\n(.*?)" + re.escape(end), re.DOTALL)
    match = pattern.search(text)
    if not match:
        raise SystemExit(f"ГРЕШКА: маркерът {marker} липсва в {MASTER.name}")
    body = match.group(1)
    new_body = f"{payload}\n{body}" if prepend else f"{body}{payload}\n"
    return text[: match.start()] + f"{start}\n{new_body}{end}" + text[match.end():]


def drop_existing_edition(text: str, iso_week: str) -> str:
    """Маха предишна чернова за същата седмица, за да е идемпотентен пускът."""
    marker = f"<!-- EDITION:{iso_week} -->"
    if marker not in text:
        return text
    start = text.index(marker)
    nxt = text.find("<!-- EDITION:", start + len(marker))
    end = nxt if nxt != -1 else text.index("<!-- EDITIONS:END -->")
    print(f"  · Съществуващо издание за {iso_week} се презаписва.")
    return text[:start] + text[end:]


def drop_existing_row(text: str, marker: str, label: str) -> str:
    start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    pattern = re.compile(re.escape(start) + r"\n(.*?)" + re.escape(end), re.DOTALL)
    match = pattern.search(text)
    if not match:
        return text
    kept = [ln for ln in match.group(1).splitlines() if not ln.startswith(f"| {label} ")]
    body = "\n".join(kept)
    if body and not body.endswith("\n"):
        body += "\n"
    return text[: match.start()] + f"{start}\n{body}{end}" + text[match.end():]


def main() -> int:
    ap = argparse.ArgumentParser(description="Изгражда седмичното издание в master файла")
    ap.add_argument("--snapshot", default=None, help="път до снимка (по подразбиране най-новата)")
    ap.add_argument("--dry-run", action="store_true", help="печата изданието, без да пипа файла")
    args = ap.parse_args()

    snap_path = Path(args.snapshot) if args.snapshot else analysis.latest_snapshot_path()
    if not snap_path or not snap_path.exists():
        print("ГРЕШКА: няма налична снимка. Пусни първо fetch_market_data.py.", file=sys.stderr)
        return 1

    snapshot = analysis.load_snapshot(snap_path)
    result = analysis.analyse(snapshot)

    snap_date = datetime.strptime(result["meta"]["snapshot_date"], "%Y-%m-%d").date()
    week_label = iso_week_label(snap_date)
    edition = build_edition(result, snap_date, week_label)

    if args.dry_run:
        print(edition)
        return 0

    text = MASTER.read_text(encoding="utf-8")
    text = drop_existing_edition(text, result["meta"]["iso_week"])
    text = drop_existing_row(text, "TS-PRICES", f"{week_label} ({snap_date.strftime('%d.%m')})")
    text = drop_existing_row(text, "TS-RANKS", week_label)

    text = splice(text, "EDITIONS", edition, prepend=True)
    text = splice(text, "TS-PRICES", timeseries_price_row(result, week_label, snap_date), prepend=False)
    text = splice(text, "TS-RANKS", timeseries_rank_row(result, week_label), prepend=False)
    text = re.sub(
        r"\*\*Последна актуализация:\*\* .*",
        f"**Последна актуализация:** {snap_date.strftime('%d.%m.%Y')}",
        text, count=1,
    )

    MASTER.write_text(text, encoding="utf-8")

    todo = edition.count(PLACEHOLDER)
    try:
        where = MASTER.relative_to(ROOT)
    except ValueError:  # при тест master файлът е извън хранилището
        where = MASTER
    print(f"✓ Издание {week_label} е вмъкнато в {where}")
    print(f"✓ РАЗДЕЛ 4: добавени редове за цени и класация")
    print(f"→ Остават {todo} места [ЗА ПОПЪЛВАНЕ] — качественият анализ по РАЗДЕЛ 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
