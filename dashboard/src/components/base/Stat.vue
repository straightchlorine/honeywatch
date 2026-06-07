<script setup lang="ts">
  import { computed } from 'vue'

  type Trend = 'up' | 'down' | 'neutral'

  /**
   * Trend is caller-supplied semantics, not derived from delta. The caller decides
   * whether an upward delta is "good" (up) or "bad" (down) for the metric.
   */
  const props = defineProps<{
    value: number | string
    label: string
    trend?: Trend
    delta?: string
  }>()

  const deltaClass = computed(() => {
    if (!props.trend) return ''
    return `trend-${props.trend}`
  })

  // Non-color cues so trend direction is not conveyed by color alone (WCAG 1.4.1).
  const trendSymbol = computed(() =>
    props.trend === 'up' ? '▲' : props.trend === 'down' ? '▼' : '',
  )
  const trendWord = computed(() =>
    props.trend === 'up' ? 'increase' : props.trend === 'down' ? 'decrease' : '',
  )
</script>

<template>
  <div class="stat">
    <div class="stat-line">
      <span class="stat-value">{{ value }}</span>
      <span v-if="delta" class="stat-delta" :class="deltaClass">
        <span v-if="trendSymbol" class="stat-trend-symbol" aria-hidden="true">{{
          trendSymbol
        }}</span>
        <span v-if="trendWord" class="visually-hidden">{{ trendWord }}: </span>{{ delta }}
      </span>
    </div>
    <span class="stat-label">{{ label }}</span>
  </div>
</template>

<style scoped>
  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-line {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    /* Wrap the delta below the value when the card is too narrow (Activity packs
       a long "N sessions" delta on every card); without this the no-shrink delta
       + big value overflow the 2-col mobile grid and scroll the whole page. */
    column-gap: var(--space-2);
    row-gap: 2px;
  }

  .stat-value {
    font-size: 36px;
    line-height: 1;
    font-weight: 700;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
  }

  .stat-label {
    color: var(--text-muted);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 500;
  }

  .stat-delta {
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    flex-shrink: 0;
    /* Never split the delta mid-string: the symbol, count and percentage stay
       together as one unit. It still wraps below the value as a whole (the
       flex-wrap on .stat-line) on narrow cards, but the "(+1.8k%)" can no
       longer drop onto its own line and inflate the card height. */
    white-space: nowrap;
  }

  .stat-trend-symbol {
    margin-right: 2px;
  }

  .trend-up {
    color: var(--success);
  }

  .trend-down {
    color: var(--error);
  }

  .trend-neutral {
    color: var(--text-muted);
  }

  @media (max-width: 768px) {
    /* Smaller hero number on mobile so it shares the narrow 2-col card with the
       delta without forcing a wrap (e.g. "May 30" peak-day value). */
    .stat-value {
      font-size: 30px;
    }
  }
</style>
