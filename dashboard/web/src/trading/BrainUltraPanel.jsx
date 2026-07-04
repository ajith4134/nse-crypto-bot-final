// BrainUltraPanel.jsx — "🧠 Brain Ultra (memory · micro-LLM · perception · continual)"
// Surfaces trading/brain/ultra.py (Phases A–E, 2026-07-02): HippoRAG+A-MEM associative
// memory, Claude-style file memory (brain_memory/), the cloned nanoGPT/llama2.c micro-LLM,
// Docling/Surya perception, Avalanche continual learning and gpt-researcher deep research.
// HONEST wiring: every value comes from GET /api/trading/brain/ultra; the recall box runs a
// REAL PPR recall (?q=) and the remember form POSTs a REAL note then re-reads state.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function Card({ title, hint, children, span }) {
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10,
                  padding: 12, gridColumn: span ? `span ${span}` : undefined,
                  boxSizing: 'border-box', minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: T.text, letterSpacing: 0.3 }}>{title}</span>
        {hint && <span style={{ color: T.muted, fontSize: 11 }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}
function Badge({ text, color }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color,
                   border: `1px solid ${color}`, borderRadius: 4, padding: '1px 6px',
                   textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{text}</span>
  )
}
function KV({ k, v, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12,
                  padding: '2px 0' }}>
      <span style={{ color: T.muted }}>{k}</span>
      <span style={{ color: color || T.text, textAlign: 'right' }}>{String(v)}</span>
    </div>
  )
}

