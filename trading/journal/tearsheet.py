"""trading/journal/tearsheet.py — Phase T5 HTML/PDF performance tearsheet.

Renders a self-contained, dependency-free "Dark Pro" HTML tearsheet from a list of
`ClosedTrade` (schema.py). The HTML is the source of truth; `render_tearsheet_pdf`
converts it to PDF via weasyprint. quantstats is used opportunistically to *add*
risk metrics (Sharpe/Sortino/max-drawdown) to the summary table, guarded so any
hiccup degrades to the built-in stats. Everything must render with one trade and
with an empty list — it never raises.

Public surface:
  render_tearsheet(trades, *, title, starting_equity) -> str (HTML)
  render_tearsheet_pdf(trades, path, **kw) -> str (path)
  equity_curve(trades, starting_equity) -> list[dict]
  monthly_pnl(trades) -> dict
"""
from __future__ import annotations

import math
from datetime import datetime

from trading.journal.schema import ClosedTrade

# ── Dark Pro palette ─────────────────────────────────────────────────────────
_BG = "#0d1117"
_PANEL = "#161b22"
_BORDER = "#30363d"
_FG = "#e6edf3"
_MUTED = "#8b949e"
_GREEN = "#26a641"
_RED = "#f85149"
_ACCENT = "#58a6ff"

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ── helpers ──────────────────────────────────────────────────────────────────
def _trade_dt(t: ClosedTrade) -> datetime | None:
    """Best-effort ISO timestamp for a trade (exit preferred, else entry)."""
    for raw in (t.exit_datetime, t.entry_datetime):
        if not raw:
            continue
        s = str(raw).strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(s[:len(fmt) + 4], fmt)
                except ValueError:
                    continue
    return None


def _fmt(v: float, prec: int = 2) -> str:
    try:
        return f"{v:,.{prec}f}"
    except (TypeError, ValueError):
        return "-"


def equity_curve(trades, starting_equity: float = 100000.0) -> list[dict]:
    """Cumulative equity + drawdown, one point per trade (plus the starting point)."""
    pts: list[dict] = [{"i": 0, "equity": float(starting_equity), "drawdown": 0.0}]
    equity = float(starting_equity)
    peak = equity
    for i, t in enumerate(trades, start=1):
        equity += float(getattr(t, "net_pnl", 0.0) or 0.0)
        peak = max(peak, equity)
        dd = (equity - peak) / peak if peak else 0.0
        pts.append({"i": i, "equity": equity, "drawdown": dd})
    return pts


def monthly_pnl(trades) -> dict:
    """Map of 'YYYY-MM' -> summed net_pnl across trades in that month."""
    out: dict[str, float] = {}
    for t in trades:
        dt = _trade_dt(t)
        if dt is None:
            continue
        key = f"{dt.year:04d}-{dt.month:02d}"
        out[key] = out.get(key, 0.0) + float(getattr(t, "net_pnl", 0.0) or 0.0)
    return out


def _summary_stats(trades, starting_equity: float) -> list[tuple[str, str, str]]:
    """Returns list of (label, value, sign) where sign in {'', 'pos', 'neg'}."""
    pnls = [float(getattr(t, "net_pnl", 0.0) or 0.0) for t in trades]
    charges = sum(float(getattr(t, "total_charges", 0.0) or 0.0) for t in trades)
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    net = sum(pnls)
    win_rate = (len(wins) / n * 100.0) if n else 0.0
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_win / gross_loss) if gross_loss else (math.inf if gross_win else 0.0)
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    expectancy = (net / n) if n else 0.0

    # streaks
    max_win_streak = max_loss_streak = cur_w = cur_l = 0
    for p in pnls:
        if p > 0:
            cur_w += 1
            cur_l = 0
        elif p < 0:
            cur_l += 1
            cur_w = 0
        else:
            cur_w = cur_l = 0
        max_win_streak = max(max_win_streak, cur_w)
        max_loss_streak = max(max_loss_streak, cur_l)

    best = max(pnls) if pnls else 0.0
    worst = min(pnls) if pnls else 0.0

    def sign(x: float) -> str:
        return "pos" if x > 0 else ("neg" if x < 0 else "")

    pf_str = "∞" if profit_factor == math.inf else _fmt(profit_factor)
    rows = [
        ("Total Trades", str(n), ""),
        ("Win Rate", f"{_fmt(win_rate)}%", sign(win_rate - 50.0) if n else ""),
        ("Net P&L", _fmt(net), sign(net)),
        ("Profit Factor", pf_str, sign(profit_factor - 1.0) if profit_factor != math.inf else "pos"),
        ("Expectancy", _fmt(expectancy), sign(expectancy)),
        ("Avg Win", _fmt(avg_win), "pos" if avg_win else ""),
        ("Avg Loss", _fmt(-avg_loss), "neg" if avg_loss else ""),
        ("Max Win Streak", str(max_win_streak), ""),
        ("Max Loss Streak", str(max_loss_streak), ""),
        ("Total Charges", _fmt(charges), "neg" if charges else ""),
        ("Best Trade", _fmt(best), sign(best)),
        ("Worst Trade", _fmt(worst), sign(worst)),
    ]
    return rows


