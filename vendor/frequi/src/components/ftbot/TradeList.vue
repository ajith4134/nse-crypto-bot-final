<script setup lang="ts">
import { getPaginationRowModel } from '@tanstack/vue-table';
import type { TableColumn, TableRow } from '@nuxt/ui';
import type { MultiDeletePayload, MultiForceExitPayload, Trade } from '@/types';

import { useRouter } from 'vue-router';

const props = withDefaults(
  defineProps<{
    trades: Trade[];
    title?: string;
    stakeCurrency?: string;
    activeTrades?: boolean;
    showFilter?: boolean;
    multiBotView?: boolean;
    emptyText?: string;
  }>(),
  {
    title: 'Trades',
    stakeCurrency: '',
    activeTrades: false,
    showFilter: false,
    multiBotView: false,
    emptyText: 'No Trades to show.',
  },
);

const botStore = useBotStore();
const router = useRouter();
const settingsStore = useSettingsStore();
const tradesTable = useTemplateRef('tradesTable');
const filterText = ref('');
const perPage = props.activeTrades ? 200 : 15;
const pagination = ref({ pageIndex: 0, pageSize: perPage });
const { confirm } = useConfirmBox();
const { forceEntryDialog, forceExitDialog } = useForceTrade();

function formatPriceWithDecimals(price: number) {
  return formatPrice(price, botStore.activeBot.stakeCurrencyDecimals);
}

// Round-trip fee cost actually paid (open + close legs), in stake currency.
function tradeFees(trade: Trade): number {
  return (trade.fee_open_cost ?? 0) + (trade.fee_close_cost ?? 0);
}
// Peak favorable / adverse excursion (MFE / MAE) as leverage-aware ratios, derived from
// the trade's recorded max_rate / min_rate vs entry. A real price-excursion analytic — it
// tracks how far price ran in each direction (fees excluded), not realized P&L.
// Clamped with the live profit_ratio so the invariant peak ≥ current ≥ trough always holds
// on screen: max/min_rate lag one bot iteration and exclude fees, so without the clamp the
// current profit could read above the peak (or below the trough) — impossible to a reader.
function peakProfit(trade: Trade): { mfe: number | null; mae: number | null } {
  const open = trade.open_rate;
  const lev = trade.leverage ?? 1;
  if (!open || trade.max_rate == null || trade.min_rate == null) return { mfe: null, mae: null };
  let { mfe, mae } = trade.is_short
    ? { mfe: ((open - trade.min_rate) / open) * lev, mae: ((open - trade.max_rate) / open) * lev }
    : { mfe: ((trade.max_rate - open) / open) * lev, mae: ((trade.min_rate - open) / open) * lev };
  const cur = trade.profit_ratio;
  if (cur != null) {
    mfe = Math.max(mfe, cur);
    mae = Math.min(mae, cur);
  }
  return { mfe, mae };
}
// Profit tailgate: the brain's ratcheting locked-profit exit. It ARMS once the trade's peak
// favorable excursion (MFE, from the real recorded max_rate) reaches ARM_PCT, then locks in
// profit that ratchets up with the peak (peak − TRAIL_PCT giveback) and never falls back —
// negative trades are handled by the −8% stop, not the tailgate. Same semantics as the sandbox.
// mlnb (2026-07-07, owner ask): the REAL tailgate state — the ratcheting locked floor and
// the trail distance the brain LEARNS from closed outcomes (profit_tailgate.learn, W2-railed)
// — rides the predictions overlay (tg_locked_pct / tg_trail_dist / tg_peak_pct, in % units).
// HONESTY (2026-07-10): when the overlay hasn't loaded there is NO live lock to show — a
// locally fabricated "peak − 0.5%" looked exactly like a brain lock and misled the owner
// into expecting exits the brain never promised. Fallback = unlocked + the local peak only.
function tailgate(trade: Trade): {
  armed: boolean;
  locked: number | null;
  peak: number | null;
  trail: number | null;
} {
  // mlnb E2 (2026-07-10): the engine now serves the live ratchet NATIVELY on every trade
  // row (tg_locked_pct/tg_peak_pct/tg_trail_dist from the same lock file the in-engine
  // custom_exit enforces) — the cross-origin overlay is only a secondary source now.
  const nat = trade as unknown as Record<string, number | null>;
  const ov =
    nat.tg_locked_pct != null
      ? nat
      : (predMap.value[String(trade.trade_id)] as Record<string, number | null> | undefined);
  if (ov && ov.tg_locked_pct != null) {
    return {
      armed: true,
      locked: Number(ov.tg_locked_pct) / 100,
      peak: ov.tg_peak_pct != null ? Number(ov.tg_peak_pct) / 100 : null,
      trail: ov.tg_trail_dist != null ? Number(ov.tg_trail_dist) : null,
    };
  }
  return { armed: false, locked: null, peak: peakProfit(trade).mfe, trail: null };
}
const isFutures = computed(() => botStore.activeBot.botFeatures?.futures ?? false);

