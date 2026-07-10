<script setup lang="ts">
import type { GridItemData } from '@/types';
import type { TabsItem } from '@nuxt/ui';

const botStore = useBotStore();
const layoutStore = useLayoutStore();
const settingsStore = useSettingsStore();
const currentBreakpoint = ref('');

const breakpointChanged = (newBreakpoint: string) => {
  // console.log('breakpoint:', newBreakpoint);
  currentBreakpoint.value = newBreakpoint;
};
const isResizableLayout = computed(() =>
  ['', 'sm', 'md', 'lg', 'xl'].includes(currentBreakpoint.value),
);
const isLayoutLocked = computed(() => {
  return layoutStore.layoutLocked || !isResizableLayout.value;
});
const gridLayoutData = computed((): GridItemData[] => {
  if (isResizableLayout.value) {
    return layoutStore.tradingLayout;
  }
  return [...layoutStore.getTradingLayoutSm];
});

const gridLayoutMultiPane = computed(() => {
  return findGridLayout(gridLayoutData.value, TradeLayout.multiPane);
});

const gridLayoutOpenTrades = computed(() => {
  return findGridLayout(gridLayoutData.value, TradeLayout.openTrades);
});

const gridLayoutTradeHistory = computed(() => {
  return findGridLayout(gridLayoutData.value, TradeLayout.tradeHistory);
});

const gridLayoutTradeDetail = computed(() => {
  return findGridLayout(gridLayoutData.value, TradeLayout.tradeDetail);
});

const gridLayoutChartView = computed(() => {
  return findGridLayout(gridLayoutData.value, TradeLayout.chartView);
});

// mlnb Brain Cockpit panels (owner-approved direction A, 2026-07-10)
const gridLayoutBrainSegments = computed(() => {
  return findGridLayout(gridLayoutData.value, TradeLayout.brainSegments);
});
const gridLayoutBrainFeed = computed(() => {
  return findGridLayout(gridLayoutData.value, TradeLayout.brainFeed);
});

const responsiveGridLayouts = computed(() => {
  return {
    sm: layoutStore.getTradingLayoutSm,
  };
});

// MLNetworkBrain: selectable chart timeframe (overrides the strategy default for the Trade chart)
const chartTf = ref<string>('');
const effectiveTf = computed(() => chartTf.value || botStore.activeBot.timeframe);
function refreshOHLCV(pair: string, columns: string[]) {
  botStore.activeBot.getPairCandles({
    pair: pair,
    timeframe: effectiveTf.value,
    columns: columns,
  });
}
// refetch the plotted pairs at the new timeframe when the dropdown changes
const _plotStore = usePlotConfigStore();
watch(chartTf, () => {
  const pairs = botStore.activeBot.plotMultiPairs?.length
    ? botStore.activeBot.plotMultiPairs
    : [botStore.activeBot.selectedPair];
  for (const pair of pairs) {
    if (pair) refreshOHLCV(pair, _plotStore.usedColumns);
  }
});

const tradingTabItems = computed<TabsItem[]>(() => {
  const showText = settingsStore.multiPaneButtonsShowText;
  return [
    {
      slot: 'pairs',
      value: 'pairs',
      label: showText ? 'Pairs combined' : undefined,
      icon: 'i-mdi-view-list',
    },
    {
      slot: 'general',
      value: 'general',
      label: showText ? 'General' : undefined,
      icon: 'i-mdi-information',
    },
    {
      slot: 'performance',
      value: 'performance',
      label: showText ? 'Performance' : undefined,
      icon: 'i-mdi-chart-line',
    },
    {
      slot: 'balance',
      value: 'balance',
      label: showText ? 'Balance' : undefined,
      icon: 'i-mdi-bank',
    },
    {
      slot: 'time-breakdown',
      value: 'time-breakdown',
      label: showText ? 'Time Breakdown' : undefined,
      icon: 'i-mdi-folder-clock',
    },
    {
      slot: 'pairlist',
      value: 'pairlist',
      label: showText ? 'Pairlist' : undefined,
      icon: 'i-mdi-format-list-group',
    },
    {
      slot: 'pair-locks',
      value: 'pair-locks',
      label: showText ? 'Pair Locks' : undefined,
      icon: 'i-mdi-lock-alert',
    },
  ];
});
</script>

