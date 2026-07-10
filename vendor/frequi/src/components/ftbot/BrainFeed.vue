<script setup lang="ts">
// mlnb Brain Cockpit — BRAIN FEED (2026-07-10). The brain's own mind-events stream
// (tailgate locks, entries, learnings, boss directives) served same-origin via
// /api/v1/mlnb/feed. Read-only mirror of mind_events.json — honest empty state when
// the brain processes haven't written anything.
const botStore = useBotStore();

interface MindEvent {
  id?: number;
  kind?: string;
  text?: string;
  salience?: number;
  ts?: number | string;
}

const events = ref<MindEvent[]>([]);
const loaded = ref(false);
let timer: number | undefined;

async function refresh() {
  const res = await botStore.activeBot.getMlnbState('feed?limit=60');
  if (res && Array.isArray(res.events)) {
    events.value = [...res.events].reverse(); // newest first
  }
  loaded.value = true;
}
onMounted(() => {
  refresh();
  timer = window.setInterval(refresh, 10000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});

const KIND_ICON: Record<string, string> = {
  trade_credit: '💰',
  learning: '📚',
  thought: '💭',
  warning: '⚠️',
  boss: '🧑‍✈️',
};

function fmtTs(ts: number | string | undefined): string {
  if (!ts) return '';
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString();
}
</script>

<template>
  <div class="h-full overflow-y-auto p-1 text-xs">
    <div v-if="!loaded" class="text-neutral-500 p-2">loading brain feed…</div>
    <div v-else-if="events.length === 0" class="text-neutral-500 p-2">
      no brain events yet — the feed fills as the loops run
    </div>
    <div
      v-for="ev in events"
      :key="ev.id ?? `${ev.ts}-${ev.text}`"
      class="border-b border-neutral-800 py-1 flex gap-1"
      :class="(ev.salience ?? 0) >= 0.7 ? '' : 'opacity-75'"
    >
      <span>{{ KIND_ICON[ev.kind ?? ''] ?? '·' }}</span>
      <span class="flex-1">{{ ev.text }}</span>
      <span class="text-neutral-500 whitespace-nowrap">{{ fmtTs(ev.ts) }}</span>
    </div>
  </div>
</template>
