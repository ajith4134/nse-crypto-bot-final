import React, { useEffect, useRef, useState } from 'react'

// P4.2 — Stream of Mind. The brain's live "state of mind": a vertical feed of
// thought entries, NEWEST AT TOP. Each entry pulses on arrival, then fades
// (CSS opacity transition) and is removed after a TTL. Timers are cleaned up
// on unmount. Driven by a `thoughts` prop = [{id, text, ts}, ...].

const TTL_MS = 18000      // total lifetime before removal
const FADE_LEAD_MS = 2000 // start the opacity fade this long before removal

export default function StreamOfMind({ thoughts = [] }) {
  const [fading, setFading] = useState({})   // id -> true once fade has started
  const [expired, setExpired] = useState({}) // id -> true once it should be gone
  const timers = useRef([])
  const seen = useRef(new Set())

  // Schedule fade + removal for any newly-arrived thought.
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

  // Clean up every pending timer on unmount.
  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const visible = thoughts.filter((t) => t && !expired[t.id])

  return (
    <div className="mind-feed">
      {visible.length === 0 ? (
        <div className="mind-idle">… idle …</div>
      ) : (
        visible.map((t) => (
          <div key={t.id} className={`mind-entry${fading[t.id] ? ' fade' : ' arrive'}`}>
            <span className="mind-spark" aria-hidden="true" />
            <span className="mind-text">{t.text}</span>
          </div>
        ))
      )}
    </div>
  )
}
