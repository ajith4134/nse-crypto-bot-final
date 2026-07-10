<script setup lang="ts">
// MlnbControls — MLNetworkBrain crypto controls, embedded in the Trade view: editable paper
// balance, max open trades, min capital (stake), leverage + spot↔futures / paper↔live toggles.
// Reads current values SAME-ORIGIN from /mlnb_status.json (the dashboard writes it). POSTs changes
// to the dashboard (cross-origin, CORS); the dashboard URL is read from that same file (survives
// tunnel changes). Applying a change restarts the Freqtrade bot.
import { ref, computed, onMounted, onUnmounted } from 'vue';

const params = ref<any>({});
const dashUrl = ref<string>('');
const msg = ref<string>('');
// Trade-type segment buttons (mini-Binance goal): Futures/Spot/Options/Prediction, multi-select,
// persisted in the dashboard's control registry. Every segment now runs a REAL engine inside
// the forked multi-segment Freqtrade process (vendor/freqtrade, mlnb_segments in config.json);
// non-futures segments execute paper/dry-run.
const SEG_META = [
  { key: 'futures', label: '⚡ Futures', note: 'Binance perp — live engine' },
  { key: 'spot', label: '🟢 Spot', note: 'Binance spot — own engine (paper)' },
  { key: 'options', label: '🎯 Options', note: 'Deribit options — own engine (paper)' },
  { key: 'prediction', label: '🔮 Prediction', note: 'Polymarket — own engine (paper)' },
];
const segSel = ref<string[]>([]);
// 🤖 AI-Brain unlimited mode: ON → the brain manages every limit itself in PAPER trading
// (auto wallet top-up, uncapped budgets) so learning never halts; OFF → manual values rule.
const brainUnlimited = ref(false);
let timer: number | undefined;
// local input state (v-model) — initialised ONCE from params so the 8s poll never overwrites
// what you're typing. The display badges still reflect live params.
const inp = ref({ paper_balance: '', max_open_trades: '', stake_amount: '', leverage: '' });
const seeded = ref(false);
// Candle-data refresh status (written by trading/crypto/freqtrade/candle_updater.py).
const candle = ref<any>({});
const candleAgo = computed(() => {
  const u = candle.value?.updated_at || candle.value?.started_at;
  if (!u) return '';
  const secs = Math.max(0, Math.floor((Date.now() - new Date(u).getTime()) / 1000));
  if (secs < 90) return `${secs}s ago`;
  if (secs < 5400) return `${Math.round(secs / 60)}m ago`;
  return `${Math.round(secs / 3600)}h ago`;
});