// Strategy / Brain / NN prediction live on the MLNetworkBrain dashboard (not Freqtrade's /api/v1),
// so fetch them cross-origin keyed by trade_id and overlay them onto the native table. The dashboard
// url is read from the same-origin overlay (mlnb_status.json) so it tracks the live tunnel.
const predMap = ref<Record<string, { strategy_label?: string; brain_pred?: string; nn_pred?: string }>>({});
let predTimer: number | undefined;
async function loadPredictions() {
  try {
    const s = await (await fetch(`${import.meta.env.BASE_URL}mlnb_status.json?t=${Date.now()}`)).json();
    const dash = String(s?.dashboard_url || '').replace(/\/$/, '');
    if (!dash) return;
    // Dedicated lightweight endpoint (cached, no slow 500-trade peak enrichment); returns a
    // {trade_id: {strategy_label, brain_pred, nn_pred}} map already keyed by the raw freqtrade id.
    const t = await (await fetch(`${dash}/api/trading/crypto/predictions`)).json();
    if (t && t.map) predMap.value = t.map;
  } catch { /* dashboard unreachable — columns show "—" honestly */ }
}
function pred(row: { trade_id?: number | null }) {
  // native engine fields first (strategy_label/brain_pred ride every trade row since E2);
  // the dashboard overlay adds what only IT can compute live (nn_pred re-scoring).
  const nat = (row ?? {}) as Record<string, string | undefined>;
  const ov = predMap.value[String(row?.trade_id ?? '')] || {};
  return {
    strategy_label: nat.strategy_label ?? ov.strategy_label,
    brain_pred: nat.brain_pred ?? ov.brain_pred,
    nn_pred: ov.nn_pred,
  };
}
onMounted(() => { loadPredictions(); predTimer = window.setInterval(loadPredictions, 15000); });
onUnmounted(() => { if (predTimer) clearInterval(predTimer); });

// Total P&L indicator — sum realized/unrealized money across the rows currently shown.
const totalPnl = computed(() =>
  props.trades.reduce((s, t) => s + (Number(t.profit_abs) || 0), 0),
);
const totalPnlCcy = computed(() => props.trades[0]?.quote_currency || props.stakeCurrency || 'USDT');

const tableFields = ref([
  { field: 'trade_id', header: 'ID' },
  { field: 'pair', header: 'Pair' },
  // mlnb: owning segment from the multi-segment fork (futures/spot/options/prediction)
  { field: 'bot_segment', header: 'Segment' },
  { field: 'amount', header: 'Amount' },
  props.activeTrades
    ? { field: 'stake_amount', header: 'Stake amount' }
    : { field: 'max_stake_amount', header: 'Total stake amount' },
  {
    field: 'open_rate',
    header: 'Open rate',
  },
  {
    field: props.activeTrades ? 'current_rate' : 'close_rate',
    header: props.activeTrades ? 'Current rate' : 'Close rate',
  },
  {
    field: 'profit',
    header: props.activeTrades ? 'Current profit %' : 'Profit %',
  },
  { field: 'profit_abs', header: props.activeTrades ? 'P&L ($)' : 'Net P&L ($)' },
  { field: 'peak', header: 'Peak P/L' },
  ...(props.activeTrades ? [{ field: 'tailgate', header: 'Tailgate' }] : []),
  { field: 'fees', header: 'Fees' },
  ...(isFutures.value
    ? [
        ...(props.activeTrades ? [{ field: 'liquidation', header: 'Liq.' }] : []),
        { field: 'funding', header: 'Funding' },
      ]
    : []),
  { field: 'strategy_label', header: 'Strategy' },
  { field: 'brain_pred', header: 'Brain' },
  { field: 'nn_pred', header: 'NN' },
  { field: 'open_timestamp', header: 'Open date' },
  ...(props.activeTrades
    ? [{ field: 'actions', header: '' }]
    : [
        { field: 'close_timestamp', header: 'Close date' },
        { field: 'exit_reason', header: 'Close Reason' },
      ]),
]);

