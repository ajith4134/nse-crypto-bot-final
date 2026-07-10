<script setup lang="ts">
// BrainControlView — custom MLNetworkBrain panel inside FreqUI: the controls FreqUI lacks
// (paper↔live / spot↔futures toggle, editable paper balance / max-trades / stake / leverage),
// a live markets screener (volume/movers/volatility/funding), and the open/closed trade tables
// with capital + P&L (USDT) + peak MFE/MAE. Calls the MLNetworkBrain dashboard API cross-origin
// (CORS-enabled); the dashboard base URL is configurable + persisted in localStorage.
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts';

const TFS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];
const chartSym = ref('BTC/USDT');
const chartTf = ref('15m');
const chartEl = ref<HTMLElement | null>(null);
let chart: any = null;
let candleSeries: any = null;
let volSeries: any = null;
function pick(sym: string) { chartSym.value = sym; loadChart(); }
async function loadChart() {
  if (!ready.value || !candleSeries) return;
  try {
    const r = await fetch(`${dashUrl.value}/api/trading/candles?symbol=${encodeURIComponent(chartSym.value)}&market=CRYPTO&tf=${chartTf.value}`);
    const j = await r.json();
    const c = (j.candles || []);
    if (!c.length) return;
    candleSeries.setData(c);
    volSeries.setData(c.map((b: any) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? 'rgba(14,203,129,.5)' : 'rgba(246,70,93,.5)' })));
    chart && chart.timeScale().fitContent();
  } catch { /* */ }
}
function setTf(t: string) { chartTf.value = t; loadChart(); }

const DASH_KEY = 'mlnb_dashboard_url';
// Default to the current MLNetworkBrain dashboard tunnel so the Brain tab auto-connects (no typing).
// Update if the dashboard tunnel URL changes, or override via the "change" link (saved locally).
const DEFAULT_DASH = 'https://between-payroll-postal-glossary.trycloudflare.com';
const dashUrl = ref<string>(localStorage.getItem(DASH_KEY) || DEFAULT_DASH);
// The dashboard tunnel URL changes every launch, so a value cached in localStorage goes stale and
// then markets/trades/controls all fail silently. The dashboard writes the CURRENT url into a
// same-origin overlay file (mlnb_status.json); read it as the source of truth so the Brain tab
// always points at the live tunnel without the user re-typing it.
async function syncDashUrl() {
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}mlnb_status.json?t=${Date.now()}`);
    const j = await r.json();
    const u = String(j?.dashboard_url || '').replace(/\/$/, '');
    if (u && u !== dashUrl.value) {
      dashUrl.value = u;
      urlInput.value = u;
      localStorage.setItem(DASH_KEY, u);
    }
  } catch { /* overlay not present yet — keep localStorage/default fallback */ }
}
const urlInput = ref<string>(dashUrl.value);
const params = ref<any>({});
const markets = ref<any[]>([]);
const openT = ref<any[]>([]);
const closedT = ref<any[]>([]);
const sort = ref<string>('volume');
const segment = ref<string>('perp');
const msg = ref<string>('');
let timer: number | undefined;

const ready = computed(() => !!dashUrl.value);
function saveUrl() {
  dashUrl.value = urlInput.value.replace(/\/$/, '');
  localStorage.setItem(DASH_KEY, dashUrl.value);
  refresh();
}
async function getJSON(path: string) {
  const r = await fetch(`${dashUrl.value}${path}`);
  return r.json();
}
async function post(path: string, body: any) {
  const r = await fetch(`${dashUrl.value}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  return r.json();
}
async function refresh() {
  await syncDashUrl();
  if (!ready.value) return;
  try {
    const t = await getJSON('/api/trading/crypto/trades');
    params.value = t.params || {};
    openT.value = t.open || [];
    closedT.value = (t.closed || []).slice(-40).reverse();
    const m = await getJSON(`/api/trading/crypto/markets?segment=${segment.value}&sort=${sort.value}&limit=40`);
    markets.value = m.rows || [];
    msg.value = '';
  } catch (e: any) {
    msg.value = `can't reach ${dashUrl.value} — ${e?.message || e}. Use the dashboard's HTTPS URL (not http/localhost).`;
  }
}
async function applyParam(body: any, label: string) {
  msg.value = `${label} → applying (bot restart)…`;
  const r = await post('/api/trading/crypto/params', body);
  msg.value = r.ok !== false ? `${label} ✓` : `${label}: ${r.reason || 'failed'}`;
  setTimeout(refresh, 6000);
}
async function switchMode(body: any, label: string, confirmMsg?: string) {
  if (confirmMsg && !window.confirm(confirmMsg)) return;
  msg.value = `${label} → restarting…`;
  const r = await post('/api/trading/crypto/mode', body);
  msg.value = r.ok !== false ? `${label} ✓` : `${label}: ${r.reason || 'refused'}`;
  setTimeout(refresh, 6000);
}
function setSort(s: string) { sort.value = s; refresh(); }

