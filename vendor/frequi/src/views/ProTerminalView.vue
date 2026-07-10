<script setup lang="ts">
// mlnb BN-U3 "Pro Terminal" (2026-07-10, owner-approved) — chart-first trading view:
// full-height candles with the brain's REAL entry/exit markers (reason in the marker
// text), the live tailgate ratchet drawn as price lines (lock + peak, converted from
// the leverage-scaled % the engine enforces), and dockable side panels (trades ·
// brain feed + X-Ray). Candles come from the brain dashboard's ccxt endpoint (any
// timeframe, same source the Brain tab chart uses); trades/locks are same-origin
// /api/v1 + /api/v1/mlnb — the E2 native fields, no cross-origin overlay.
import { createChart, CandlestickSeries, HistogramSeries, createSeriesMarkers } from 'lightweight-charts';
import type { Trade } from '@/types';

const botStore = useBotStore();
const { dashUrl, dashJson } = useMlnbDash();

const TFS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];
const tf = ref('15m');
const pair = ref<string>('');
const showLeft = ref(true);
const showRight = ref(true);
const status = ref<string>('');

// ── trades for the selected pair ──────────────────────────────────────────────
const openForPair = computed<Trade[]>(() =>
  botStore.activeBot.openTrades.filter((t) => t.pair === pair.value),
);
const closedForPair = computed<Trade[]>(() =>
  (botStore.activeBot.trades as Trade[])
    .filter((t) => t.pair === pair.value && !t.is_open)
    .slice(-40),
);
const xrayTrade = computed<Trade | undefined>(() => openForPair.value[0]);

// ── chart ─────────────────────────────────────────────────────────────────────
const chartEl = ref<HTMLElement | null>(null);
let chart: any = null;
let candleSeries: any = null;
let volSeries: any = null;
let markersPlugin: any = null;
let priceLines: any[] = [];
let firstCandleTs = 0;

function ensureChart() {
  if (chart || !chartEl.value) return;
  chart = createChart(chartEl.value, {
    autoSize: true,
    layout: {
      background: { color: 'transparent' },
      textColor: '#9aa4bf',
      fontFamily: 'Inter, system-ui',
    },
    grid: { vertLines: { color: '#1e2638' }, horzLines: { color: '#1e2638' } },
    timeScale: { timeVisible: true, borderColor: '#2a3550' },
    rightPriceScale: { borderColor: '#2a3550' },
  });
  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: '#0ecb81',
    downColor: '#f6465d',
    borderUpColor: '#0ecb81',
    borderDownColor: '#f6465d',
    wickUpColor: '#0ecb81',
    wickDownColor: '#f6465d',
  });
  volSeries = chart.addSeries(HistogramSeries, {
    priceScaleId: 'vol',
    priceFormat: { type: 'volume' },
    color: '#2a3550',
  });
  chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  markersPlugin = createSeriesMarkers(candleSeries, []);
}

async function loadChart() {
  if (!pair.value) return;
  ensureChart();
  if (!candleSeries) return;
  // full pair as-held (futures notation included) — the dash endpoint routes
  // spot symbols to the spot pool and perp/futures-only symbols to the swap pool
  status.value = 'loading…';
  const j = await dashJson(
    `/api/trading/candles?symbol=${encodeURIComponent(pair.value)}&market=CRYPTO&tf=${tf.value}`,
  );
  const candles = j?.candles || [];
  if (!candles.length) {
    status.value = j === null
      ? `brain dashboard unreachable (${dashUrl.value})`
      : `no ${tf.value} candles for ${pair.value}${j?.error ? ` — ${j.error}` : ''}`;
    return;
  }
  status.value = '';
  firstCandleTs = candles[0].time;
  candleSeries.setData(candles);
  volSeries.setData(
    candles.map((c: any) => ({
      time: c.time,
      value: c.volume,
      color: c.close >= c.open ? '#0ecb8144' : '#f6465d44',
    })),
  );
  drawMarkers();
  await drawRatchetLines();
}

