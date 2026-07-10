<script setup lang="ts">
// mlnb Brain Cockpit — X-RAY (2026-07-10). Entry-time decision context for the selected
// trade: what the brain saw the moment it entered (strategy, direction+confidence,
// psychology read, app signals, eyes coverage). Served same-origin from
// /api/v1/mlnb/xray over crypto_entry_meta.json; honest "no snapshot" when the entry
// predates the sidecar or wasn't brain-driven.
import type { Trade } from '@/types';

const props = defineProps<{ trade: Trade }>();
const botStore = useBotStore();

const meta = ref<Record<string, any> | null>(null);
const looked = ref(false);
const showRaw = ref(false);

async function load() {
  looked.value = false;
  meta.value = null;
  const t = props.trade as any;
  if (!t?.pair || !t?.open_timestamp) {
    looked.value = true;
    return;
  }
  const q = `xray?pair=${encodeURIComponent(t.pair)}&segment=${encodeURIComponent(
    t.bot_segment || 'futures',
  )}&open_ts=${t.open_timestamp}`;
  const res = await botStore.activeBot.getMlnbState(q);
  meta.value = res?.found ? res.meta : null;
  looked.value = true;
}
watch(() => (props.trade as any)?.trade_id, load, { immediate: true });

const rows = computed(() => {
  const m = meta.value;
  if (!m) return [];
  const brain = m.brain || {};
  const psych = m.psychology || {};
  const app = m.app_signals || {};
  const ui = m.decision_snapshot?.ui_view || {};
  const out: Array<[string, string]> = [];
  if (m.strategy) out.push(['Strategy', String(m.strategy)]);
  if (m.direction)
    out.push([
      'Brain call',
      `${m.direction}${brain.confidence != null ? ` @ ${Number(brain.confidence).toFixed(2)}` : ''}`,
    ]);
  if (m.explore) out.push(['Mode', 'explore (learning entry — gates advisory)']);
  if (psych.fear != null) out.push(['Psychology fear', Number(psych.fear).toFixed(2)]);
  if (psych.signal) out.push(['Psychology signal', String(psych.signal)]);
  if (app.vote?.p_up != null) out.push(['App vote p(up)', Number(app.vote.p_up).toFixed(2)]);
  if (ui.n_tfs != null)
    out.push(['Eyes coverage', `${ui.n_tfs} timeframe(s)${ui.ui_only_mode ? ' · UI-only' : ''}`]);
  return out;
});
</script>

<template>
  <div class="text-xs p-1">
    <div class="font-semibold mb-1">🧠 Brain X-Ray (entry-time)</div>
    <div v-if="!looked" class="text-neutral-500">loading…</div>
    <div v-else-if="!meta" class="text-neutral-500">
      no entry snapshot recorded for this trade (pre-sidecar entry or non-brain entry)
    </div>
    <template v-else>
      <div v-for="[k, v] in rows" :key="k" class="flex justify-between gap-2 py-0.5">
        <span class="text-neutral-400">{{ k }}</span>
        <span class="text-right">{{ v }}</span>
      </div>
      <button class="text-neutral-500 underline mt-1" @click="showRaw = !showRaw">
        {{ showRaw ? 'hide' : 'show' }} full snapshot
      </button>
      <pre
        v-if="showRaw"
        class="mt-1 max-h-64 overflow-auto bg-neutral-900 rounded p-1 whitespace-pre-wrap"
        >{{ JSON.stringify(meta, null, 1) }}</pre
      >
    </template>
  </div>
</template>
