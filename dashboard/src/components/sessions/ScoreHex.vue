<script setup lang="ts">
  import { computed } from 'vue'
  import { seq } from '@/composables/useSeqScale'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { hexPoints } from '@/utils/hex'
  import { SCORE_TIP, scoreFrac } from '@/utils/sessionStory'

  // `ceiling` is the dataset-wide max interest. `interactive` renders a button with the score
  // tooltip but tabindex -1 (never a Tab stop); otherwise a plain role="img" span.
  const {
    interest,
    ceiling,
    interactive = false,
  } = defineProps<{
    interest: number
    ceiling: number
    interactive?: boolean
  }>()

  const TIP = SCORE_TIP

  const frac = computed(() => scoreFrac(interest, ceiling))
  // Glow starts at 60% of the top score; below interest=5 there is too little
  // activity to color, so the hex stays neutral grey.
  const hot = computed(() => frac.value > 0.6)
  const hexFill = computed(() =>
    interest > 5 ? seq(Math.pow(frac.value, 0.9)) : 'var(--surface-2)',
  )
  // Normalized 0-100: the hottest session reads as 100, others scale beneath it.
  const displayScore = computed(() => Math.round(100 * frac.value))
  const points = hexPoints(15, 16.5, 14)

  const tooltip = useHwTooltip()
</script>

<template>
  <component
    :is="interactive ? 'button' : 'span'"
    class="score-hex"
    :class="{ hot, interactive }"
    :type="interactive ? 'button' : undefined"
    :tabindex="interactive ? -1 : undefined"
    :role="interactive ? undefined : 'img'"
    :aria-label="`Interest score ${displayScore} of 100`"
    @pointerenter="interactive && tooltip.show(TIP)"
    @pointermove="interactive && tooltip.move($event as PointerEvent)"
    @pointerleave="interactive && tooltip.hide()"
    @focus="interactive && tooltip.show(TIP)"
    @blur="interactive && tooltip.hide()"
  >
    <svg viewBox="0 0 30 33" aria-hidden="true">
      <polygon
        :points="points"
        :fill="hexFill"
        stroke="var(--border-strong)"
        :stroke-width="interest > 5 ? 0 : 1"
      />
    </svg>
    <b aria-hidden="true">{{ displayScore }}</b>
  </component>
</template>

<style scoped>
  .score-hex {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 26px;
    flex: 0 0 auto;
  }

  .score-hex.interactive {
    appearance: none;
    padding: 0;
    border: none;
    background: transparent;
    font: inherit;
    cursor: pointer;
    width: 26px;
    height: 29px;
  }

  .score-hex.interactive:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: 1px;
    border-radius: var(--radius-sm);
  }

  .score-hex svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .score-hex b {
    position: relative;
    font: 700 10px var(--font-mono);
    color: var(--text);
  }

  .score-hex.interactive b {
    font-weight: 650;
  }

  .score-hex.hot b {
    color: var(--bg-0);
  }
</style>
