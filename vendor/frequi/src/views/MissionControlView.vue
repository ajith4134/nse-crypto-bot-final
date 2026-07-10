<script setup lang="ts">
// mlnb BN-U2 "Mission Control" (2026-07-10, owner-approved) — the brain's dashboard
// panels as NATIVE FreqUI tabs, one URL for everything. Data honesty: Brain + Funnel
// tabs read same-origin /api/v1/mlnb/* (engine-served); School + Sandbox live only on
// the MLNetworkBrain dashboard (:8000 / tunnel), reached via the shared mlnbDash
// composable — an unreachable dashboard renders as exactly that, never as fake tiles.
const { dashUrl, dashJson } = useMlnbDash();

const TABS = [
  { key: 'brain', label: '🧠 Brain' },
  { key: 'funnel', label: '🌪 Funnel' },
  { key: 'school', label: '🏫 App School' },
  { key: 'sandbox', label: '🧪 Sandbox' },
] as const;
const tab = ref<string>('brain');

// ── School (dashboard /api/trading/app_school) ────────────────────────────────
const school = ref<any | null>(null);
const schoolLooked = ref(false);
async function loadSchool() {
  school.value = await dashJson('/api/trading/app_school');
  schoolLooked.value = true;
}
const schoolBrokers = computed(() => {
  const m = school.value?.map || {};
  return Object.keys(m).map((broker) => ({ broker, ...m[broker] }));
});

// ── Sandbox (dashboard /api/trading/sandbox) ──────────────────────────────────
const sandbox = ref<any | null>(null);
const sandboxLooked = ref(false);
async function loadSandbox() {
  sandbox.value = await dashJson('/api/trading/sandbox');
  sandboxLooked.value = true;
}
const sandboxStats = computed<Array<[string, string]>>(() => {
  const s = sandbox.value;
  if (!s) return [];
  const money = (v: unknown) => (v == null ? '–' : Number(v).toFixed(2));
  return [
    ['Equity', money(s.equity)],
    ['Balance', money(s.balance)],
    ['Used margin', money(s.used_margin)],
    ['Unrealized P&L', money(s.unrealized_pnl)],
    ['Realized P&L', money(s.realized_pnl)],
    ['Open trades', String(s.open_trades ?? '–')],
    ['Closed', String(s.closed_count ?? '–')],
    ['Win rate', s.win_rate != null ? `${(Number(s.win_rate) * 100).toFixed(1)}%` : '–'],
    ['Cycles', String(s.cycles ?? '–')],
    ['Signal mode', String(s.signal_mode ?? '–')],
  ];
});

