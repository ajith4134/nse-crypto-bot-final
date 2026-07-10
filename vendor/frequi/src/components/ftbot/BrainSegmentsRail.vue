<script setup lang="ts">
// mlnb Brain Cockpit — SEGMENTS rail (2026-07-10, owner-approved direction A).
// Live per-segment tiles built from REAL data only: open trades grouped by bot_segment
// (count + unrealized P&L) and the funnel's last-cycle report per segment (entered /
// skipped + skip reasons — the honest "why nothing happened" the owner asked for after
// options ran silent for 4.5h). No fabricated values: a segment with no data says so.
const botStore = useBotStore();

const funnel = ref<Record<string, any> | null>(null);
let timer: number | undefined;
async function refresh() {
  const res = await botStore.activeBot.getMlnbState('funnel');
  funnel.value = res?.status ?? null;
}
onMounted(() => {
  refresh();
  timer = window.setInterval(refresh, 15000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});

const KNOWN_SEGMENTS = ['futures', 'spot', 'options', 'prediction'];

const tiles = computed(() => {
  const groups: Record<string, { count: number; pnl: number }> = {};
  for (const t of botStore.activeBot.openTrades) {
    const seg = ((t as any).bot_segment || 'futures') as string;
    groups[seg] = groups[seg] || { count: 0, pnl: 0 };
    groups[seg].count += 1;
    groups[seg].pnl += Number((t as any).profit_abs ?? 0) || 0;
  }
  // funnel reports: broker_sense_status.json keys markets; "crypto:<segment>" entries
  // come from the extra-segment drivers, plain "crypto" is the last main-cycle report.
  const reports: Record<string, any> = {};
  for (const [key, rep] of Object.entries(funnel.value || {})) {
    if (!rep || typeof rep !== 'object') continue;
    const seg = (rep as any).segment || key.split(':')[1];
    if (seg) reports[seg] = rep;
  }
  const segs = new Set([...KNOWN_SEGMENTS, ...Object.keys(groups)]);
  return [...segs].map((seg) => {
    const rep = reports[seg];
    const ex = rep?.stages?.execute ?? rep ?? {};
    return {
      seg,
      count: groups[seg]?.count ?? 0,
      pnl: groups[seg]?.pnl ?? 0,
      entered: Array.isArray(ex.entered) ? ex.entered.length : null,
      skipped: typeof ex.skipped === 'number' ? ex.skipped : null,
      reasons: ex.skip_reasons && Object.keys(ex.skip_reasons).length ? ex.skip_reasons : null,
      cycleTs: rep?.ts ?? null,
    };
  });
});

function fmtReasons(reasons: Record<string, number>): string {
  return Object.entries(reasons)
    .map(([k, v]) => `${k.replace(/_/g, ' ')} ×${v}`)
    .join(' · ');
}
</script>

<template>
  <div class="flex flex-col gap-1 p-1 overflow-y-auto h-full">
    <div
      v-for="t in tiles"
      :key="t.seg"
      class="rounded border border-neutral-700 px-2 py-1 text-xs"
      :class="t.count > 0 ? 'bg-neutral-800/60' : 'opacity-60'"
    >
      <div class="flex justify-between items-baseline">
        <span class="font-semibold uppercase tracking-wide">{{ t.seg }}</span>
        <span :class="t.pnl >= 0 ? 'text-green-400' : 'text-red-400'">
          {{ t.count }} open · {{ t.pnl >= 0 ? '+' : '' }}{{ t.pnl.toFixed(2) }}
        </span>
      </div>
      <div v-if="t.entered !== null || t.skipped !== null" class="text-neutral-400 mt-0.5">
        last cycle: {{ t.entered ?? 0 }} entered<span v-if="t.skipped !== null">
          · {{ t.skipped }} skipped</span
        >
      </div>
      <div
        v-if="t.reasons"
        class="text-neutral-500 mt-0.5"
        title="why the brain skipped candidates last cycle"
      >
        {{ fmtReasons(t.reasons) }}
      </div>
      <div v-if="t.entered === null && t.count === 0" class="text-neutral-500 mt-0.5">
        no cycle report yet
      </div>
    </div>
  </div>
</template>