<template>
  <GridLayout
    class="h-full w-full"
    style="padding: 1px"
    :row-height="50"
    :layout="gridLayoutData"
    :vertical-compact="false"
    :margin="[1, 1]"
    :responsive-layouts="responsiveGridLayouts"
    :is-resizable="!isLayoutLocked"
    :is-draggable="!isLayoutLocked"
    :responsive="true"
    :cols="{ lg: 12, md: 12, sm: 12, xs: 4, xxs: 2 }"
    :col-num="12"
    @update:breakpoint="breakpointChanged"
  >
    <template #default="{ gridItemProps }">
      <GridItem
        v-if="gridLayoutBrainSegments.h !== 0"
        v-bind="gridItemProps"
        :i="gridLayoutBrainSegments.i"
        :x="gridLayoutBrainSegments.x"
        :y="gridLayoutBrainSegments.y"
        :w="gridLayoutBrainSegments.w"
        :h="gridLayoutBrainSegments.h"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Brain Segments">
          <BrainSegmentsRail />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-if="gridLayoutBrainFeed.h !== 0"
        v-bind="gridItemProps"
        :i="gridLayoutBrainFeed.i"
        :x="gridLayoutBrainFeed.x"
        :y="gridLayoutBrainFeed.y"
        :w="gridLayoutBrainFeed.w"
        :h="gridLayoutBrainFeed.h"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Brain Feed">
          <BrainFeed />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-if="gridLayoutMultiPane.h !== 0"
        v-bind="gridItemProps"
        :i="gridLayoutMultiPane.i"
        :x="gridLayoutMultiPane.x"
        :y="gridLayoutMultiPane.y"
        :w="gridLayoutMultiPane.w"
        :h="gridLayoutMultiPane.h"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Multi Pane">
          <div class="mt-1 flex justify-center">
            <BotControls class="mt-1 mb-2" />
          </div>
          <MlnbControls class="mb-2" />
          <UTabs color="neutral" :items="tradingTabItems" variant="link" default-value="pairs">
            <template #pairs>
              <PairSummary
                :pairlist="botStore.activeBot.whitelist"
                :current-locks="botStore.activeBot.activeLocks"
                :trades="botStore.activeBot.openTrades"
              />
            </template>
            <template #general>
              <BotStatus />
            </template>
            <template #performance>
              <BotPerformance />
            </template>
            <template #balance>
              <BotBalance />
            </template>
            <template #time-breakdown>
              <PeriodBreakdown />
            </template>
            <template #pairlist>
              <PairListLive />
            </template>
            <template #pair-locks>
              <PairLockList />
            </template>
          </UTabs>
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-if="gridLayoutOpenTrades.h !== 0"
        v-bind="gridItemProps"
        :i="gridLayoutOpenTrades.i"
        :x="gridLayoutOpenTrades.x"
        :y="gridLayoutOpenTrades.y"
        :w="gridLayoutOpenTrades.w"
        :h="gridLayoutOpenTrades.h"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Open Trades">
          <TradeList
            class="open-trades"
            :trades="botStore.activeBot.openTrades"
            title="Open trades"
            :active-trades="true"
            empty-text="Currently no open trades."
          />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-if="gridLayoutTradeHistory.h !== 0"
        v-bind="gridItemProps"
        :i="gridLayoutTradeHistory.i"
        :x="gridLayoutTradeHistory.x"
        :y="gridLayoutTradeHistory.y"
        :w="gridLayoutTradeHistory.w"
        :h="gridLayoutTradeHistory.h"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Closed Trades">
          <TradeList
            class="trade-history"
            :trades="botStore.activeBot.closedTrades"
            title="Trade history"
            :show-filter="true"
            empty-text="No closed trades so far."
          />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-if="
          botStore.activeBot.detailTradeId &&
          botStore.activeBot.tradeDetail &&
          gridLayoutTradeDetail.h !== 0
        "
        v-bind="gridItemProps"
        :i="gridLayoutTradeDetail.i"
        :x="gridLayoutTradeDetail.x"
        :y="gridLayoutTradeDetail.y"
        :w="gridLayoutTradeDetail.w"
        :h="gridLayoutTradeDetail.h"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Trade Detail">
          <TradeDetail
            :trade="botStore.activeBot.tradeDetail"
            :stake-currency="botStore.activeBot.stakeCurrency"
          />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-if="gridLayoutTradeDetail.h !== 0"
        v-bind="gridItemProps"
        :i="gridLayoutChartView.i"
        :x="gridLayoutChartView.x"
        :y="gridLayoutChartView.y"
        :w="gridLayoutChartView.w"
        :h="gridLayoutChartView.h"
        :min-h="6"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Chart">
          <div class="flex items-center gap-2 mb-1 px-1">
            <span class="text-xs text-neutral-400">Timeframe</span>
            <TimeframeSelect v-model="chartTf" />
            <span class="text-2xs text-neutral-500">(empty = strategy default {{ botStore.activeBot.timeframe }})</span>
          </div>
          <CandleChartContainer
            :available-pairs="botStore.activeBot.whitelist"
            :historic-view="!!false"
            :timeframe="effectiveTf"
            :trades="botStore.activeBot.allTrades"
            @refresh-data="refreshOHLCV"
          >
          </CandleChartContainer>
        </DraggableContainer>
      </GridItem>
    </template>
  </GridLayout>
</template>