def _quantstats_rows(trades, starting_equity: float) -> list[tuple[str, str, str]]:
    """Optional quantstats enrichment — fully guarded; returns [] on any issue."""
    try:
        import pandas as pd
        import quantstats as qs

        curve = equity_curve(trades, starting_equity)
        equities = [p["equity"] for p in curve]
        if len(equities) < 3:
            return []
        idx = []
        for i, t in enumerate(trades, start=1):
            dt = _trade_dt(t)
            idx.append(dt if dt is not None else None)
        # Build a daily-ish returns series indexed by trade order (synthetic dates if needed)
        dates = pd.date_range("2000-01-01", periods=len(equities), freq="D")
        eq = pd.Series(equities, index=dates, dtype="float64")
        returns = eq.pct_change().dropna()
        if returns.empty or returns.std() == 0:
            return []

        out: list[tuple[str, str, str]] = []
        try:
            sharpe = float(qs.stats.sharpe(returns))
            if math.isfinite(sharpe):
                out.append(("Sharpe (qs)", _fmt(sharpe), "pos" if sharpe > 0 else "neg"))
        except Exception:
            pass
        try:
            sortino = float(qs.stats.sortino(returns))
            if math.isfinite(sortino):
                out.append(("Sortino (qs)", _fmt(sortino), "pos" if sortino > 0 else "neg"))
        except Exception:
            pass
        try:
            mdd = float(qs.stats.max_drawdown(eq))
            if math.isfinite(mdd):
                out.append(("Max Drawdown (qs)", f"{_fmt(mdd * 100.0)}%", "neg" if mdd < 0 else ""))
        except Exception:
            pass
        return out
    except Exception:
        return []


# ── SVG charts (dependency-free) ─────────────────────────────────────────────
def _svg_line(values, color, fill, width=720, height=180, baseline=None):
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if baseline is not None:
        lo = min(lo, baseline)
        hi = max(hi, baseline)
    span = (hi - lo) or 1.0
    n = len(values)
    dx = width / max(n - 1, 1)
    pad = 8

    def y(v):
        return pad + (height - 2 * pad) * (1 - (v - lo) / span)

    pts = " ".join(f"{i * dx:.1f},{y(v):.1f}" for i, v in enumerate(values))
    base_y = y(baseline) if baseline is not None else height - pad
    area = f"0,{base_y:.1f} " + pts + f" {(n - 1) * dx:.1f},{base_y:.1f}"
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'preserveAspectRatio="none" style="display:block">'
        f'<polygon points="{area}" fill="{fill}" />'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" />'
        f'</svg>'
    )


def _equity_section(curve) -> str:
    equities = [p["equity"] for p in curve]
    dds = [p["drawdown"] * 100.0 for p in curve]
    eq_svg = _svg_line(equities, _ACCENT, "rgba(88,166,255,0.15)")
    dd_svg = _svg_line(dds, _RED, "rgba(248,81,73,0.18)", height=120, baseline=0.0)
    return (
        f'<div class="panel"><h2>Equity Curve</h2>'
        f'<div class="axis"><span>{_fmt(min(equities))}</span>'
        f'<span>{_fmt(max(equities))}</span></div>{eq_svg}</div>'
        f'<div class="panel"><h2>Drawdown (Underwater)</h2>'
        f'<div class="axis"><span>{_fmt(min(dds))}%</span><span>0%</span></div>{dd_svg}</div>'
    )


def _heatmap_section(trades) -> str:
    mp = monthly_pnl(trades)
    if not mp:
        return ('<div class="panel"><h2>Monthly P&amp;L</h2>'
                '<p class="muted">No dated trades to chart.</p></div>')
    years = sorted({int(k[:4]) for k in mp})
    mags = [abs(v) for v in mp.values() if v]
    mx = max(mags) if mags else 1.0

    def cell(year, month):
        v = mp.get(f"{year:04d}-{month:02d}")
        if v is None:
            return '<td class="empty"></td>'
        alpha = min(abs(v) / mx, 1.0) * 0.85 + 0.12 if mx else 0.2
        if v > 0:
            bg = f"rgba(38,166,65,{alpha:.2f})"
        elif v < 0:
            bg = f"rgba(248,81,73,{alpha:.2f})"
        else:
            bg = "transparent"
        return f'<td style="background:{bg}">{_fmt(v, 0)}</td>'

    head = "".join(f"<th>{m}</th>" for m in _MONTHS)
    body = ""
    for y in years:
        row = "".join(cell(y, m) for m in range(1, 13))
        total = sum(mp.get(f"{y:04d}-{m:02d}", 0.0) for m in range(1, 13))
        cls = "pos" if total > 0 else ("neg" if total < 0 else "")
        body += (f"<tr><th>{y}</th>{row}"
                 f'<td class="total {cls}">{_fmt(total, 0)}</td></tr>')
    return (
        '<div class="panel"><h2>Monthly P&amp;L Heatmap</h2>'
        '<table class="heat"><thead><tr><th></th>' + head +
        '<th>Total</th></tr></thead><tbody>' + body + '</tbody></table></div>'
    )