// ── brain entry/exit markers (REAL trades only; reason rides the marker text) ─
function drawMarkers() {
  if (!markersPlugin) return;
  const marks: any[] = [];
  const inRange = (tsMs: number | undefined) =>
    tsMs != null && tsMs / 1000 >= firstCandleTs ? Math.floor(tsMs / 1000) : null;
  for (const t of closedForPair.value) {
    const et = inRange((t as any).open_timestamp);
    if (et != null)
      marks.push({
        time: et,
        position: t.is_short ? 'aboveBar' : 'belowBar',
        color: t.is_short ? '#f6465d' : '#0ecb81',
        shape: t.is_short ? 'arrowDown' : 'arrowUp',
        text: `${t.is_short ? 'S' : 'L'} #${t.trade_id}`,
      });
    const xt = inRange((t as any).close_timestamp);
    if (xt != null)
      marks.push({
        time: xt,
        position: 'aboveBar',
        color: (t.profit_abs ?? 0) >= 0 ? '#f0b90b' : '#8b95b0',
        shape: 'circle',
        text: `✕ ${t.exit_reason || 'exit'} ${(t.profit_abs ?? 0) >= 0 ? '+' : ''}${(
          t.profit_abs ?? 0
        ).toFixed(2)}`,
      });
  }
  for (const t of openForPair.value) {
    const et = inRange((t as any).open_timestamp);
    if (et != null)
      marks.push({
        time: et,
        position: t.is_short ? 'aboveBar' : 'belowBar',
        color: '#22d3ee',
        shape: t.is_short ? 'arrowDown' : 'arrowUp',
        text: `OPEN ${t.is_short ? 'S' : 'L'} #${t.trade_id}`,
      });
  }
  marks.sort((a, b) => a.time - b.time);
  markersPlugin.setMarkers(marks);
}

// ── live tailgate ratchet lines (engine-enforced locks, /api/v1/mlnb/tailgate) ─
// The lock file stores the LEVERAGE-SCALED profit % the engine enforces
// (custom_exit compares it to current_profit*100). Convert to a chart price:
// long → open_rate·(1 + lock/(100·lev)), short mirrored. Fees are not modeled in
// the conversion, so lines are labeled ≈. No lock recorded → no line, honestly.
async function drawRatchetLines() {
  for (const l of priceLines) candleSeries.removePriceLine(l);
  priceLines = [];
  if (!openForPair.value.length) return;
  const res = await botStore.activeBot.getMlnbState('tailgate');
  const locks = res?.locks || {};
  for (const t of openForPair.value) {
    const lk = locks[String(t.trade_id)];
    if (!lk || typeof lk !== 'object') continue;
    const lev = Number((t as any).leverage || 1) || 1;
    const dirn = t.is_short ? -1 : 1;
    const toPrice = (pct: number) => t.open_rate * (1 + (dirn * pct) / (100 * lev));
    if (lk.locked != null && Number(lk.locked) > 0)
      priceLines.push(
        candleSeries.createPriceLine({
          price: toPrice(Number(lk.locked)),
          color: '#f0b90b',
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: `≈LOCK #${t.trade_id} ${Number(lk.locked).toFixed(2)}%`,
        }),
      );
    if (lk.peak != null)
      priceLines.push(
        candleSeries.createPriceLine({
          price: toPrice(Number(lk.peak)),
          color: '#8b95b0',
          lineWidth: 1,
          lineStyle: 3,
          axisLabelVisible: true,
          title: `≈PEAK #${t.trade_id} ${Number(lk.peak).toFixed(2)}%`,
        }),
      );
  }
}

// ── selection + lifecycle ─────────────────────────────────────────────────────
function pick(p: string) {
  pair.value = p;
  loadChart();
}
function setTf(t: string) {
  tf.value = t;
  loadChart();
}

