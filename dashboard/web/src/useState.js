import { useEffect, useState } from 'react'

// Polls /api/state so any node/metric written by a run appears automatically
// (dashboard-sync). Falls back gracefully when no state has been generated yet.
export function useNetworkState(intervalMs = 4000) {
  const [state, setState] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const r = await fetch('/api/state', { cache: 'no-store' })
        const j = await r.json()
        if (alive) { setState(j); setErr(null) }
      } catch (e) {
        if (alive) setErr(String(e))
      }
    }
    load()
    const t = setInterval(load, intervalMs)
    return () => { alive = false; clearInterval(t) }
  }, [intervalMs])

  return { state, err }
}

// Color per node-family kind — keep in sync with the legend in App.jsx.
export const KIND_COLOR = {
  base: '#5cc8ff',
  regressor: '#36e0c8',
  physics: '#ff8c42',
  chaos: '#ffd23f',
  signal: '#4ad9ff',
  quant: '#7cff6b',
  math: '#c98bff',
  ml: '#5cc8ff',
  control: '#ff6bd6',
  ensemble: '#b98cff',
  meta: '#b98cff',
  output: '#4ade80',
  automl: '#f0a14b',
  symbolic: '#4ade80',
  regime: '#fbbf24',
  chaos: '#36e0c8',
  router: '#ff7ab6',
  brain: '#ffffff',
}
export const kindColor = (k) => KIND_COLOR[k] || '#8ea0c0'
