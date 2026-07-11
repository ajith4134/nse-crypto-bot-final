// BinanceEdgePanel.jsx — "🟡 Binance Edge (compute-offload)"
// Surfaces the data the brain now reads FROM Binance instead of computing locally: the all-market
// WS mirror status, top movers (Binance-pushed), funding extremes, recent liquidations, and live
// listing catalysts. Honest wiring: reads /api/trading/binance, a STATE-FILE-ONLY route the funnel
// process refreshes every ~10s (no sockets in the request thread). Self-contained; polls ~5s.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = Number(v); return Number.isFinite(n) ? n : null }
function fmtVol(v) { const n = num(v); if (n == null) return '—'
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`; if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  return `$${Math.round(n)}` }
function pct(v) { const n = num(v); return n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` }
function fund(v) { const n = num(v); return n == null ? '—' : `${(n * 100).toFixed(4)}%` }
function base(sym) { return String(sym || '').replace(/USDT$|USDC$/, '') }

function Row({ children, gap = 8 }) {
  return <div style={{ display: 'flex', gap, alignItems: 'center', flexWrap: 'wrap' }}>{children}</div>
}
function Chip({ text, color }) {
  return <span style={{ fontSize: 10, fontFamily: 'monospace', color: color || T.text,
    border: `1px solid ${T.gridline}`, borderRadius: 4, padding: '1px 5px', whiteSpace: 'nowrap' }}>{text}</span>
}
function Col({ title, children }) {
  return (
    <div style={{ flex: 1, minWidth: 150, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{title}</span>
      {children}
    </div>
  )
}

export default function BinanceEdgePanel() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const tick = () => getJSON('/api/trading/binance')
      .then((x) => { if (alive) { setD(x); setErr(null) } })
      .catch((e) => { if (alive) setErr(String(e.message || e)) })
    tick(); const id = setInterval(tick, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const st = (d && d.status) || {}
  const connected = !!st.connected
  const topVol = (d && Array.isArray(d.top_volume)) ? d.top_volume : []
  const topGain = (d && Array.isArray(d.top_gainers)) ? d.top_gainers : []
  const fundHi = (d && Array.isArray(d.funding_high)) ? d.funding_high : []
  const fundLo = (d && Array.isArray(d.funding_low)) ? d.funding_low : []
  const liqs = (d && Array.isArray(d.liquidations)) ? d.liquidations : []
  const newList = (d && Array.isArray(d.new_listings)) ? d.new_listings : []
  const anns = (d && Array.isArray(d.announcements)) ? d.announcements : []
  const secHot = (d && Array.isArray(d.sectors_hot)) ? d.sectors_hot : []
  const reg = (d && d.options_regime && d.options_regime.available !== false) ? d.options_regime : null

  return (
    <div style={{ background: T.panel, border: `1px solid ${T.gridline}`, borderRadius: 8,
                  padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <Row>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>🟡 Binance Edge</span>
        <Chip text={connected ? 'MIRROR LIVE' : 'MIRROR DOWN'} color={connected ? T.good : T.bad} />
        <span style={{ fontSize: 10, color: T.muted }}>
          {num(st.symbols_ticker) ?? 0} tick · {num(st.symbols_mark) ?? 0} mark
          {st.last_msg_age_s != null ? ` · ${st.last_msg_age_s}s ago` : ''}
        </span>
        {reg && reg.label && (
          <Chip text={`regime: ${reg.label}${num(reg.btc && reg.btc.atm_iv) != null ? ` · BTC IV ${(reg.btc.atm_iv * 100).toFixed(0)}%` : ''}`}
            color={reg.label === 'risk-off' ? T.bad : reg.label === 'risk-on' ? T.good : T.warn} />
        )}
      </Row>

      {err && <div style={{ color: T.bad, fontSize: 11 }}>error: {err}</div>}
      {d && d.available === false &&
        <div style={{ color: T.muted, fontSize: 12 }}>{d.note || 'no snapshot yet — start the crypto funnel'}</div>}

      {(topVol.length > 0 || topGain.length > 0) && (
        <Row gap={16}>
          <Col title="Top volume (pushed)">
            {topVol.slice(0, 6).map((r) => (
              <Row key={r.symbol}><Chip text={base(r.symbol)} />
                <span style={{ fontSize: 11, color: T.muted }}>{fmtVol(r.quote_volume)}</span>
                <span style={{ fontSize: 11, color: num(r.pct_change) >= 0 ? T.good : T.bad }}>{pct(r.pct_change)}</span>
              </Row>
            ))}
          </Col>
          <Col title="Top gainers">
            {topGain.slice(0, 6).map((r) => (
              <Row key={r.symbol}><Chip text={base(r.symbol)} color={T.good} />
                <span style={{ fontSize: 11, color: T.good }}>{pct(r.pct_change)}</span>
              </Row>
            ))}
          </Col>
        </Row>
      )}

      {(fundHi.length > 0 || fundLo.length > 0) && (
        <Row gap={16}>
          <Col title="Funding highest (longs pay)">
            {fundHi.slice(0, 5).map((r) => (
              <Row key={r.symbol}><Chip text={base(r.symbol)} />
                <span style={{ fontSize: 11, color: T.warn }}>{fund(r.funding_rate)}</span></Row>
            ))}
          </Col>
          <Col title="Funding lowest (shorts pay)">
            {fundLo.slice(0, 5).map((r) => (
              <Row key={r.symbol}><Chip text={base(r.symbol)} />
                <span style={{ fontSize: 11, color: T.good }}>{fund(r.funding_rate)}</span></Row>
            ))}
          </Col>
        </Row>
      )}

      <Row gap={16}>
        <Col title={`Liquidations (${liqs.length})`}>
          {liqs.length === 0 && <span style={{ fontSize: 11, color: T.muted }}>none in buffer</span>}
          {liqs.slice(0, 5).map((x, i) => (
            <Row key={i}><Chip text={base(x.symbol)} />
              <span style={{ fontSize: 11, color: x.side === 'SELL' ? T.bad : T.good }}>
                {x.side === 'SELL' ? 'long liq' : 'short liq'}</span>
              <span style={{ fontSize: 10, color: T.muted }}>{fmtVol(num(x.qty) * num(x.price))}</span>
            </Row>
          ))}
        </Col>
        <Col title={`Listing catalysts`}>
          {newList.length === 0 && anns.length === 0 &&
            <span style={{ fontSize: 11, color: T.muted }}>none active</span>}
          {newList.slice(0, 4).map((n) => (
            <Row key={n.raw}><Chip text={base(n.raw)} color={T.good} />
              <span style={{ fontSize: 10, color: T.good }}>NEW · {Math.round((num(n.age_s) || 0) / 3600)}h</span></Row>
          ))}
          {anns.slice(0, 3).map((a, i) => (
            <span key={i} style={{ fontSize: 10, color: T.muted, overflow: 'hidden',
              textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.title}>📣 {a.title}</span>
          ))}
        </Col>
      </Row>

      {secHot.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Sector rotation (Binance-classified)
          </span>
          <Row gap={6}>
            {secHot.map((s) => {
              const up = num(s.avg_pct_change) >= 0
              return <span key={s.sector} style={{ fontSize: 10, fontFamily: 'monospace',
                color: up ? T.good : T.bad, border: `1px solid ${up ? T.good : T.bad}`,
                borderRadius: 4, padding: '1px 6px' }}
                title={`${s.members} coins`}>{s.sector} {pct(s.avg_pct_change)}</span>
            })}
          </Row>
        </div>
      )}
    </div>
  )
}
