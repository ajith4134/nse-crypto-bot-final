"""trading/journal/schema.py — 85+ column closed-trade record (T5 §3, blueprint §5).

The single canonical schema for a CLOSED trade, covering NSE equity/F&O and crypto
spot/perp. `ClosedTrade` is a dataclass with every field from blueprint Section 5,
grouped exactly as documented. `COLUMNS` is the canonical ordered list of column keys
(the dashboard's Closed Trades table and CSV export both use it), so the column set
has ONE source of truth.

All fields default to None/0/"" so a partially-known trade still serialises cleanly;
the journal fills derived fields (charges, quality metrics) after construction. JSON
list fields (partial_exits, node_contributions, tags) are kept as Python objects and
serialised by `to_dict`. Pure data — no I/O, no computation here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields


@dataclass
class ClosedTrade:
    # ── Identity & Classification ───────────────────────────────────────────────
    trade_id: str = ""
    entry_order_id: str = ""
    exit_order_id: str = ""
    symbol: str = ""
    exchange: str = ""                      # NSE/BSE/MCX/NFO/Binance/Bybit
    instrument_type: str = ""              # EQ/CE/PE/FUT/PERP/QUARTERLY/SPOT/OPT
    direction: str = ""                    # LONG/SHORT
    product_type: str = ""                 # MIS/CNC/NRML/MTF/MARGIN/CROSS/ISOLATED
    strategy_name: str = ""
    setup_type: str = ""                   # Breakout/Reversal/Momentum/Scalp/Swing/Hedge
    market_session: str = ""
    broker_used: str = ""

    # ── F&O / Options Specific ──────────────────────────────────────────────────
    underlying_symbol: str = ""
    underlying_price_entry: float | None = None
    underlying_price_exit: float | None = None
    expiry_date: str = ""
    strike_price: float | None = None
    option_type: str = ""                  # CE/PE
    lot_size: int = 1
    num_lots: float | None = None

    # ── Execution Data ──────────────────────────────────────────────────────────
    entry_datetime: str = ""               # ISO ms precision
    exit_datetime: str = ""
    quantity: float = 0.0                  # absolute base/share/contract qty
    entry_price: float = 0.0
    exit_price: float = 0.0
    entry_order_type: str = ""
    exit_order_type: str = ""
    intended_entry_price: float | None = None
    intended_exit_price: float | None = None
    entry_slippage: float | None = None
    exit_slippage: float | None = None
    partial_exits: list = field(default_factory=list)  # [{price, qty, time, reason}]

    # ── P&L (Gross → Net) ───────────────────────────────────────────────────────
    gross_pnl: float = 0.0
    stt: float = 0.0
    exchange_txn_charges: float = 0.0
    brokerage: float = 0.0
    gst: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    other_charges: float = 0.0
    total_charges: float = 0.0
    net_pnl: float = 0.0
    net_pnl_pct: float | None = None
    mtf_interest: float = 0.0
    funding_pnl: float = 0.0               # crypto perp funding collected/paid
    maker_taker_fee: float = 0.0           # crypto exchange fee
    net_pnl_crypto: float | None = None    # after fees + funding

    # ── Risk & Sizing ───────────────────────────────────────────────────────────
    margin_used: float | None = None
    leverage: float | None = None
    margin_mode: str = ""                  # Cross/Isolated
    capital_at_risk: float | None = None   # initial SL distance × qty
    risk_pct_portfolio: float | None = None
    initial_sl_price: float | None = None
    initial_target_price: float | None = None
    risk_reward: float | None = None
    kelly_fraction: float | None = None
    portfolio_heat_entry: float | None = None
    trailing_sl_triggered: bool | None = None
    profit_lock_triggered: bool | None = None

    # ── Trade Quality Metrics ───────────────────────────────────────────────────
    mae: float | None = None               # ₹/$ adverse excursion (positive)
    mae_time: str = ""
    mae_pct: float | None = None
    mfe: float | None = None               # ₹/$ favourable excursion
    mfe_time: str = ""
    mfe_pct: float | None = None
    entry_efficiency: float | None = None  # %
    exit_efficiency: float | None = None   # %
    r_multiple: float | None = None        # net P&L / initial risk
    holding_duration: str = ""             # HH:MM:SS
    day_of_week: str = ""
    entry_hour: int | None = None

    # ── Market Context at Entry ─────────────────────────────────────────────────
    india_vix_entry: float | None = None
    nifty_level_entry: float | None = None
    market_regime_entry: str = ""          # Trending/Ranging/Volatile/Crash
    regime_confidence: float | None = None
    volume_entry: float | None = None
    relative_volume: float | None = None
    oi_entry: float | None = None
    oi_change_pct: float | None = None
    fear_greed_index: float | None = None
    btc_price_entry: float | None = None
    funding_rate_entry: float | None = None
    long_short_ratio_entry: float | None = None

    # ── Broker-app market context (discovered by the App Driving School from the broker's OWN
    #    pages — real fields the apps surface that we now snapshot at entry) ──────────────────
    mark_price_entry: float | None = None       # perp mark price (funding/liquidation ref) — crypto
    index_price_entry: float | None = None       # spot index behind the perp — crypto
    funding_interval_hours: float | None = None  # hours between funding payments — crypto
    turnover_24h_entry: float | None = None      # 24h traded value (both markets)
    high_24h_entry: float | None = None          # 24h / day high
    low_24h_entry: float | None = None           # 24h / day low

    # ── Profit Tailgating (adaptive ratchet that LOCKS profit as it climbs, tailgating the peak) ──
    tailgate_locked_profit_pct: float | None = None  # profit% currently LOCKED — ratchets UP with the
    #                                                  peak, never down; exit fires if profit hits it
    tailgate_distance_pct: float | None = None   # trailing distance from peak the tailgate used
    tailgate_peak_profit_pct: float | None = None  # the peak profit% the trade reached
    tailgate_triggered: bool | None = None       # did the tailgate lock the exit? (vs stop/target)
    tailgate_captured_pct: float | None = None   # profit% actually locked vs the peak (efficiency)

    # ── Options Greeks at Entry/Exit ────────────────────────────────────────────
    iv_entry: float | None = None
    iv_exit: float | None = None
    iv_rank_entry: float | None = None
    iv_percentile_entry: float | None = None
    delta_entry: float | None = None
    gamma_entry: float | None = None
    theta_entry: float | None = None
    vega_entry: float | None = None
    rho_entry: float | None = None
    delta_exit: float | None = None
    total_theta_collected: float | None = None

    # ── Brain / AI Metadata ─────────────────────────────────────────────────────
    brain_confidence_entry: float | None = None
    brain_prediction: str = ""             # UP/DOWN/NEUTRAL
    brain_correct: bool | None = None
    node_contributions: list = field(default_factory=list)  # JSON
    signal_source: str = ""

    # ── Calibrated uncertainty at entry (Pillar 17; trading/uq/conformal.py) ────
    p_up: float | None = None              # conformal P(trade nets > 0)
    interval_width: float | None = None    # coverage-guaranteed return-interval width (%)
    self_uncertainty: float | None = None  # ensemble vote entropy ∈ [0, 1]
    abstain_reason: str = ""               # non-empty when the UQ gate downgraded (e.g. half-size)

    # ── Trader Psychology at Entry (order-book depth; trading/brain/psychology.py) ──
    trader_psychology: float | None = None  # composite crowd score ∈ [-1, 1]
    psych_label: str = ""                   # capitulation…euphoric
    psych_obi: float | None = None          # book imbalance (top levels)
    psych_ofi: float | None = None          # order flow imbalance
    psych_microprice_drift_bps: float | None = None  # Stoikov microprice − mid
    psych_spread_bps: float | None = None
    psych_depth_slope_bias: float | None = None
    psych_wall_bias: float | None = None    # whale-wall support/resistance bias
    psych_fear: float | None = None         # spread/λ/VPIN fear component ∈ [0, 1]
    psych_vpin: float | None = None         # toxic-flow probability
    psych_deeplob_prob_up: float | None = None  # DeepLOB P(up) from depth sequence

    # ── Full decision context (ALL data the brain considered at entry) ──────────
    decision_snapshot: dict = field(default_factory=dict)  # JSON

    # ── Decision memory (episodic provenance; trading/brain/decision_memory.py) ──
    episode_id: str = ""                    # links journal row → decision-memory episode
    feature_attribution: dict = field(default_factory=dict)  # JSON: SHAP top drivers
    exit_reflection: str = ""               # 2-4 sentence lesson written at close

    # ── Trade Behavior Flags ────────────────────────────────────────────────────
    revenge_trade_flag: bool = False
    overtrading_flag: bool = False
    scaled_in: bool | None = None
    scaled_out: bool | None = None
    rollover: bool | None = None
    corporate_action_impact: str = ""

    # ── User Annotations ────────────────────────────────────────────────────────
    notes: str = ""
    tags: list = field(default_factory=list)
    mistake_type: str = ""                 # FOMO/Early exit/Late entry/No SL/Sized too big
    lesson_learned: str = ""
    rating: int | None = None              # 1–5 stars

    # ── serialisation ───────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return asdict(self)

    def to_row(self) -> list:
        """Values in canonical COLUMNS order, JSON-encoding list/dict cells for CSV."""
        d = self.to_dict()
        out = []
        for c in COLUMNS:
            v = d.get(c)
            out.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "ClosedTrade":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


# Canonical ordered column list — single source of truth for table + CSV export.
COLUMNS: list[str] = [f.name for f in fields(ClosedTrade)]


def csv_header() -> str:
    return ",".join(COLUMNS)
