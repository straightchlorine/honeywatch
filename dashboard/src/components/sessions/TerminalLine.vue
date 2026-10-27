<script lang="ts">
  // One ResizeObserver shared by every line: a long replay renders thousands of them.
  const lineMeasures = new Map<Element, () => void>()
  const lineRo =
    typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver((entries) => {
          for (const e of entries) lineMeasures.get(e.target)?.()
        })
  function observeLine(el: Element, measure: () => void): void {
    lineMeasures.set(el, measure)
    lineRo?.observe(el)
  }
  function unobserveLine(el: Element): void {
    lineMeasures.delete(el)
    lineRo?.unobserve(el)
  }
</script>

<script setup lang="ts">
  import { onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
  import type { TerminalLine } from './useTerminalTranscript'
  import { useHwTooltip } from '@/composables/useHwTooltip'

  defineProps<{ line: TerminalLine }>()

  const tt = useHwTooltip()
  const HOST = 'honeypot'

  // Phone only (CSS clamps below 760px): long lines get a show-all toggle.
  // The clamp is 6 lines; the toggle shows only while it actually truncates.
  const body = useTemplateRef<HTMLElement>('body')
  const open = ref(false)
  const clipped = ref(false)
  function measure(): void {
    const el = body.value
    if (el && !open.value) clipped.value = el.scrollHeight > el.clientHeight + 1
  }
  onMounted(() => {
    measure()
    if (body.value) observeLine(body.value, measure)
  })
  onBeforeUnmount(() => body.value && unobserveLine(body.value))
</script>

<template>
  <!-- Annotations (< ... >) mark honeywatch metadata, since cowrie doesn't record raw input. -->
  <div class="line" :class="`line-${line.kind}`">
    <span class="ts">{{ line.time }}</span>
    <span ref="body" class="line-body" :class="{ clamp: !open }" @focusin="open = true">
      <template v-if="line.kind === 'command'">
        <span class="prompt">{{ line.user }}@{{ HOST }}:~$ </span
        ><span class="input"
          ><template v-for="(seg, i) in line.segments" :key="i"
            ><span
              v-if="seg.redacted"
              class="ip-blot"
              tabindex="0"
              @pointerenter="tt.show('IP address hidden')"
              @pointermove="tt.move($event as PointerEvent)"
              @pointerleave="tt.hide()"
              @focus="tt.show('IP address hidden')"
              @blur="tt.hide()"
              >{{ seg.text }}<span class="visually-hidden"> (IP address hidden)</span></span
            ><template v-else>{{ seg.text }}</template></template
          ></span
        >
      </template>
      <span v-else-if="line.kind === 'auth-ok' || line.kind === 'auth-fail'" class="annotation"
        ><span aria-hidden="true">&lt; </span>{{ line.pre
        }}<span
          v-if="line.password"
          class="cred"
          tabindex="0"
          @pointerenter="tt.show('password the attacker supplied')"
          @pointermove="tt.move($event as PointerEvent)"
          @pointerleave="tt.hide()"
          @focus="tt.show('password the attacker supplied')"
          @blur="tt.hide()"
          >{{ line.password }}</span
        ><span v-else class="cred cred-empty"
          >(blank)<span class="visually-hidden"> (no password supplied)</span></span
        >{{ line.post }}<span aria-hidden="true"> &gt;</span></span
      >
      <span v-else class="annotation"
        ><span aria-hidden="true">&lt; </span>{{ line.text
        }}<span aria-hidden="true"> &gt;</span></span
      >
    </span>
    <button
      v-if="clipped || open"
      type="button"
      class="more"
      :aria-expanded="open"
      @click="open = !open"
    >
      {{ open ? 'show less' : 'show all' }}
    </button>
  </div>
</template>

<style scoped>
  .line {
    display: flex;
    gap: var(--space-3);
    align-items: baseline;
    font-family: var(--font-mono);
    font-size: var(--type-sm);
    /* Looser line-height for brute-force stacks; 1.7 felt cramped. */
    line-height: 1.85;
    padding-block: 2px;
  }

  @media (max-width: 768px) {
    .line {
      line-height: 1.5;
    }
  }

  /* Fixed width so wrapped command bodies hang under body, not clock. */
  .ts {
    flex: 0 0 auto;
    width: 8ch;
    text-align: right;
    color: var(--text-dim);
    font-variant-numeric: tabular-nums;
    user-select: none;
    -webkit-user-select: none;
  }

  .line-body {
    flex: 1 1 auto;
    min-width: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .more {
    display: none;
  }

  @media (max-width: 759px) {
    .line {
      display: grid;
      grid-template-columns: 8ch minmax(0, 1fr);
    }

    .line-body.clamp {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 6;
      line-clamp: 6;
      overflow: hidden;
    }

    .more {
      display: block;
      grid-column: 2;
      padding: 0;
      background: none;
      border: 0;
      text-align: left;
      color: var(--accent);
      font: inherit;
      line-height: 1.5;
      cursor: pointer;
    }
  }

  .prompt {
    color: var(--text-dim);
  }

  .input {
    color: var(--text);
  }

  .annotation {
    color: var(--text-muted);
    font-style: italic;
  }

  .line-auth-ok .annotation {
    color: var(--success);
  }

  .ip-blot {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 16%, transparent);
    border-radius: 2px;
    padding: 0 3px;
    font-style: normal;
  }

  /* Warning tone signals real data, not redaction; non-italic stands out in italic context. */
  .cred {
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 14%, transparent);
    border-radius: 2px;
    padding: 0 4px;
    font-style: normal;
    font-weight: 600;
  }

  .cred-empty {
    /* --text-muted for AAA contrast; stays italic to read as placeholder. */
    color: var(--text-muted);
    background: none;
    font-weight: 400;
    font-style: italic;
  }
</style>