if (props.multiBotView) {
  tableFields.value.unshift({ field: 'botName', header: 'Bot' });
}

const tableColumns = computed<TableColumn<Trade>[]>(() =>
  tableFields.value.map((f) => ({ accessorKey: f.field, header: f.header })),
);

const filteredTrades = computed(() => {
  if (!filterText.value) return props.trades;
  const text = filterText.value.toLowerCase();
  return props.trades.filter(
    (t) =>
      t.pair.toLowerCase().includes(text) ||
      t.exit_reason?.toLowerCase().includes(text) ||
      t.enter_tag?.toLowerCase().includes(text) ||
      (props.multiBotView ? t.botName?.toLowerCase().includes(text) : false),
  );
});

async function forceExitHandler(item: Trade, ordertype: string | undefined = undefined) {
  const message = ordertype
    ? `Really exit trade ${item.trade_id} (Pair ${item.pair}) using a ${ordertype} order?`
    : `Really exit trade ${item.trade_id} (Pair ${item.pair})?`;
  if (
    settingsStore.confirmDialog !== true ||
    (await confirm({
      title: 'Force exit trade',
      description: 'This action cannot be undone.',
      message,
      confirmText: 'Confirm',
    }))
  ) {
    const payload: MultiForceExitPayload = {
      tradeid: String(item.trade_id),
      botId: item.botId,
    };
    if (ordertype) {
      payload.ordertype = ordertype;
    }
    botStore
      .forceSellMulti(payload)
      .then((xxx) => console.log(xxx))
      .catch((error) => console.log(error.response));
  }
}

async function removeTradeHandler(item: Trade) {
  if (
    await confirm({
      title: 'Delete trade',
      description: 'This action cannot be undone.',
      message: `Really delete trade ${item.trade_id} (Pair ${item.pair})?`,
      confirmText: 'Confirm',
    })
  ) {
    const payload: MultiDeletePayload = {
      tradeid: String(item.trade_id),
      botId: item.botId,
    };
    botStore.deleteTradeMulti(payload).catch((error) => console.log(error.response));
  }
}

function forceExitPartialHandler(item: Trade) {
  forceExitDialog({
    trade: item,
    stakeCurrencyDecimals: botStore.activeBot.botState.stake_currency_decimals ?? 3,
  });
}

async function cancelOpenOrderHandler(item: Trade) {
  if (
    await confirm({
      title: 'Cancel open order',
      description: 'This action cannot be undone.',
      message: `Really cancel open order for trade ${item.trade_id} (Pair ${item.pair})?`,
      confirmText: 'Confirm',
    })
  ) {
    const payload: MultiDeletePayload = {
      tradeid: String(item.trade_id),
      botId: item.botId,
    };
    botStore.cancelOpenOrderMulti(payload).catch((error) => console.log(error.response));
  }
}

function reloadTradeHandler(item: Trade) {
  botStore.reloadTradeMulti({ tradeid: String(item.trade_id), botId: item.botId });
}

function handleForceEntry(item: Trade) {
  forceEntryDialog({
    pair: item.pair,
    positionIncrease: true,
  });
}

const onRowClicked = (item: Trade) => {
  if (props.multiBotView && botStore.selectedBot !== item.botId) {
    // Multibotview - on click switch to the bot trade view
    botStore.selectBot(item.botId);
  }
  if (item && item.trade_id !== botStore.activeBot.detailTradeId) {
    botStore.activeBot.setDetailTrade(item);
    if (props.multiBotView) {
      router.push({ name: 'Freqtrade Trading' });
    }
  } else {
    botStore.activeBot.setDetailTrade(null);
  }
};

function onRowSelect(_e: Event, row: TableRow<Trade>) {
  onRowClicked(row.original);
}