const isLive = computed(() => params.value.mode === 'live' || params.value.dry_run === false);
const isFut = computed(() => params.value.segment === 'futures');
const n = (v: any, d = 2) => (v == null || isNaN(v) ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
// Aggregate P&L indicators (USDT) — open unrealized + closed realized.
const openPnl = computed(() => openT.value.reduce((s, r) => s + (Number(r.unrealized_pnl_usdt) || 0), 0));
const closedPnl = computed(() => closedT.value.reduce((s, r) => s + (Number(r.net_pnl_crypto ?? r.net_pnl) || 0), 0));

onMounted(() => {
  refresh();
  timer = window.setInterval(refresh, 6000);
  if (chartEl.value) {
    chart = createChart(chartEl.value, {
      autoSize: true,
      layout: { background: { color: 'transparent' }, textColor: '#9aa4bf', fontFamily: 'Inter, system-ui' },
      grid: { vertLines: { color: '#1e2638' }, horzLines: { color: '#1e2638' } },
      timeScale: { timeVisible: true, borderColor: '#2a3550' },
      rightPriceScale: { borderColor: '#2a3550' },
    });
    candleSeries = chart.addSeries(CandlestickSeries, { upColor: '#0ecb81', downColor: '#f6465d', borderUpColor: '#0ecb81', borderDownColor: '#f6465d', wickUpColor: '#0ecb81', wickDownColor: '#f6465d' });
    volSeries = chart.addSeries(HistogramSeries, { priceScaleId: 'vol', priceFormat: { type: 'volume' } });
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    loadChart();
  }
});
watch([chartSym, chartTf], loadChart);
onUnmounted(() => { if (timer) clearInterval(timer); if (chart) chart.remove(); });
</script>

<template>
  <div class="p-4 text-sm" style="font-family: Inter, system-ui, sans-serif;">
    <h2 class="text-xl font-extrabold mb-3">🧠 MLNetworkBrain — Crypto Control</h2>

    <div v-if="!ready" class="mb-4 p-3 rounded border border-gray-500">
      <div class="mb-2 font-semibold">Connect to the MLNetworkBrain dashboard API:</div>
      <input v-model="urlInput" placeholder="https://your-dashboard.trycloudflare.com"
        class="px-2 py-1 rounded border border-gray-500 w-96 bg-transparent" />
      <button @click="saveUrl" class="ml-2 px-3 py-1 rounded bg-blue-600 text-white font-bold">Connect</button>
      <div class="text-xs text-gray-400 mt-1">The dashboard URL (port 8000 / its tunnel). Saved locally; CORS-enabled.</div>
    </div>

    <template v-else>
      <div class="flex items-center gap-3 mb-3 flex-wrap">
        <span :class="isLive ? 'text-red-500' : 'text-green-500'" class="font-bold">{{ isLive ? 'LIVE 💵' : 'PAPER' }}</span>
        <span class="text-amber-400 font-bold">{{ (params.segment || 'spot').toUpperCase() }}</span>
        <span v-if="msg" class="text-xs px-2 py-0.5 rounded border">{{ msg }}</span>
        <span class="text-xs text-gray-400 ml-auto">dash: {{ dashUrl }} <button @click="dashUrl=''" class="underline">change</button></span>
      </div>

      <!-- controls -->
      <div class="flex gap-4 flex-wrap items-end p-3 rounded border border-gray-600 mb-4">
        <label class="flex flex-col gap-1 text-xs">Paper balance (USDT)
          <span class="flex gap-1"><input :value="params.paper_balance" type="number" step="1000" class="w-28 px-2 py-1 rounded border border-gray-500 bg-transparent" @keyup.enter="applyParam({paper_balance:Number(($event.target as any).value)},'Paper balance')" id="pb" /><button @click="applyParam({paper_balance:Number((document.getElementById('pb') as any).value)},'Paper balance')" class="px-2 rounded border">Set</button></span></label>
        <label class="flex flex-col gap-1 text-xs">Max open trades
          <span class="flex gap-1"><input :value="params.max_open_trades" type="number" class="w-20 px-2 py-1 rounded border border-gray-500 bg-transparent" id="mt" /><button @click="applyParam({max_open_trades:Number((document.getElementById('mt') as any).value)},'Max open')" class="px-2 rounded border">Set</button></span></label>
        <label class="flex flex-col gap-1 text-xs">Min capital (USDT)
          <span class="flex gap-1"><input :value="params.stake_amount" type="number" step="50" class="w-24 px-2 py-1 rounded border border-gray-500 bg-transparent" id="sa" /><button @click="applyParam({stake_amount:Number((document.getElementById('sa') as any).value)},'Stake')" class="px-2 rounded border">Set</button></span></label>
        <label class="flex flex-col gap-1 text-xs">Leverage (x)
          <span class="flex gap-1"><input :value="params.leverage" type="number" class="w-16 px-2 py-1 rounded border border-gray-500 bg-transparent" id="lv" /><button @click="applyParam({leverage:Number((document.getElementById('lv') as any).value)},'Leverage')" class="px-2 rounded border">Set</button></span></label>
        <button @click="isFut ? switchMode({segment:'spot'},'→ Spot') : switchMode({segment:'futures'},'→ Futures','Switch to FUTURES (perp, shorting)? Bot restarts.')" class="px-3 py-1.5 rounded border border-amber-500 text-amber-400 font-bold">{{ isFut ? '→ Spot' : '→ Futures' }}</button>
        <button @click="isLive ? switchMode({mode:'paper'},'→ Paper') : switchMode({mode:'live',confirm:true},'→ LIVE','Switch to LIVE (REAL MONEY)? Bot restarts and trades real funds.')" :class="isLive ? 'border-green-500 text-green-400' : 'border-red-500 text-red-400'" class="px-3 py-1.5 rounded border font-bold">{{ isLive ? '→ Paper' : '→ LIVE 💵' }}</button>
      </div>

      <!-- markets screener -->
      <div class="font-bold mb-1">📈 Markets — pick universe</div>
      <div class="flex gap-1 mb-2 flex-wrap">
        <span v-for="s in ['volume','movers','gainers','losers','volatility','funding','price']" :key="s"
          @click="setSort(s)" :class="sort===s ? 'bg-blue-600 text-white' : 'border'" class="px-2 py-0.5 rounded text-xs cursor-pointer border-gray-500">{{ s }}</span>
        <span @click="segment = segment==='perp'?'spot':'perp'; refresh()" class="px-2 py-0.5 rounded text-xs cursor-pointer border border-amber-500 text-amber-400 ml-2">{{ segment.toUpperCase() }}</span>
      </div>
      <div class="overflow-auto mb-4" style="max-height: 240px">
        <table class="w-full text-xs" style="min-width: 640px"><thead><tr class="text-gray-400 text-left">
          <th class="p-1">Symbol</th><th class="p-1 text-right">Last</th><th class="p-1 text-right">24h%</th><th class="p-1 text-right">Volatility</th><th class="p-1 text-right">Funding</th><th class="p-1 text-right">Vol</th></tr></thead>
          <tbody><tr v-if="!markets.length"><td colspan="6" class="p-3 text-center text-gray-500">loading markets…</td></tr>
          <tr v-for="r in markets" :key="r.symbol" class="border-t border-gray-700">
            <td class="p-1 font-semibold">{{ r.display }} <span class="text-gray-500">{{ r.segment }}</span></td>
            <td class="p-1 text-right">{{ n(r.last, 6) }}</td>
            <td class="p-1 text-right" :class="r.pct_24h>=0?'text-green-500':'text-red-500'">{{ r.pct_24h>=0?'+':'' }}{{ r.pct_24h?.toFixed(2) }}%</td>
            <td class="p-1 text-right text-amber-400">{{ r.volatility }}%</td>
            <td class="p-1 text-right" :class="r.funding>=0?'text-green-500':'text-red-500'">{{ r.funding }}%</td>
            <td class="p-1 text-right text-gray-400">{{ n(r.quote_volume/1e6,0) }}M</td>
          </tr></tbody></table>
      </div>

      <!-- open trades -->
      <div class="font-bold mb-1 flex items-center gap-2">Open ({{ openT.length }})
        <span class="text-xs font-normal">· Total uP&L
          <span :class="openPnl>=0?'text-green-500':'text-red-500'">{{ openPnl>=0?'+':'' }}{{ n(openPnl,4) }} USDT</span></span></div>
      <div class="overflow-auto mb-4"><table class="w-full text-xs"><thead><tr class="text-gray-400 text-left">
        <th class="p-1">Symbol</th><th class="p-1">Side</th><th class="p-1 text-right">Lev</th><th class="p-1 text-right">Capital USDT</th><th class="p-1 text-right">uP&L USDT</th><th class="p-1 text-right">Peak+ (MFE)</th><th class="p-1 text-right">Peak− (MAE)</th><th class="p-1">Strategy</th><th class="p-1">Brain</th><th class="p-1">NN</th></tr></thead>
        <tbody><tr v-if="!openT.length"><td colspan="10" class="p-2 text-center text-gray-500">no open trades</td></tr>
        <tr v-for="r in openT" :key="r.trade_id" class="border-t border-gray-700">
          <td class="p-1">{{ r.symbol }}</td><td class="p-1" :class="r.direction==='SHORT'?'text-red-500':'text-green-500'">{{ r.direction }}</td>
          <td class="p-1 text-right">{{ r.leverage }}x</td><td class="p-1 text-right">{{ n(r.capital_usdt) }}</td>
          <td class="p-1 text-right" :class="r.unrealized_pnl_usdt>=0?'text-green-500':'text-red-500'">{{ n(r.unrealized_pnl_usdt,4) }}</td>
          <td class="p-1 text-right text-green-500">{{ n(r.peak_profit_usdt,4) }}</td><td class="p-1 text-right text-red-500">{{ n(r.peak_loss_usdt,4) }}</td>
          <td class="p-1 text-cyan-400">{{ r.strategy_label }}</td>
          <td class="p-1" :class="String(r.brain_pred).startsWith('SHORT')?'text-red-400':'text-green-400'">{{ r.brain_pred }}</td>
          <td class="p-1 text-amber-300">{{ r.nn_pred }}</td>
        </tr></tbody></table></div>

      <!-- closed trades -->
      <div class="font-bold mb-1 flex items-center gap-2">Closed ({{ closedT.length }})
        <span class="text-xs font-normal">· Total net P&L
          <span :class="closedPnl>=0?'text-green-500':'text-red-500'">{{ closedPnl>=0?'+':'' }}{{ n(closedPnl,4) }} USDT</span></span></div>
      <div class="overflow-auto"><table class="w-full text-xs"><thead><tr class="text-gray-400 text-left">
        <th class="p-1">Trade</th><th class="p-1">Symbol</th><th class="p-1">Side</th><th class="p-1 text-right">Entry</th><th class="p-1 text-right">Exit</th><th class="p-1 text-right">Net P&L USDT</th><th class="p-1 text-right">MFE</th><th class="p-1 text-right">MAE</th><th class="p-1">Strategy</th><th class="p-1">Brain</th><th class="p-1">NN</th></tr></thead>
        <tbody><tr v-if="!closedT.length"><td colspan="11" class="p-2 text-center text-gray-500">no closed trades</td></tr>
        <tr v-for="r in closedT" :key="r.trade_id" class="border-t border-gray-700">
          <td class="p-1">{{ r.trade_id }}</td><td class="p-1">{{ r.symbol }}</td><td class="p-1" :class="r.direction==='SHORT'?'text-red-500':'text-green-500'">{{ r.direction }}</td>
          <td class="p-1 text-right">{{ n(r.entry_price,4) }}</td><td class="p-1 text-right">{{ n(r.exit_price,4) }}</td>
          <td class="p-1 text-right" :class="(r.net_pnl_crypto ?? r.net_pnl)>=0?'text-green-500':'text-red-500'">{{ n(r.net_pnl_crypto ?? r.net_pnl,4) }}</td>
          <td class="p-1 text-right text-green-500">{{ n(r.mfe,4) }}</td><td class="p-1 text-right text-red-500">{{ n(r.mae,4) }}</td>
          <td class="p-1 text-cyan-400">{{ r.strategy_label }}</td>
          <td class="p-1" :class="String(r.brain_pred).startsWith('SHORT')?'text-red-400':'text-green-400'">{{ r.brain_pred }}</td>
          <td class="p-1 text-amber-300">{{ r.nn_pred }}</td>
        </tr></tbody></table></div>
    </template>
  </div>
</template>
