<script setup lang="ts">
  // The sessions pages' count chip: an elongated hexagon (the honeycomb cell, stretched) with a
  // bold numeral and a small glyph saying what was counted. Border and fill are two clipped layers.
  import { ICONS } from '@/components/icons'
  import { useHwTooltip } from '@/composables/useHwTooltip'

  // glyph: shown instead of the slot's words on phones (the caller supplies title + aria-label).
  // iconOnly: the glyph replaces the words at any width.
  const {
    tone = 'amber',
    icon,
    glyph,
    iconOnly = false,
    title,
  } = defineProps<{
    tone?: 'amber' | 'ok' | 'bad' | 'dim'
    icon?: keyof typeof ICONS
    glyph?: keyof typeof ICONS
    iconOnly?: boolean
    // Shown in the honeywatch tooltip on hover; taken as a prop so no native title bubble appears.
    title?: string
  }>()

  const tt = useHwTooltip()
</script>

<template>
  <span
    class="chip"
    :class="[tone, { glyphed: glyph, only: glyph && iconOnly }]"
    :role="glyph || $attrs['aria-label'] ? 'img' : undefined"
    @pointerenter="title && tt.showAt($event.currentTarget as Element, title)"
    @pointerleave="title && tt.hide()"
  >
    <span :class="{ word: glyph }"><slot /></span>
    <svg v-if="glyph" class="chip-icon glyph" viewBox="0 0 24 24" aria-hidden="true">
      <path :d="ICONS[glyph]" />
    </svg>
    <svg v-if="icon" class="chip-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path :d="ICONS[icon]" />
    </svg>
    <slot name="end" />
  </span>
</template>

<style scoped>
  .chip {
    --tint: var(--accent);
    --ink: var(--accent-hot);
    --cut: 7px;
    --edge: var(--accent-dim);
    --fill: var(--bg-1);
    --hover: 18%;
    position: relative;
    isolation: isolate;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 22px;
    padding: 0 calc(var(--cut) + 4px);
    font: 700 11.5px var(--font-mono);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
    color: var(--ink);
    white-space: nowrap;
    background: var(--edge);
    clip-path: polygon(
      var(--cut) 0,
      calc(100% - var(--cut)) 0,
      100% 50%,
      calc(100% - var(--cut)) 100%,
      var(--cut) 100%,
      0 50%
    );
  }
  .chip::before {
    content: '';
    position: absolute;
    z-index: -1;
    inset: 1px;
    background: var(--fill);
    clip-path: polygon(
      calc(var(--cut) - 0.4px) 0,
      calc(100% - var(--cut) + 0.4px) 0,
      100% 50%,
      calc(100% - var(--cut) + 0.4px) 100%,
      calc(var(--cut) - 0.4px) 100%,
      0 50%
    );
    transition: background var(--motion-fast);
  }
  /* Amber (the base tone): solid accent-dim outline around a dark fill; the others tint both. */
  .chip.ok,
  .chip.bad,
  .chip.dim {
    --edge: color-mix(in srgb, var(--tint) 50%, var(--bg-1));
    --fill: color-mix(in srgb, var(--tint) 16%, var(--bg-1));
    --hover: 30%;
  }
  .chip.ok {
    --tint: var(--ok);
    --ink: var(--ok);
  }
  .chip.bad {
    --tint: var(--bad);
    --ink: var(--bad);
  }
  .chip.dim {
    --tint: var(--text-dim);
    --ink: var(--text-dim);
    font-weight: 600;
  }
  a:hover > .chip::before,
  button:hover > .chip::before {
    background: color-mix(in srgb, var(--tint) var(--hover), var(--bg-1));
  }
  .chip-icon {
    width: 11px;
    height: 11px;
    fill: currentColor;
    flex: none;
  }
  .chip-icon.glyph {
    display: none;
  }
  .only .word {
    display: none;
  }
  .only .chip-icon.glyph {
    display: block;
    width: 13px;
    height: 13px;
  }
  /* Tablet band: two pixels less padding a side keeps three chips inside the Story column. */
  @media (min-width: 760px) and (max-width: 1179.98px) {
    .chip {
      padding: 0 calc(var(--cut) + 2px);
    }
  }
  @media (max-width: 759.98px) {
    .glyphed .word {
      display: none;
    }
    .glyphed .chip-icon.glyph {
      display: block;
      width: 13px;
      height: 13px;
    }
  }
</style>
