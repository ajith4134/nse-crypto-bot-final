// ConceptSpacePanel.jsx — "🧬 Concept Discovery (idea-discovery mode)"
// The net invents its own market features (self-supervised encoder → sparse-autoencoder
// probe → LLM naming), and this panel SHOWS them: a concept-space manifold (perception
// collapsing into concept clusters, like the video) + the discovered-feature list with the
// two lanes (experiment=ungated / validated=proof-gated). Real data from
// /api/trading/brain/discovery; "Discover" POSTs /run over real Binance candles.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function postJSON(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }

const CLUSTER_COLORS = ['#4da3ff', '#2ec27e', '#ffb454', '#c56cff', '#ff7a9c', '#57d1c9', '#e0e068', '#ff9351']
const clusterColor = (c) => (c == null || c < 0 ? T.muted : CLUSTER_COLORS[c % CLUSTER_COLORS.length])

function LaneBadge({ lane }) {
  const c = lane === 'validated' ? T.good : T.accent
  return <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.4, color: c,
    border: `1px solid ${c}`, borderRadius: 4, padding: '1px 5px' }}>{lane === 'validated' ? 'VALIDATED' : 'EXPERIMENT'}</span>
}

// The concept manifold: normalized [0,1] points colored by concept cluster.
function Manifold({ manifold }) {
  const pts = manifold?.points || []
  const S = 220
  return (
    <div style={{ position: 'relative', width: S, height: S, background: T.panel2,
                  border: `1px solid ${T.gridline}`, borderRadius: 6, flexShrink: 0 }}>
      {pts.map((p) => (
        <div key={p.idx} title={`cluster ${p.cluster}`} style={{ position: 'absolute',
          left: `${p.x * (S - 6)}px`, top: `${(1 - p.y) * (S - 6)}px`, width: 4, height: 4,
          borderRadius: 4, background: clusterColor(p.cluster), opacity: 0.8 }} />
      ))}
      <span style={{ position: 'absolute', left: 6, bottom: 4, fontSize: 9, color: T.muted }}>
        {manifold?.n_clusters ?? 0} concept clusters · {pts.length} windows
      </span>
    </div>
  )
}

function FeatureRow({ f }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ width: 42, fontSize: 10, color: T.muted, fontFamily: 'monospace' }}>#{f.id}</span>
      <span style={{ flex: 1, fontSize: 12, color: T.text, minWidth: 0, overflow: 'hidden',
                     textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.description}>{f.name}</span>
      <LaneBadge lane={f.lane} />
      <span style={{ width: 58, fontSize: 10, color: T.muted, textAlign: 'right' }}
            title="activation rate">{num(f.activation_rate) == null ? '—' : `${Math.round(f.activation_rate * 100)}%`}</span>
      <span style={{ width: 54, fontSize: 10, textAlign: 'right',
                     color: Math.abs(num(f.gate_score) || 0) > 0.08 ? T.good : T.muted }}
            title="validation gate score (OOS fwd-return corr)">{num(f.gate_score) == null ? '—' : f.gate_score.toFixed(2)}</span>
    </div>
  )
}

export default function ConceptSpacePanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => getJSON('/api/trading/brain/discovery')
    .then((d) => { setData(d); setErr(null) }).catch((e) => setErr(String(e.message || e)))
  useEffect(() => { load(); const id = setInterval(load, 8000); return () => clearInterval(id) }, [])

  const discover = async () => {
    setBusy(true)
    try { await postJSON('/api/trading/brain/discovery/run', { symbol: 'BTCUSDT', interval: '1h', use_llm: false }); await load() }
    catch (e) { setErr(String(e.message || e)) }
    finally { setBusy(false) }
  }

  const feats = data?.features || []
  const st = data?.stats || {}

  return (
    <div style={{ background: T.panel, border: `1px solid ${T.gridline}`, borderRadius: 8, padding: 12,
                  display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>🧬 Concept Discovery</span>
        <button onClick={discover} disabled={busy} style={{ fontSize: 11, fontWeight: 700,
          color: busy ? T.muted : T.bg, background: busy ? T.gridline : T.accent, border: 'none',
          borderRadius: 5, padding: '4px 10px', cursor: busy ? 'default' : 'pointer' }}>
          {busy ? 'discovering…' : 'Discover ▸'}
        </button>
      </div>

      <div style={{ fontSize: 10, color: T.muted }}>
        net invents its own features → probe → name → manifold ·
        {st.encoder ? ` encoder=${st.encoder}` : ''}{st.sae ? ' · SAE' : ''}
        {data?.symbol ? ` · ${data.symbol} ${data.interval || ''}` : ''}
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <Manifold manifold={data?.manifold} />
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', gap: 16, marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: T.muted }}>features <b style={{ color: T.text }}>{feats.length}</b></span>
            <span style={{ fontSize: 11, color: T.accent }}>experiment <b>{st.n_experiment ?? 0}</b></span>
            <span style={{ fontSize: 11, color: T.good }}>validated <b>{st.n_validated ?? 0}</b></span>
          </div>
          {err && <div style={{ color: T.bad, fontSize: 11 }}>error: {err}</div>}
          {!err && feats.length === 0 &&
            <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>
              no concepts yet — press <b>Discover</b> to invent features from live BTC candles.
            </div>}
          <div style={{ overflowY: 'auto', maxHeight: 190 }}>
            {feats.map((f) => <FeatureRow key={f.id} f={f} />)}
          </div>
        </div>
      </div>
    </div>
  )
}
