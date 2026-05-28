import { defineStore } from 'pinia'
import type { ConnectionState, LiveEvent } from '../types/stream'

const MAX_BUFFER = 200

interface StreamState {
  status: ConnectionState
  buffer: LiveEvent[]
  lastEventAt: string | null
}

export const useStreamStore = defineStore('stream', {
  state: (): StreamState => ({
    status: 'idle',
    buffer: [],
    lastEventAt: null,
  }),

  getters: {
    latestByCountry(state): Record<string, LiveEvent> {
      const out: Record<string, LiveEvent> = {}
      for (const ev of state.buffer) {
        const cc = ev.country_code ?? 'XX'
        const existing = out[cc]
        if (!existing || (ev.started_at > existing.started_at)) {
          out[cc] = ev
        }
      }
      return out
    },
  },

  actions: {
    pushEvent(ev: LiveEvent) {
      this.buffer.push(ev)
      if (this.buffer.length > MAX_BUFFER) {
        this.buffer.splice(0, this.buffer.length - MAX_BUFFER)
      }
      this.lastEventAt = ev.started_at
    },
    setStatus(status: ConnectionState) {
      this.status = status
    },
    clear() {
      this.buffer = []
      this.lastEventAt = null
    },
  },
})