def _stats_section(rows) -> str:
    cells = ""
    for label, value, sign in rows:
        cls = f"val {sign}" if sign else "val"
        cells += (f'<div class="stat"><span class="lbl">{label}</span>'
                  f'<span class="{cls}">{value}</span></div>')
    return f'<div class="panel"><h2>Summary</h2><div class="stats">{cells}</div></div>'


_CSS = f"""
* {{ box-sizing: border-box; }}
body {{ margin:0; padding:28px; background:{_BG}; color:{_FG};
  font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
h1 {{ font-size:22px; margin:0 0 4px; letter-spacing:.3px; }}
h2 {{ font-size:14px; color:{_MUTED}; text-transform:uppercase;
  letter-spacing:1px; margin:0 0 14px; font-weight:600; }}
.sub {{ color:{_MUTED}; font-size:12px; margin:0 0 22px; }}
.panel {{ background:{_PANEL}; border:1px solid {_BORDER}; border-radius:10px;
  padding:18px 20px; margin-bottom:20px; }}
.stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
.stat {{ display:flex; flex-direction:column; gap:4px; padding:12px;
  background:{_BG}; border:1px solid {_BORDER}; border-radius:8px; }}
.lbl {{ color:{_MUTED}; font-size:11px; text-transform:uppercase; letter-spacing:.5px; }}
.val {{ font-size:20px; font-weight:700; }}
.val.pos, .total.pos {{ color:{_GREEN}; }}
.val.neg, .total.neg {{ color:{_RED}; }}
.axis {{ display:flex; justify-content:space-between; color:{_MUTED};
  font-size:11px; margin-bottom:6px; }}
table.heat {{ border-collapse:collapse; width:100%; font-size:12px; }}
table.heat th {{ color:{_MUTED}; font-weight:600; padding:6px 8px; text-align:center; }}
table.heat td {{ padding:8px 6px; text-align:center; border:1px solid {_BORDER};
  border-radius:4px; min-width:42px; color:{_FG}; }}
table.heat td.empty {{ background:{_BG}; color:{_MUTED}; }}
table.heat td.total {{ font-weight:700; background:{_BG}; }}
.muted {{ color:{_MUTED}; }}
.empty-state {{ text-align:center; padding:80px 20px; }}
.empty-state .big {{ font-size:48px; margin-bottom:12px; }}
footer {{ color:{_MUTED}; font-size:11px; text-align:center; margin-top:8px; }}
"""


def _page(title: str, body: str) -> str:
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{title}</title><style>{_CSS}</style></head>'
        f'<body>{body}'
        f'<footer>ML-Network-Brain · Trade Journal · '
        f'generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</footer>'
        f'</body></html>'
    )


def render_tearsheet(trades, *, title: str = "Trade Journal Tearsheet",
                     starting_equity: float = 100000.0) -> str:
    """Self-contained dark-theme HTML tearsheet. Never raises."""
    trades = list(trades or [])
    if not trades:
        body = (
            f'<h1>{title}</h1>'
            '<div class="panel empty-state">'
            '<div class="big">📭</div>'
            '<h2>No trades yet</h2>'
            '<p class="muted">Record some closed trades and your equity curve, '
            'drawdown and monthly P&amp;L will appear here.</p></div>'
        )
        return _page(title, body)

    stats = _summary_stats(trades, starting_equity)
    stats += _quantstats_rows(trades, starting_equity)
    curve = equity_curve(trades, starting_equity)

    body = (
        f'<h1>{title}</h1>'
        f'<p class="sub">{len(trades)} closed trades · starting equity '
        f'{_fmt(starting_equity)} · ending equity {_fmt(curve[-1]["equity"])}</p>'
        + _stats_section(stats)
        + _equity_section(curve)
        + _heatmap_section(trades)
    )
    return _page(title, body)


def render_tearsheet_pdf(trades, path: str, **kw) -> str:
    """Render the HTML tearsheet and write it to `path` as PDF via weasyprint."""
    html = render_tearsheet(trades, **kw)
    import weasyprint
    weasyprint.HTML(string=html).write_pdf(path)
    return path
