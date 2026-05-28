export type ConnectionState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'

export interface LiveEvent {
  id: string
  sensor: string
  protocol: string
  dst_port: number
  started_at: string
  country_code: string | null
}
