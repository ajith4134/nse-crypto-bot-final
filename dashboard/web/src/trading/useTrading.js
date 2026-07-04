// useTrading — polls every T6 trading API endpoint and returns one honest state
// object. Components are presentational and receive this via props; only this hook
// touches the network. Endpoint JSON shapes are the contract the backend implements.
import { useEffect, useRef, useState } from 'react'

const ENDPOINTS = {
  tickers: '/api/trading/tickers',           // {tickers:[{symbol,last,change,change_pct,market}], demo}
  openTrades: '/api/trading/opentrades',     // {columns:[...], rows:[{...}], demo}
  scorecard: '/api/trading/scorecard',       // {groups:[{market,currency,cards:[{segment,realized,unrealized,total,open_count,closed_count}]}], grand_total_inr}
  closedTrades: '/api/trading/closedtrades', // {columns:[...85+...], rows:[{...}], demo}
  confidence: '/api/trading/confidence',     // {symbols:[{symbol,confidence,win_rate,n,brier}], demo}
  context: '/api/trading/context',           // {india_vix, fii_dii, fear_greed, demo}
  execution: '/api/trading/execution/status',
  options: '/api/trading/options/status',
  journal: '/api/trading/journal/status',
  candles: '/api/trading/candles?symbol=BTC/USDT&market=CRYPTO&tf=5m', // {symbol,market,tf,candles:[{time,open,high,low,close,volume}],live}
  orderbook: '/api/trading/orderbook?symbol=BTC/USDT&market=CRYPTO', // {symbol,market,bids:[[price,size],...],asks:[[price,size],...],mid,spread,live}
  watchlist: '/api/trading/watchlist',       // {watchlist:{NSE:[{symbol,segment,last}],CRYPTO:[...]}, candidates:{NSE:[{symbol,segment,market,score,reason,metrics}],...}, live}
  loop: '/api/trading/online/loop',          // {..., config:{trail_atr_mult,sizing_method,max_risk_pct,max_position_pct,kelly_fraction}, selected_segments}
  brainPredict: '/api/trading/brain/predict', // {model:{engine,trained,oof_accuracy,n_train,...}, open_predictions:[...], closed_replay:[...]}
  strategyLibrary: '/api/trading/strategy/library', // {coverage:{total,n_executable,n_data_gated,by_category,by_segment}, leaderboard:[{rank,name,category,metrics}], data_gated:{total,by_gating_need,sample}, evolution_status}
  guiAgent: '/api/trading/gui/status?observe=1',  // {targets, perception_capabilities, action_capabilities, skills:{n_skills,n_practiced,skills:[...]}, reflections:{n_lessons,recent:[...]}, last_perception:{reachable,n_controls,charts}, available, note}
}

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`)
  return r.json()
}

// Poll cadence per endpoint, in ticks of the base interval (4s): live-feel data every
// tick; aggregates every few ticks; near-static catalogs rarely. Combined with the
// hidden-tab pause this cuts tunnel traffic ~70% with no visible staleness (the server
// additionally serves the heavy ones from its stale-while-revalidate cache).
const EVERY = {
  tickers: 1, orderbook: 1, openTrades: 2, loop: 2, candles: 2,
  scorecard: 4, confidence: 4, closedTrades: 4, execution: 4,
  watchlist: 8, context: 8, options: 8, journal: 8, brainPredict: 8,
  strategyLibrary: 15, guiAgent: 15,
}

export function useTrading(intervalMs = 4000) {
  const [data, setData] = useState({})
  const [err, setErr] = useState(null)
  const timer = useRef(null)
  const tickNo = useRef(0)

  useEffect(() => {
    let alive = true
    // Each endpoint refreshes INDEPENDENTLY and merges into state by key — so one slow
    // endpoint (e.g. brain/predict trains the NN, brain/status builds a pipeline) never
    // stalls or blanks the other panels. (A single Promise.all batch made the whole
    // dashboard flicker empty every tick whenever any one endpoint was slow.)
    const tick = (first = false) => {
      if (!first && document.hidden) return   // hidden tab: stop polling entirely
      const n = tickNo.current++
      Object.entries(ENDPOINTS).forEach(([k, url]) => {
        if (!first && n % (EVERY[k] || 1) !== 0) return
        getJSON(url)
          .then((v) => { if (alive) { setData((d) => ({ ...d, [k]: v })); setErr(null) } })
          .catch((e) => {
            if (alive) {
              setData((d) => ({ ...d, [k]: { ...(d[k] || {}), error: String(e) } }))
              setErr(String(e))
            }
          })
      })
    }
    tick(true)
    timer.current = setInterval(tick, intervalMs)
    // refresh immediately when the user returns to the tab
    const onVis = () => { if (!document.hidden) tick(true) }
    document.addEventListener('visibilitychange', onVis)
    return () => { alive = false; clearInterval(timer.current); document.removeEventListener('visibilitychange', onVis) }
  }, [intervalMs])

  return { data, err }
}
