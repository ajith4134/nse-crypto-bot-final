import React, { useEffect, useRef, useState } from 'react'

// P4.2 → ULTRA (2026-07-04) — Stream of Mind. Two real feeds in one panel:
//  • think-cycle thoughts (AG-UI, via the `thoughts` prop) — ephemeral: pulse, fade, expire.
//  • the brain-wide MIND EVENT BUS (GET /api/brain/mind/events, trading/brain/mind_events.py)
//    — typed, durable events from the REAL subsystems: problems in the loop, discoveries
//    ("found a profitable edge"), trade credit on open/close, online research, boss-directive
//    progress ("target 50 → 23 open"), learning cycles and R&D inventions. Polled
//    incrementally (?since=id); honest wiring — only renders what the bus actually holds.

const TTL_MS = 18000      // ephemeral thoughts: total lifetime before removal
const FADE_LEAD_MS = 2000 // start the opacity fade this long before removal
const POLL_MS = 5000
const MAX_EVENTS = 80

const KIND_META = {
  problem:      { icon: '⚠',  label: 'problem' },
  discovery:    { icon: '◆',  label: 'discovery' },
  trade_credit: { icon: '₿',  label: 'trade' },
  research:     { icon: '🔎', label: 'research' },
  directive:    { icon: '🎯', label: 'directive' },
  learning:     { icon: '📈', label: 'learning' },
  invention:    { icon: '💡', label: 'invention' },
  boss:         { icon: '👑', label: 'boss' },
  thought:      { icon: '·',  label: 'thought' },
}

function fmtTime(ts) {
  try {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

export default function StreamOfMind({ thoughts = [] }) {
  const [fading, setFading] = useState({})   // id -> true once fade has started
  const [expired, setExpired] = useState({}) // id -> true once it should be gone
  const [events, setEvents] = useState([])   // mind-bus events, newest first
  const [open, setOpen] = useState({})       // event id -> detail expanded
  const timers = useRef([])
  const seen = useRef(new Set())
  const lastId = useRef(0)

  // Schedule fade + removal for any newly-arrived ephemeral thought.
  useEffect(() => {
    thoughts.forEach((t) => {
      if (!t || seen.current.has(t.id)) return
      seen.current.add(t.id)
      const age = Date.now() - (t.ts || Date.now())
      const fadeIn = Math.max(0, TTL_MS - FADE_LEAD_MS - age)
      const goneIn = Math.max(0, TTL_MS - age)
      timers.current.push(setTimeout(() => {
        setFading((f) => ({ ...f, [t.id]: true }))
      }, fadeIn))
      timers.current.push(setTimeout(() => {
        setExpired((e) => ({ ...e, [t.id]: true }))
      }, goneIn))
    })
  }, [thoughts])

  // Poll the real mind-event bus incrementally.
  useEffect(() => {
    let alive = true
    const poll = async () => {
      try {
        const r = await fetch(`/api/brain/mind/events?since=${lastId.current}`)
        const j = await r.json()
        const evs = Array.isArray(j.events) ? j.events : []
        if (alive && evs.length > 0) {
          lastId.current = Math.max(lastId.current, ...evs.map((e) => e.id || 0))
          setEvents((cur) => {
            const known = new Set(cur.map((e) => e.id))
            const fresh = evs.filter((e) => !known.has(e.id))
            return [...fresh.reverse(), ...cur].slice(0, MAX_EVENTS)
          })
        }
      } catch { /* dashboard offline — keep whatever we have */ }
    }
    poll()
    const t = setInterval(poll, POLL_MS)
    return () => { alive = false; clearInterval(t) }
  }, [])

  // Clean up every pending timer on unmount.
  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const visible = thoughts.filter((t) => t && !expired[t.id])

  return (
    <div className="mind-feed">
      {visible.map((t) => (
        <div key={`th-${t.id}`} className={`mind-entry${fading[t.id] ? ' fade' : ' arrive'}`}>
          <span className="mind-spark" aria-hidden="true" />
          <span className="mind-text">{t.text}</span>
        </div>
      ))}
      {events.length === 0 && visible.length === 0 ? (
        <div className="mind-idle">… idle …</div>
      ) : (
        events.map((e) => {
          const meta = KIND_META[e.kind] || KIND_META.thought
          const salient = (e.salience || 0) >= 0.75
          return (
            <div
              key={`ev-${e.id}`}
              className={`mind-event kind-${e.kind}${salient ? ' salient' : ''}`}
              onClick={() => e.detail && setOpen((o) => ({ ...o, [e.id]: !o[e.id] }))}
              title={e.detail ? 'click for detail' : undefined}
            >
              <span className={`mind-badge kind-${e.kind}`}>{meta.icon} {meta.label}</span>
              <span className="mind-text">{e.text}</span>
              <span className="mind-when">{fmtTime(e.ts)}</span>
              {open[e.id] && e.detail && <div className="mind-detail">{e.detail}</div>}
            </div>
          )
        })
      )}
    </div>
  )
}
