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
    <span v-else class="annotation"
      ><span aria-hidden="true">‹ </span>{{ line.text }}<span aria-hidden="true"> ›</span></span
    >
  </div>
</template>

<style scoped>
.line {
  font-family: var(--font-mono);
  font-size: var(--type-sm);
  line-height: 1.7;
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
</style>
