// useTrading — polls every T6 trading API endpoint and returns one honest state
// object. Components are presentational and receive this via props; only this hook
// touches the network. Endpoint JSON shapes are the contract the backend implements.
import { useEffect, useRef, useState } from 'react'

const ENDPOINTS = {
  tickers: '/api/trading/tickers',           // {tickers:[{symbol,last,change,change_pct,market}], demo}
  openTrades: '/api/trading/opentrades',     // {columns:[...], rows:[{...}], demo}
  closedTrades: '/api/trading/closedtrades', // {columns:[...85+...], rows:[{...}], demo}
  confidence: '/api/trading/confidence',     // {symbols:[{symbol,confidence,win_rate,n,brier}], demo}
  context: '/api/trading/context',           // {india_vix, fii_dii, fear_greed, demo}
  execution: '/api/trading/execution/status',
  options: '/api/trading/options/status',
  journal: '/api/trading/journal/status',
  candles: '/api/trading/candles?symbol=BTC/USDT&market=CRYPTO&tf=5m', // {symbol,market,tf,candles:[{time,open,high,low,close,volume}],live}
  orderbook: '/api/trading/orderbook?symbol=BTC/USDT&market=CRYPTO', // {symbol,market,bids:[[price,size],...],asks:[[price,size],...],mid,spread,live}
}

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`)
  return r.json()
}

export function useTrading(intervalMs = 4000) {
  const [data, setData] = useState({})
  const [err, setErr] = useState(null)
  const timer = useRef(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const entries = await Promise.all(
          Object.entries(ENDPOINTS).map(async ([k, url]) => {
            try { return [k, await getJSON(url)] } catch (e) { return [k, { error: String(e) }] }
          })
        )
        if (!alive) return
        setData(Object.fromEntries(entries))
        setErr(null)
      } catch (e) {
        if (alive) setErr(String(e))
      }
    }
    tick()
    timer.current = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(timer.current) }
  }, [intervalMs])

  return { data, err }
}