let timer: number | undefined;
async function init() {
  try {
    // activeBot may not be selected yet on a cold deep-link to /terminal
    await Promise.all([botStore.activeBot.getOpenTrades(), botStore.activeBot.getTrades()]);
  } catch {
    /* trades arrive via the global auto-refresh instead */
  }
  if (!pair.value) pair.value = botStore.activeBot?.openTrades?.[0]?.pair || 'BTC/USDT:USDT';
  loadChart();
}
// late store hydration (deep link): adopt the first open trade's pair once it appears
watch(
  () => botStore.activeBot?.openTrades?.length,
  () => {
    if (pair.value === 'BTC/USDT:USDT' && botStore.activeBot.openTrades.length) {
      pick(botStore.activeBot.openTrades[0].pair);
    }
  },
);
onMounted(() => {
  init();
  timer = window.setInterval(loadChart, 30000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
  if (chart) chart.remove();
  chart = null;
});
</script>

<template>
  <div class="flex h-full text-xs">
    <!-- LEFT DOCK: open trades (all pairs) — click to chart -->
    <div v-if="showLeft" class="w-56 shrink-0 border-r border-neutral-800 overflow-y-auto">
      <div class="p-1 text-neutral-500 font-semibold">OPEN TRADES</div>
      <div
        v-for="t in botStore.activeBot.openTrades"
        :key="t.trade_id"
        class="px-2 py-1 cursor-pointer border-b border-neutral-900 hover:bg-neutral-800/60"
        :class="t.pair === pair ? 'bg-cyan-950/40 border-s-2 border-s-cyan-500' : ''"
        @click="pick(t.pair)"
      >
        <div class="flex justify-between">
          <span>{{ t.pair.split('/')[0] }}</span>
          <span :class="t.is_short ? 'text-red-400' : 'text-green-400'">
            {{ t.is_short ? 'SHORT' : 'LONG' }}
          </span>
        </div>
        <div class="flex justify-between text-neutral-400">
          <span>#{{ t.trade_id }} · {{ (t as any).bot_segment || 'futures' }}</span>
          <span :class="(t.profit_abs ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'">
            {{ (t.profit_abs ?? 0) >= 0 ? '+' : '' }}{{ (t.profit_abs ?? 0).toFixed(2) }}
          </span>
        </div>
      </div>
      <div v-if="!botStore.activeBot.openTrades.length" class="p-2 text-neutral-500">
        no open trades
      </div>
    </div>

    <!-- CENTER: chart-first -->
    <div class="flex-1 min-w-0 flex flex-col">
      <div class="flex items-center gap-1 p-1 border-b border-neutral-800 flex-wrap">
        <button
          class="px-2 py-0.5 rounded border border-neutral-700 text-neutral-400"
          title="toggle trades dock"
          @click="showLeft = !showLeft"
        >
          ⇤
        </button>
        <span class="font-semibold text-sm text-neutral-200">{{ pair || '—' }}</span>
        <span class="text-neutral-500">{{ openForPair.length }} open here</span>
        <span class="mx-2 text-neutral-700">|</span>
        <button
          v-for="t in TFS"
          :key="t"
          class="px-1.5 py-0.5 rounded border"
          :class="
            tf === t
              ? 'border-cyan-500 text-cyan-300'
              : 'border-neutral-800 text-neutral-500 hover:text-neutral-300'
          "
          @click="setTf(t)"
        >
          {{ t }}
        </button>
        <span v-if="status" class="text-amber-400 ms-2">{{ status }}</span>
        <button
          class="px-2 py-0.5 rounded border border-neutral-700 text-neutral-400 ms-auto"
          title="toggle brain dock"
          @click="showRight = !showRight"
        >
          ⇥
        </button>
      </div>
      <div ref="chartEl" class="flex-1 min-h-0"></div>
      <div class="p-1 text-neutral-600 border-t border-neutral-900">
        markers = real brain entries/exits (text = reason) · dashed ≈LOCK line = the
        ratchet exit the engine enforces · dotted ≈PEAK = best profit seen
      </div>
    </div>

    <!-- RIGHT DOCK: brain X-Ray for the charted open trade + live brain feed -->
    <div v-if="showRight" class="w-72 shrink-0 border-s border-neutral-800 flex flex-col">
      <div v-if="xrayTrade" class="border-b border-neutral-800 max-h-[45%] overflow-y-auto">
        <BrainXray :trade="xrayTrade" />
      </div>
      <div class="flex-1 min-h-0">
        <div class="p-1 text-neutral-500 font-semibold">BRAIN FEED</div>
        <div class="h-[calc(100%-1.5rem)]">
          <BrainFeed />
        </div>
      </div>
    </div>
  </div>
</template>