let timer: number | undefined;
function refreshActive() {
  if (tab.value === 'school') loadSchool();
  if (tab.value === 'sandbox') loadSandbox();
}
watch(tab, refreshActive);
onMounted(() => {
  refreshActive();
  timer = window.setInterval(refreshActive, 20000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <div class="flex flex-col h-full p-2 gap-2 text-sm">
    <div class="flex items-center gap-1 flex-wrap">
      <button
        v-for="t in TABS"
        :key="t.key"
        class="px-3 py-1 rounded border text-xs"
        :class="
          tab === t.key
            ? 'border-cyan-500 bg-cyan-950/60 text-cyan-200'
            : 'border-neutral-700 text-neutral-400 hover:text-neutral-200'
        "
        @click="tab = t.key"
      >
        {{ t.label }}
      </button>
      <span class="ms-auto text-xs text-neutral-500" :title="dashUrl">
        brain dashboard: {{ dashUrl.replace(/^https?:\/\//, '') }}
      </span>
    </div>

    <!-- BRAIN: same-origin mind-events feed (engine /api/v1/mlnb/feed) -->
    <div v-if="tab === 'brain'" class="flex-1 min-h-0 border border-neutral-800 rounded">
      <BrainFeed />
    </div>

    <!-- FUNNEL: per-segment live tiles (engine /api/v1/mlnb/funnel + open trades) -->
    <div v-else-if="tab === 'funnel'" class="flex-1 min-h-0 border border-neutral-800 rounded">
      <BrainSegmentsRail />
    </div>

    <!-- APP SCHOOL: broker-app learning coverage (dashboard API) -->
    <div v-else-if="tab === 'school'" class="flex-1 min-h-0 overflow-y-auto">
      <div v-if="!schoolLooked" class="text-neutral-500 p-2">loading app school…</div>
      <div v-else-if="!school?.available" class="text-neutral-500 p-2">
        brain dashboard unreachable at {{ dashUrl }} — App School data lives there
      </div>
      <template v-else>
        <div class="text-xs text-neutral-400 px-1 pb-2">
          session: {{ school.stats?.clicks ?? 0 }} clicks ·
          {{ school.stats?.explorations ?? 0 }} explorations ·
          {{ school.stats?.routes_learned ?? 0 }} routes learned
        </div>
        <div class="grid gap-2 md:grid-cols-2">
          <div
            v-for="b in schoolBrokers"
            :key="b.broker"
            class="border border-neutral-800 rounded p-2"
          >
            <div class="flex justify-between items-baseline">
              <span class="font-semibold uppercase">{{ b.broker }}</span>
              <span :class="b.pct >= 100 ? 'text-green-400' : 'text-amber-400'">
                {{ b.pct ?? 0 }}% learned
              </span>
            </div>
            <div class="text-xs text-neutral-400 mt-1">
              {{ b.pages_found ?? 0 }} pages · {{ b.links_found ?? 0 }} links ·
              {{ Object.keys(b.routes || {}).length }} data routes
            </div>
            <div class="text-xs mt-1 flex flex-wrap gap-1">
              <span
                v-for="g in b.learned || []"
                :key="g"
                class="px-1 rounded bg-green-950/60 text-green-300 border border-green-900"
                >{{ g }}</span
              >
              <span
                v-for="g in b.missing || []"
                :key="g"
                class="px-1 rounded bg-neutral-900 text-neutral-500 border border-neutral-800"
                >{{ g }} ✗</span
              >
            </div>
            <details class="mt-1 text-xs text-neutral-400">
              <summary class="cursor-pointer">learned routes</summary>
              <div
                v-for="(r, goal) in b.routes || {}"
                :key="goal"
                class="py-0.5 border-b border-neutral-900"
              >
                <span class="text-neutral-200">{{ goal }}</span>
                <span class="text-neutral-500"> ← {{ r.endpoint || r.url }} (×{{ r.n }})</span>
              </div>
            </details>
          </div>
        </div>
      </template>
    </div>

    <!-- SANDBOX: the in-dashboard paper sim on the real per-coin brain engine -->
    <div v-else-if="tab === 'sandbox'" class="flex-1 min-h-0 overflow-y-auto">
      <div v-if="!sandboxLooked" class="text-neutral-500 p-2">loading sandbox…</div>
      <div v-else-if="!sandbox?.available" class="text-neutral-500 p-2">
        brain dashboard unreachable at {{ dashUrl }} — Sandbox data lives there
      </div>
      <template v-else>
        <div class="text-xs px-1 pb-1" :class="sandbox.enabled ? 'text-green-400' : 'text-neutral-500'">
          {{ sandbox.enabled ? '● running' : '○ not the active engine' }} —
          {{ sandbox.note || 'learning sandbox' }}
        </div>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-2 p-1">
          <div
            v-for="[k, v] in sandboxStats"
            :key="k"
            class="border border-neutral-800 rounded p-2"
          >
            <div class="text-neutral-500 text-xs">{{ k }}</div>
            <div class="text-base">{{ v }}</div>
          </div>
        </div>
        <table v-if="(sandbox.open || []).length" class="w-full text-xs mt-2">
          <thead class="text-neutral-500 text-left">
            <tr>
              <th class="p-1">Symbol</th>
              <th class="p-1">Side</th>
              <th class="p-1">Entry</th>
              <th class="p-1">Last</th>
              <th class="p-1">P&L %</th>
              <th class="p-1">Peak %</th>
              <th class="p-1">Lock %</th>
              <th class="p-1">Exit by</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="t in sandbox.open"
              :key="t.symbol"
              class="border-t border-neutral-900"
            >
              <td class="p-1">{{ t.symbol }}</td>
              <td class="p-1" :class="t.side === 'long' ? 'text-green-400' : 'text-red-400'">
                {{ t.side }}
              </td>
              <td class="p-1">{{ t.entry }}</td>
              <td class="p-1">{{ t.price }}</td>
              <td class="p-1" :class="(t.pnl_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ t.pnl_pct != null ? t.pnl_pct.toFixed(2) : '–' }}
              </td>
              <td class="p-1">{{ t.peak_pct != null ? t.peak_pct.toFixed(2) : '–' }}</td>
              <td class="p-1">
                {{ t.tailgate_locked_pct != null ? t.tailgate_locked_pct.toFixed(2) : '–' }}
              </td>
              <td class="p-1 text-neutral-400">{{ t.exit_by }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="text-neutral-500 text-xs p-2">no open sandbox positions</div>
      </template>
    </div>
  </div>
</template>