const rowSelection = computed({
  get() {
    const selectedTradeIndex = filteredTrades.value.findIndex(
      (t) => String(t.trade_id) === String(botStore.activeBot.detailTradeId),
    );
    if (selectedTradeIndex === -1) return {};
    return { [String(selectedTradeIndex)]: true };
  },
  set() {
    // noop, selection is controlled by activeBot.detailTradeId
  },
});
</script>

<template>
  <div class="h-full overflow-auto w-full mlnb-trade-table">
    <div v-if="trades.length" class="flex justify-end items-center gap-2 px-2 py-1 text-sm">
      <span class="opacity-70">Total {{ activeTrades ? 'unrealized' : 'net' }} P&L:</span>
      <span :class="totalPnl >= 0 ? 'text-green-500' : 'text-red-500'" class="font-semibold">
        {{ totalPnl >= 0 ? '+' : '' }}{{ formatPrice(totalPnl, 3) }} {{ totalPnlCcy }}
      </span>
    </div>
    <UTable
      ref="tradesTable"
      v-model:pagination="pagination"
      :pagination-options="{ getPaginationRowModel: getPaginationRowModel() }"
      :data="filteredTrades"
      :columns="tableColumns"
      class="text-center"
      v-model:row-selection="rowSelection"
      :ui="{
        tr: 'data-[selected=true]:bg-primary/30 dark:data-[selected=true]:bg-primary-700',
      }"
      @select="onRowSelect"
    >
      <template #empty>
        {{ emptyText }}
      </template>
      <template #trade_id-cell="{ row }">
        {{ row.original.trade_id }}
        {{
          botStore.activeBot.botFeatures.futures && row.original.trading_mode !== 'spot'
            ? (row.original.trade_id ? '| ' : '') + (row.original.is_short ? 'Short' : 'Long')
            : ''
        }}
      </template>
      <template #pair-cell="{ row }">
        {{
          `${row.original.pair}${row.original.open_order_id || row.original.has_open_orders ? '*' : ''}`
        }}
      </template>
      <template #actions-cell="{ row }">
        <TradeActionsPopover
          :id="row.original.trade_id ?? row.index"
          :enable-force-entry="botStore.activeBot.botState.force_entry_enable"
          :trade="row.original"
          :bot-features="botStore.activeBot.botFeatures"
          @delete-trade="removeTradeHandler(row.original)"
          @force-exit="forceExitHandler"
          @force-exit-partial="forceExitPartialHandler"
          @cancel-open-order="cancelOpenOrderHandler"
          @reload-trade="reloadTradeHandler"
          @force-entry="handleForceEntry"
        />
      </template>
      <template #stake_amount-cell="{ row }">
        {{ formatPriceWithDecimals(row.original.stake_amount) }}
        {{ row.original.trading_mode !== 'spot' ? `(${row.original.leverage}x)` : '' }}
      </template>
      <template #max_stake_amount-cell="{ row }">
        {{ formatPriceWithDecimals(row.original.max_stake_amount ?? 0) }}
        {{ row.original.trading_mode !== 'spot' ? `(${row.original.leverage}x)` : '' }}
      </template>
      <template #open_rate-cell="{ row }">{{ formatPrice(row.original.open_rate) }}</template>
      <template #current_rate-cell="{ row }">{{
        formatPrice(row.original.current_rate ?? null)
      }}</template>
      <template #close_rate-cell="{ row }">{{
        formatPrice(row.original.close_rate ?? null)
      }}</template>
      <template #amount-cell="{ row }">{{ formatPrice(row.original.amount) }}</template>
      <template #profit-cell="{ row }"><TradeProfit :trade="row.original" /></template>
      <template #profit_abs-cell="{ row }">
        <span :class="(row.original.profit_abs ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'">
          {{ formatPriceCurrency(row.original.profit_abs ?? 0, row.original.quote_currency || 'USDT', 3) }}
        </span>
      </template>
      <template #peak-cell="{ row }">
        <!-- owner 2026-07-17: max profit / max loss in QUOTE (USDT), not % — the MFE/MAE
             ratio × stake_amount is the same money basis as the Profit column's abs value -->
        <span class="text-green-500">{{
          peakProfit(row.original).mfe !== null && row.original.stake_amount != null
            ? formatPriceCurrency(
                (peakProfit(row.original).mfe as number) * row.original.stake_amount,
                row.original.quote_currency || 'USDT',
                2,
              )
            : '–'
        }}</span>
        <span class="opacity-40"> / </span>
        <span class="text-red-500">{{
          peakProfit(row.original).mae !== null && row.original.stake_amount != null
            ? formatPriceCurrency(
                (peakProfit(row.original).mae as number) * row.original.stake_amount,
                row.original.quote_currency || 'USDT',
                2,
              )
            : '–'
        }}</span>
      </template>
      <template #tailgate-cell="{ row }">
        <span v-if="tailgate(row.original).armed" class="text-green-400" title="locked-in profit (ratchets up with the peak, never falls back) · ~N% = the trail rate the lock follows the peak by — LEARNED by the brain from closed outcomes">
          🔒 {{ formatPercent(tailgate(row.original).locked, 1) }}
          <span v-if="tailgate(row.original).trail != null" class="opacity-70 text-xs">
            ~{{ (Number(tailgate(row.original).trail) * 100).toFixed(0) }}%
          </span>
        </span>
        <span v-else class="opacity-40" title="no live brain lock for this trade (arms once peak ≥ +0.5%; shows 🔓 + local peak until the dashboard overlay loads)">
          🔓 {{ tailgate(row.original).peak != null ? formatPercent(tailgate(row.original).peak, 1) : '–' }}
        </span>
      </template>
      <template #fees-cell="{ row }">{{
        formatPriceCurrency(tradeFees(row.original), row.original.quote_currency || 'USDT', 4)
      }}</template>
      <template #liquidation-cell="{ row }">{{
        row.original.liquidation_price ? formatPrice(row.original.liquidation_price) : '–'
      }}</template>
      <template #funding-cell="{ row }">
        <span :class="(row.original.funding_fees ?? 0) <= 0 ? 'text-green-500' : 'text-red-500'">{{
          row.original.funding_fees != null ? formatPrice(row.original.funding_fees, 4) : '–'
        }}</span>
      </template>
      <template #strategy_label-cell="{ row }">
        <span class="text-cyan-400">{{ pred(row.original).strategy_label || '–' }}</span>
      </template>
      <template #brain_pred-cell="{ row }">
        <span :class="String(pred(row.original).brain_pred).startsWith('SHORT') ? 'text-red-400' : 'text-green-400'">{{
          pred(row.original).brain_pred || '–'
        }}</span>
      </template>
      <template #nn_pred-cell="{ row }">
        <span class="text-amber-300">{{ pred(row.original).nn_pred || '–' }}</span>
      </template>
      <template #open_timestamp-cell="{ row }"
        ><DateTimeTZ :date="row.original.open_timestamp"
      /></template>
      <template #close_timestamp-cell="{ row }"
        ><DateTimeTZ :date="row.original.close_timestamp ?? 0"
      /></template>
      <template #exit_reason-cell="{ row }">{{ row.original.exit_reason }}</template>
      <template #botName-cell="{ row }">{{ row.original.botName }}</template>
    </UTable>

    <div v-if="showFilter" class="flex justify-end gap-2 p-2">
      <UInput v-model="filterText" placeholder="Filter" class="w-64" />
    </div>
    <div v-if="!activeTrades" class="flex justify-end border-t border-default pt-2">
      <UPagination
        :page="(tradesTable?.tableApi?.getState().pagination.pageIndex || 0) + 1"
        :items-per-page="tradesTable?.tableApi?.getState().pagination.pageSize"
        :total="tradesTable?.tableApi?.getFilteredRowModel().rows.length ?? 0"
        @update:page="(p) => tradesTable?.tableApi?.setPageIndex(p - 1)"
      />
    </div>
  </div>
</template>

<style scoped>
/* Auto-fit the frame: the table stretches to the panel width and scrolls smoothly when the
   richer column set overflows; rows fade in and transition softly as data updates. */
.mlnb-trade-table {
  scroll-behavior: smooth;
}
.mlnb-trade-table :deep(table) {
  width: 100%;
  min-width: max-content;
}
.mlnb-trade-table :deep(td),
.mlnb-trade-table :deep(th) {
  white-space: nowrap;
  transition: background-color 0.15s ease;
}
.mlnb-trade-table :deep(tbody tr) {
  transition:
    background-color 0.15s ease,
    opacity 0.3s ease;
  animation: mlnb-row-in 0.25s ease both;
}
@keyframes mlnb-row-in {
  from {
    opacity: 0;
    transform: translateY(2px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
