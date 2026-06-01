<script setup lang="ts">
import type { TerminalLine } from './useTerminalTranscript'

defineProps<{ line: TerminalLine }>()

const HOST = 'honeypot'
</script>

<template>
  <!-- Command lines = attacker-typed input (bright). Everything else is a
       honeywatch annotation (muted, wrapped in ‹ … ›) so it can never be
       mistaken for real command output, which cowrie does not record. -->
  <div class="line" :class="`line-${line.kind}`">
    <template v-if="line.kind === 'command'">
      <span class="prompt">{{ line.user }}@{{ HOST }}:~$ </span
      ><span class="input"
        ><template v-for="(seg, i) in line.segments" :key="i"
          ><span v-if="seg.redacted" class="ip-blot" title="IP address redacted"
            >{{ seg.text }}<span class="visually-hidden"> (IP address redacted)</span></span
          ><template v-else>{{ seg.text }}</template></template
        ></span
      >
    </template>
    <span
      v-else-if="line.kind === 'auth-ok' || line.kind === 'auth-fail'"
      class="annotation"
      ><span aria-hidden="true">‹ </span>{{ line.pre
      }}<span
        v-if="line.password"
        class="cred"
        title="password the attacker supplied"
        >{{ line.password }}</span
      ><span v-else class="cred cred-empty"
        >‹empty›<span class="visually-hidden"> (no password supplied)</span></span
      >{{ line.post }}<span aria-hidden="true"> ›</span></span
    >
    <span v-else class="annotation"
      ><span aria-hidden="true">‹ </span>{{ line.text }}<span aria-hidden="true"> ›</span></span
    >
  </div>
</template>

<style scoped>
.line {
  font-family: var(--font-mono);
  font-size: var(--type-sm);
  /* Looser leading + a little vertical padding give the replay breathing room --
     stacked identical brute-force lines read as cramped at 1.7 with no gap. */
  line-height: 1.85;
  padding-block: 2px;
  white-space: pre-wrap;
  /* anywhere (vs break-word) also breaks long unbroken tokens -- base64 blobs,
     long URLs -- so they never force horizontal scroll inside the replay. */
  overflow-wrap: anywhere;
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

/* The captured credential. Warning tone (not the accent ip-blot) reads as
   real attacker data rather than a redaction; non-italic so it stands out as a
   literal value inside the italic annotation. */
.cred {
  color: var(--warning);
  background: color-mix(in srgb, var(--warning) 14%, transparent);
  border-radius: 2px;
  padding: 0 4px;
  font-style: normal;
  font-weight: 600;
}

.cred-empty {
  /* --text-muted (not --text-dim) so the empty marker clears AAA contrast on the
     terminal bg; still reads as a muted, italic placeholder. */
  color: var(--text-muted);
  background: none;
  font-weight: 400;
  font-style: italic;
}
</style>