export default function BrainUltraPanel() {
  const [st, setSt] = useState(null)
  const [err, setErr] = useState(null)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const [note, setNote] = useState({ name: '', body: '' })
  const [saved, setSaved] = useState(null)

  const refresh = () => getJSON('/api/trading/brain/ultra')
    .then(d => { setSt(d); setErr(d.available ? null : d.error) })
    .catch(e => setErr(String(e)))
  useEffect(() => { refresh(); const t = setInterval(refresh, 12000); return () => clearInterval(t) }, [])

  const doRecall = () => {
    if (!q.trim()) return
    getJSON(`/api/trading/brain/ultra?q=${encodeURIComponent(q)}`)
      .then(d => setHits(d.hits || [])).catch(e => setErr(String(e)))
  }
  const doRemember = async () => {
    if (!note.name.trim() || !note.body.trim()) return
    const r = await fetch('/api/trading/brain/ultra/remember', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: note.name, description: note.body.slice(0, 80),
                             body: note.body, type: 'lesson' }),
    })
    const d = await r.json()
    setSaved(d.ok ? d.name : `error: ${d.error}`)
    setNote({ name: '', body: '' })
    refresh()                                   // round-trip: re-read real state
  }

  const inp = { background: T.bg, color: T.text, border: `1px solid ${T.border}`,
                borderRadius: 6, padding: '5px 8px', fontSize: 12, minWidth: 0 }
  const fm = st?.file_memory, assoc = st?.associative, ml = st?.micro_llm
  const perc = st?.perception, cont = st?.continual, res = st?.researcher

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
      <Card title="🧠 Brain Ultra" hint="HippoRAG+A-MEM · nanoGPT/llama2.c · Docling · Avalanche" span={3}>
        {err && <div style={{ color: T.bad, fontSize: 12 }}>{err}</div>}
        {!st && !err && <div style={{ color: T.muted, fontSize: 12 }}>loading…</div>}
      </Card>

      <Card title="Associative memory" hint="PPR multi-hop recall + note evolution">
        {assoc && <>
          <KV k="notes" v={assoc.notes} />
          <KV k="links" v={assoc.links} />
          <KV k="graph nodes / edges" v={`${assoc.graph?.nodes ?? '—'} / ${assoc.graph?.edges ?? '—'}`} />
          <KV k="LLM extraction" v={assoc.llm ? 'active' : 'heuristic'} color={assoc.llm ? T.good : T.warn} />
          <KV k="persisted" v={assoc.persisted ? 'yes' : 'no'} color={assoc.persisted ? T.good : T.warn} />
        </>}
      </Card>

      <Card title="File memory (brain_memory/)" hint="Claude-style one-fact-per-file">
        {fm && <>
          <KV k="notes" v={fm.notes} />
          <KV k="by type" v={Object.entries(fm.by_type || {}).map(([k, v]) => `${k}:${v}`).join(' ') || '—'} />
          <KV k="index" v={fm.index ? 'MEMORY.md' : 'missing'} color={fm.index ? T.good : T.bad} />
        </>}
        <div style={{ display: 'grid', gap: 6, marginTop: 8 }}>
          <input style={inp} placeholder="note name" value={note.name}
                 onChange={e => setNote({ ...note, name: e.target.value })} />
          <textarea style={{ ...inp, minHeight: 40 }} placeholder="the fact / lesson to remember"
                    value={note.body} onChange={e => setNote({ ...note, body: e.target.value })} />
          <button onClick={doRemember}
                  style={{ ...inp, cursor: 'pointer', fontWeight: 600 }}>remember</button>
          {saved && <span style={{ color: T.good, fontSize: 11 }}>saved: {saved}</span>}
        </div>
      </Card>

      <Card title="Micro-LLM (cloned)" hint="nanoGPT node + llama2.c C kernel">
        {ml && <>
          <KV k="node" v="micro_llm (NodeProtocol)" />
          <KV k="C kernel built" v={ml.c_kernel_built ? 'yes (run.c)' : 'no'}
              color={ml.c_kernel_built ? T.good : T.warn} />
          <KV k="trained this session" v={ml.trained ? 'yes' : 'not yet'}
              color={ml.trained ? T.good : T.muted} />
          {ml.last_losses?.length > 0 && <KV k="last losses" v={ml.last_losses.map(x => Number(x).toFixed(3)).join(' ')} />}
        </>}
      </Card>

      <Card title="Perception" hint="read any doc/image → memory">
        {perc && <>
          <KV k="docling" v={perc.docling ? 'installed' : 'missing'} color={perc.docling ? T.good : T.bad} />
          <KV k="surya OCR" v={perc.surya_ocr ? 'installed' : 'missing'} color={perc.surya_ocr ? T.good : T.bad} />
          <KV k="plain formats" v={(perc.plain_formats || []).join(' ')} />
        </>}
      </Card>

      <Card title="Continual learning" hint="no catastrophic forgetting">
        {cont && <>
          <KV k="engine" v={cont.engine || cont.error} color={cont.engine ? T.good : T.bad} />
          <KV k="world-model" v={cont.worldmodel_online ? 'online replay update' : '—'} />
        </>}
        {res && <KV k="deep research" v={res.deep_engine ? 'gpt-researcher + reflexion' : '—'} />}
      </Card>

      <Card title="Associative recall (live)" hint="query → PPR spreads to related old memories" span={3}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
          <input style={{ ...inp, flex: 1 }} placeholder="e.g. bitcoin funding leverage"
                 value={q} onChange={e => setQ(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && doRecall()} />
          <button onClick={doRecall} style={{ ...inp, cursor: 'pointer', fontWeight: 600 }}>recall</button>
        </div>
        {hits === null
          ? <div style={{ color: T.muted, fontSize: 12 }}>type a topic — the brain recalls associated memories</div>
          : hits.length === 0
            ? <div style={{ color: T.muted, fontSize: 12 }}>no associated memories yet</div>
            : hits.map((h, i) => (
              <div key={i} style={{ borderTop: `1px solid ${T.border}`, padding: '6px 0',
                                    display: 'flex', gap: 8, alignItems: 'baseline' }}>
                <Badge text={(h.score ?? 0).toFixed ? Number(h.score).toFixed(3) : h.score} color={T.accent || T.good} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: T.text, fontWeight: 600 }}>{h.title}</div>
                  <div style={{ fontSize: 11, color: T.muted }}>{h.snippet}</div>
                </div>
              </div>))}
      </Card>
    </div>
  )
}