async function load() {
  try {
    const c = await (await fetch(`/mlnb_candles.json?t=${Date.now()}`)).json();
    candle.value = c || {};
  } catch { /* candle updater not running — indicator shows "off" */ }
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}mlnb_status.json?t=${Date.now()}`);
    const j = await r.json();
    params.value = j.params || {};
    dashUrl.value = (j.dashboard_url || '').replace(/\/$/, '');
    if (j.segments && Array.isArray(j.segments.selected)) segSel.value = j.segments.selected;
    if (typeof j.brain_unlimited === 'boolean') brainUnlimited.value = j.brain_unlimited;
    if (!seeded.value) {
      inp.value = {
        paper_balance: params.value.paper_balance ?? '',
        max_open_trades: params.value.max_open_trades ?? '',
        stake_amount: params.value.stake_amount ?? '',
        leverage: params.value.leverage ?? '',
      };
      seeded.value = true;
    }
  } catch { /* status file not ready yet */ }
}
async function post(path: string, body: any) {
  // SAME-ORIGIN first: through the Caddy gateway (:8100 / the public tunnel) /api/trading/* is
  // routed to the dashboard on the SAME host FreqUI is served from — no tunnel URL needed and
  // the browser's dashboard basic-auth is attached automatically. The cross-origin dashUrl is
  // only a fallback (it used to point at a dead trycloudflare URL → every control "failed").
  const opts = {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } as RequestInit;
  let sameOriginStatus = '';
  try {
    const r = await fetch(path, opts);
    if (r.status === 401) return { ok: false, reason: 'not logged in — open the dashboard root (/) once and sign in' };
    if (r.ok) return await r.json();
    // dashboard reachable but refused (404/500) or gateway said it's down (502) — report
    // the REAL status instead of silently falling through to a possibly-stale tunnel URL.
    sameOriginStatus = `dashboard answered HTTP ${r.status}${r.status === 502 ? ' (dashboard :8000 down? run start_all.sh / restart-dashboard)' : ''}`;
  } catch { sameOriginStatus = 'same-origin fetch failed (FreqUI opened directly on :8080?)'; }
  if (!dashUrl.value) return { ok: false, reason: sameOriginStatus || 'dashboard unreachable' };
  try {
    const r = await fetch(`${dashUrl.value}${path}`, opts);
    if (r.status === 401) return { ok: false, reason: 'not logged in — open the dashboard root (/) once and sign in' };
    return await r.json();
  } catch (e: any) {
    return { ok: false, reason: `dashboard unreachable: ${e?.message || e}` };
  }
}
// The bot restart (esp. spot→futures, which re-downloads perp data) can take 20-40s. Poll the
// status repeatedly so the UI reflects the NEW state once the bot settles — instead of reading
// stale state once at 6s and looking like it reverted.
function pollUntilSettled(secs = 45) {
  const started = Date.now();
  const tick = async () => {
    await load();
    if (Date.now() - started < secs * 1000) setTimeout(tick, 4000);
  };
  setTimeout(tick, 4000);
}
async function applyParam(body: any, label: string) {
  msg.value = `${label} → applying (bot restarting, ~30s)…`;
  const r = await post('/api/trading/crypto/params', body);
  msg.value = r.ok !== false ? `${label} ✓ (applying…)` : `${label}: ${r.reason || 'failed'}`;
  pollUntilSettled();
}
async function switchMode(body: any, label: string, confirmMsg?: string) {
  if (confirmMsg && !window.confirm(confirmMsg)) return;
  msg.value = `${label} → restarting (~30s for futures data)…`;
  const r = await post('/api/trading/crypto/mode', body);
  msg.value = r.ok !== false ? `${label} ✓ (restarting…)` : `${label}: ${r.reason || 'refused'}`;
  pollUntilSettled();
}
// Permanently wipe ALL closed trades (brain journal + Freqtrade history) so the brain stops
// learning on contaminated paper data. Type-to-confirm (must type RESET); the backend backs up
// both stores first, so the wipe is recoverable. OPEN trades are left untouched.
async function resetClosed() {
  const typed = window.prompt(
    'Type RESET to permanently wipe ALL closed trades (brain journal + Freqtrade history).\n' +
    'Backs up first — OPEN trades are untouched. The brain then retrains on the empty history.',
  );
  if (!typed || typed.trim().toUpperCase() !== 'RESET') { msg.value = 'Reset cancelled — nothing deleted'; return; }
  msg.value = 'Resetting closed trades…';
  const r = await post('/api/trading/closedtrades/reset', { confirm: 'RESET' });
  if (r.ok !== false) {
    msg.value = `Closed trades reset ✓ (journal ${r.journal_cleared ?? 0}, freqtrade ${r.freqtrade_deleted ?? 0} deleted, backed up)`;
    pollUntilSettled();
  } else {
    msg.value = `Reset failed: ${r.reason || 'error'}`;
  }
}

// Toggle one trade-type segment on/off (optimistic; the 10s status poll reconciles).
async function toggleSeg(key: string) {
  const on = segSel.value.includes(key);
  segSel.value = on ? segSel.value.filter((s) => s !== key) : [...segSel.value, key];
  const r = await post('/api/trading/online/control', { action: 'toggle_segment', market: 'CRYPTO', segment: key });
  msg.value = r.ok !== false ? `Segment ${key} ${on ? 'off' : 'on'} ✓` : `Segment ${key}: ${r.reason || 'failed'}`;
}
// 🤖 toggle AI-Brain unlimited mode. ON also lifts the Freqtrade max-open cap (paper).
async function toggleBrainUnlimited() {
  const next = !brainUnlimited.value;
  brainUnlimited.value = next;
  const r = await post('/api/trading/online/control', { action: 'set_strategy', brain_unlimited: next });
  if (next && r.ok !== false) {
    // unlimited Freqtrade open-trade cap too (paper) — bot restarts to apply
    post('/api/trading/crypto/params', { max_open_trades: -1 });
  }
  msg.value = r.ok !== false
    ? (next ? '🤖 AI Brain ON — unlimited paper learning (auto top-up, caps lifted)' : '🤖 AI Brain OFF — manual limits rule')
    : `AI Brain: ${r.reason || 'failed'}`;
}
async function selectAllSeg() {
  const all = SEG_META.map((s) => s.key);
  segSel.value = all;
  const r = await post('/api/trading/online/control', { action: 'segments', market: 'CRYPTO', segments: all });
  msg.value = r.ok !== false ? 'All 4 segments on ✓' : `Segments: ${r.reason || 'failed'}`;
}

const isLive = computed(() => params.value.mode === 'live' || params.value.dry_run === false);
const isFut = computed(() => params.value.segment === 'futures');

onMounted(() => { load(); timer = window.setInterval(load, 8000); });
onUnmounted(() => { if (timer) clearInterval(timer); });
</script>

<template>
  <div class="flex gap-3 flex-wrap items-end p-2 rounded border border-neutral-300 dark:border-neutral-700 text-xs">
    <span class="font-bold text-sm me-1">🧠 Crypto Controls</span>
    <span :class="isLive ? 'text-red-500' : 'text-green-500'" class="font-bold">{{ isLive ? 'LIVE 💵' : 'PAPER' }}</span>
    <span class="text-amber-500 font-bold">{{ (params.segment || 'spot').toUpperCase() }}</span>

    <!-- trade-type SEGMENT buttons — multi-select; every selected segment trades on the ONE
         shared paper wallet. Wired to the dashboard's persisted segment registry. -->
    <span class="flex gap-1 items-center flex-wrap">
      <button v-for="s in SEG_META" :key="s.key"
        class="px-2 py-1 rounded border font-bold"
        :class="segSel.includes(s.key) ? 'border-sky-400 text-sky-300 bg-sky-950' : 'border-neutral-600 text-neutral-500'"
        :title="`${s.key} — ${s.note}; click to toggle`"
        @click="toggleSeg(s.key)">{{ s.label }}</button>
      <button class="px-2 py-1 rounded border border-dashed border-sky-400 text-sky-400"
        title="Select all four segments" @click="selectAllSeg">All 4</button>
      <span class="text-neutral-500">{{ segSel.length }}/4</span>
      <button class="px-2 py-1 rounded border font-bold"
        :class="brainUnlimited ? 'border-violet-400 text-violet-300 bg-violet-950 animate-pulse' : 'border-neutral-600 text-neutral-500'"
        title="AI Brain unlimited mode (PAPER): the brain manages balance/caps itself — wallet auto-tops-up, budgets uncapped, learning never halts. Turn OFF to restore your manual values."
        @click="toggleBrainUnlimited">🤖 AI Brain {{ brainUnlimited ? 'ON' : 'OFF' }}</button>
    </span>

    <label class="flex flex-col gap-0.5">Paper balance (USDT)
      <span class="flex gap-1"><input v-model="inp.paper_balance" type="number" step="1000" class="w-24 px-1 py-0.5 rounded border border-neutral-400 bg-transparent" /><button class="px-2 rounded border" @click="applyParam({ paper_balance: Number(inp.paper_balance) }, 'Paper balance')">Set</button></span></label>
    <label class="flex flex-col gap-0.5">Max open trades
      <span class="flex gap-1"><input v-model="inp.max_open_trades" type="number" class="w-16 px-1 py-0.5 rounded border border-neutral-400 bg-transparent" /><button class="px-2 rounded border" @click="applyParam({ max_open_trades: Number(inp.max_open_trades) }, 'Max open')">Set</button></span></label>
    <label class="flex flex-col gap-0.5">Min capital (USDT)
      <span class="flex gap-1"><input v-model="inp.stake_amount" type="number" step="50" class="w-20 px-1 py-0.5 rounded border border-neutral-400 bg-transparent" /><button class="px-2 rounded border" @click="applyParam({ stake_amount: Number(inp.stake_amount) }, 'Stake')">Set</button></span></label>
    <label class="flex flex-col gap-0.5">Leverage (x)
      <span class="flex gap-1"><input v-model="inp.leverage" type="number" class="w-14 px-1 py-0.5 rounded border border-neutral-400 bg-transparent" /><button class="px-2 rounded border" @click="applyParam({ leverage: Number(inp.leverage) }, 'Leverage')">Set</button></span></label>

    <button class="px-2 py-1 rounded border border-amber-500 text-amber-500 font-bold" @click="isFut ? switchMode({ segment: 'spot' }, '→ Spot') : switchMode({ segment: 'futures' }, '→ Futures', 'Switch CRYPTO to FUTURES (perp, shorting)? Bot restarts.')">{{ isFut ? '→ Spot' : '→ Futures' }}</button>
    <button class="px-2 py-1 rounded border font-bold" :class="isLive ? 'border-green-500 text-green-500' : 'border-red-500 text-red-500'" @click="isLive ? switchMode({ mode: 'paper' }, '→ Paper') : switchMode({ mode: 'live', confirm: true }, '→ LIVE', 'Switch CRYPTO to LIVE (REAL MONEY)? Bot restarts and trades real funds.')">{{ isLive ? '→ Paper' : '→ LIVE 💵' }}</button>

    <button class="px-2 py-1 rounded border border-red-500 text-red-500 font-bold"
      title="Permanently delete ALL closed trades (brain journal + Freqtrade) so the brain doesn't learn on contaminated data. Backs up first; OPEN trades untouched."
      @click="resetClosed">⟲ Reset closed trades</button>

    <span v-if="msg" class="px-2 py-0.5 rounded border text-neutral-400">{{ msg }}</span>

    <!-- candle-data refresh indicator (continuous OHLCV updater) -->
    <span class="px-2 py-0.5 rounded border text-xs flex items-center gap-1"
      :class="candle.state === 'updating' ? 'border-sky-500 text-sky-400'
        : candle.state === 'idle' ? 'border-green-600 text-green-500'
        : candle.state === 'error' ? 'border-red-500 text-red-500' : 'border-neutral-600 text-neutral-500'"
      :title="candle.state ? `candles · ${candle.pairs || '?'} pairs · ${(candle.timeframes||[]).join(' ')} · ${candle.days||'?'}d` : 'candle updater not running'">
      🕯
      <template v-if="candle.state === 'updating'">candles: updating… <span class="animate-pulse">●</span></template>
      <template v-else-if="candle.state === 'idle'">candles: updated {{ candleAgo }}</template>
      <template v-else-if="candle.state === 'error'">candles: error</template>
      <template v-else>candles: off</template>
    </span>
  </div>
</template>
