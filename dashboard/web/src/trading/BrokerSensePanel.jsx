// BrokerSensePanel.jsx — the Broker-Sense Funnel (Dark Pro UI).
// Honest view of the brain trading THROUGH the broker web apps: their screeners narrow the
// universe (savers A/J), candle screenshots → CNN direction (D/F), screen-mirror bid/ask
// with API fail-safe (G + owner rule 4), hot watchlist TTL (E), adaptive budget (I) —
// APIs execute only. Self-fetching like ComputerUsePanel: GET /api/trading/broker_sense
// every ~8s, POST {op:'run_cycle'} to drive one paper cycle.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const URL_ = '/api/trading/broker_sense'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}

function Btn({ children, onClick, color, disabled }) {
  const c = color || T.accent
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: T.panel2, color: disabled ? T.muted : c,
      border: `1px solid ${disabled ? T.border : c}`, borderRadius: 8, padding: '7px 12px',
      cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 13, fontWeight: 600,
      opacity: disabled ? 0.6 : 1, whiteSpace: 'nowrap' }}>
      {children}
    </button>
  )
}

export default function BrokerSensePanel({ intervalMs = 8000 }) {
  const [market, setMarket] = useState('crypto')
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const alive = useRef(true)

  const refresh = async (m) => {
    try {
      const d = await getJSON(`${URL_}?market=${m || market}`)
      if (alive.current) { setData(d); setErr(null) }
    } catch (e) { if (alive.current) setErr(String(e.message || e)) }
  }

  useEffect(() => {
    alive.current = true; refresh(market)
    const t = setInterval(() => refresh(market), intervalMs)
    return () => { alive.current = false; clearInterval(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, market])

  const runCycle = async () => {
    setBusy(true)
    try {
      const r = await fetch(URL_, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ op: 'run_cycle', market }) })
      const d = await r.json()
      setResult({ ok: d.ok !== false, text: d.ok !== false ? 'cycle started ✓ (paper)' : `✗ ${d.error || ''}` })
    } catch (e) { setResult({ ok: false, text: `✗ ${String(e.message || e)}` }) }
    finally { setBusy(false); setTimeout(() => refresh(market), 1500) }
  }

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
    padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif', boxSizing: 'border-box', width: '100%' }

  if (!data) {
    return (<div style={wrap}><div style={{ color: T.muted, fontSize: 13, padding: '24px 0', textAlign: 'center' }}>
      <span style={{ fontSize: 22, opacity: 0.6 }}>🕶️</span>
      <div style={{ marginTop: 8 }}>{err ? `broker-sense feed: ${err}` : 'loading broker-sense funnel…'}</div>
    </div></div>)
  }

  const last = data.last_cycle || {}
  const st = last.stages || {}
  const sess = data.sessions || {}
  const pend = sess.pending_asks || []
  const cols = data.learning_columns || {}
  const brokers = data.brokers || {}
  const execu = data.execution || {}
  const watch = data.watchlist || {}
  const box = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 12 }
  const cap = { fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }

  return (
    <div style={wrap}>
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🕶️ Broker-Sense Funnel</span>
        <span style={{ fontSize: 11, color: T.muted }}>broker apps screen · vision reads · APIs execute</span>
        <div style={{ flex: 1 }} />
        {['crypto', 'nse'].map((m) => (
          <button key={m} onClick={() => setMarket(m)} style={{
            background: market === m ? T.panel2 : 'transparent', color: market === m ? T.accent : T.muted,
            border: `1px solid ${market === m ? T.accent : T.border}`, borderRadius: 6,
            padding: '3px 10px', fontSize: 11, fontWeight: 700, cursor: 'pointer',
            textTransform: 'uppercase' }}>{m}</button>
        ))}
        {result && <span style={{ fontSize: 11, fontWeight: 700, color: result.ok ? T.good : T.bad,
          border: `1px solid ${result.ok ? T.good : T.bad}`, borderRadius: 4, padding: '2px 8px' }}>{result.text}</span>}
        <span style={{ fontSize: 11, fontWeight: 700, color: T.muted,
          border: `1px solid ${T.border}`, borderRadius: 4, padding: '2px 8px' }}>🔒 paper-first</span>
        {/* NSE data source: selection reads off the paid Zerodha Kite in-RAM mirror. Real numbers only. */}
        {market === 'nse' && data.nse_data && (
          <span title={`Zerodha Kite mirror · ${data.nse_data.mirror?.symbols_ticker ?? 0} symbols streaming · last tick ${data.nse_data.mirror?.last_msg_age_s ?? '—'}s ago · subscribed ${data.nse_data.mirror?.symbols_subscribed ?? 0}`}
            style={{ fontSize: 11, fontWeight: 700,
              color: String(data.nse_data.source).startsWith('in-RAM') ? T.good : T.warn,
              border: `1px solid ${String(data.nse_data.source).startsWith('in-RAM') ? T.good : T.warn}`,
              borderRadius: 4, padding: '2px 8px' }}>
            📡 {data.nse_data.source}
          </span>
        )}
      </div>

      {/* pending credential/OTP asks — surfaced loudly, the owner answers in Brain Chat */}
      {pend.length > 0 && (
        <div style={{ ...box, borderColor: T.warn, marginBottom: 12 }}>
          <div style={{ ...cap, color: T.warn }}>🔐 waiting for you in Brain Chat</div>
          {pend.map((p, i) => (
            <div key={i} style={{ fontSize: 12, color: T.text, padding: '2px 0', whiteSpace: 'pre-wrap' }}>
              {p.note || `${p.site}: ${(p.fields || []).join(', ')}`}
            </div>
          ))}
        </div>
      )}

      {/* the funnel — last cycle stage counts */}
      <div style={{ ...box, marginBottom: 12 }}>
        <div style={cap}>last cycle · {last.segment || '—'} · preset “{st.screen?.preset ?? '—'}”</div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <Stat label="screened (their servers)" value={st.screen?.surfaced ?? '—'} />
          <span style={{ color: T.muted }}>→</span>
          <Stat label="hot shortlist" value={st.heat?.shortlist ?? '—'} color={T.accent} />
          <span style={{ color: T.muted }}>→</span>
          <Stat label="charts read" value={st.look?.read ?? '—'} />
          <Stat label="cache hits" value={st.look?.cache_hits ?? 0} color={T.good} />
          <span style={{ color: T.muted }}>→</span>
          <Stat label="book-verified" value={st.verify?.checked ?? '—'} />
          <Stat label="ocr rejected→api" value={st.verify?.ocr_rejected ?? 0} color={T.warn} />
          <span style={{ color: T.muted }}>→</span>
          <Stat label="entered" value={(st.execute?.entered || []).length} color={T.good} />
          <Stat label="took" value={last.took_s != null ? `${last.took_s}s` : '—'}
            color={last.completed_within_budget === false ? T.bad : T.good} />
          <Stat label="shots deleted" value={last.screenshots_deleted ?? 0} />
        </div>
        {(st.execute?.entered || []).length > 0 && (
          <div style={{ marginTop: 8, fontSize: 11, color: T.good }}>
            opened: {(st.execute.entered || []).join(' · ')}
          </div>
        )}
      </div>

      {/* controls */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <Btn onClick={runCycle} disabled={busy} color={T.accent}>▶ Run one cycle (paper)</Btn>
        <span style={{ fontSize: 11, color: T.muted, alignSelf: 'center' }}>
          budget-bound: shortlist auto-sizes (now {data.shortlist_n ?? '—'}) so every cycle completes
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
        {/* broker roles — the owner's mapping, enforced in code */}
        <div style={box}>
          <div style={cap}>broker roles (enforced in code)</div>
          <div style={{ fontSize: 12, color: T.text, lineHeight: 1.7 }}>
            <div><span style={{ color: T.muted }}>screening:</span> {(brokers.screening || []).join(' · ')}</div>
            <div><span style={{ color: T.muted }}>paper:</span> {execu.paper ? `${execu.paper.nse} · ${execu.paper.crypto}` : '—'}</div>
            <div><span style={{ color: T.muted }}>real (off):</span> {execu.real ? `NSE ${execu.real.nse} · crypto ${execu.real.crypto}` : '—'}</div>
          </div>
        </div>

        {/* sessions — who we're logged into */}
        <div style={box}>
          <div style={cap}>broker sessions</div>
          <div style={{ fontSize: 12, lineHeight: 1.7 }}>
            <div><span style={{ color: T.muted }}>saved logins:</span> {Object.keys(sess.credentials_saved || {}).join(' · ') || 'none yet'}</div>
            <div><span style={{ color: T.muted }}>sessions on disk:</span> {(sess.sessions_on_disk || []).join(' · ') || 'none yet'}</div>
          </div>
          {(sess.recent_events || []).slice(-3).map((e, i) => (
            <div key={i} style={{ fontSize: 11, color: T.muted, marginTop: 4 }}>· {e.msg}</div>
          ))}
        </div>

        {/* discovered learning columns — decision #6 */}
        <div style={box}>
          <div style={cap}>discovered learning columns · {cols.n_columns ?? 0}</div>
          {(cols.columns || []).slice(0, 8).map((c) => (
            <div key={c.name} style={{ display: 'flex', gap: 8, padding: '3px 0', borderBottom: `1px solid ${T.gridline}` }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={c.label}>{c.name}</span>
              <span style={{ fontSize: 11, color: T.muted }}>{c.source}</span>
              <span style={{ fontSize: 11, color: T.accent }}>×{c.n_seen}</span>
            </div>
          ))}
          {!(cols.columns || []).length && <span style={{ fontSize: 12, color: T.muted }}>none yet — cycles discover them from the apps</span>}
        </div>

        {/* hot watchlist — saver E */}
        <div style={box}>
          <div style={cap}>hot watchlist · {watch.n_tracked ?? 0} tracked (TTL {watch.ttl_bars ?? '—'} bars)</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {(watch.hot || []).slice(0, 14).map((s) => (
              <span key={s} style={{ fontSize: 11, fontWeight: 600, color: T.accent,
                border: `1px solid ${T.border}`, borderRadius: 12, padding: '2px 9px' }}>{String(s).split('/')[0]}</span>
            ))}
            {!(watch.hot || []).length && <span style={{ fontSize: 12, color: T.muted }}>empty — run a cycle</span>}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: T.muted, borderTop: `1px solid ${T.gridline}`, marginTop: 12, paddingTop: 8 }}>
        ℹ the brokers' servers scan the whole universe (screener pushdown); vision reads only the hot few;
        every screenshot is deleted after its read; a bad OCR digit is replaced by the API number, never traded.
      </div>
    </div>
  )
}
