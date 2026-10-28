// Herkunft und Alter eines Datensatzes – kommt bei jeder Antwort mit
export interface DataMeta {
  source: string
  fetched_at: string | null
  from_cache: boolean
  cache_age_seconds: number
  stale: boolean
  error: string | null
}

export interface Quote extends DataMeta {
  symbol: string
  name: string
  available: boolean
  price: number | null
  prev_close: number | null
  change: number | null
  change_pct: number | null
  day_high: number | null
  day_low: number | null
  volume: number | null
  currency: string | null
  exchange: string | null
  market_time: string | null
}

export interface OHLCV {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface History extends DataMeta {
  symbol: string
  available: boolean
  currency: string | null
  candles: OHLCV[]
}

export interface AssetInfo extends DataMeta {
  symbol: string
  available: boolean
  name: string
  description: string | null
  asset_type: string | null
  sector: string | null
  industry: string | null
  country: string | null
  currency: string | null
  financial_currency: string | null
  exchange: string | null
  website: string | null
  employees: number | null
  market_cap: number | null
  pe_ratio: number | null
  price_to_book: number | null
  ev_ebitda: number | null
  eps: number | null
  dividend_yield: number | null
  revenue: number | null
  week_52_high: number | null
  week_52_low: number | null
  avg_volume: number | null
}

export interface IndicatorValue {
  time: number
  value: number
}

export interface Indicator {
  name: string
  values: IndicatorValue[]
}

export interface IndicatorsResponse extends DataMeta {
  symbol: string
  available: boolean
  indicators: Indicator[]
  signal: 'BUY' | 'SELL' | 'NEUTRAL' | null
  signal_reason: string | null
}

export interface NewsItem {
  id: string
  headline: string
  source: string
  url: string
  published_at: string | null
  symbols: string[]
}

export interface NewsResponse extends DataMeta {
  items: NewsItem[]
}

export interface SearchResult {
  symbol: string
  name: string
  asset_type: string | null
  exchange: string | null
  sector: string | null
}

export interface SearchResponse {
  results: SearchResult[]
  error: string | null
}

export interface Position {
  id: string
  symbol: string
  name: string
  quantity: number
  avg_cost: number
  currency: string | null
  current_price: number | null
  market_value: number | null
  cost_basis: number
  pnl: number | null
  pnl_pct: number | null
  day_pnl: number | null
  day_pnl_pct: number | null
  notes: string | null
  opened_at: string | null
  quote_time: string | null
  quote_error: string | null
}

export interface PortfolioSummary {
  positions: Position[]
  currency: string | null
  total_value: number | null
  total_cost: number | null
  total_pnl: number | null
  total_pnl_pct: number | null
  day_pnl: number | null
  totals_note: string | null
}

export interface Alert {
  id: string
  symbol: string
  condition: 'above' | 'below'
  threshold: number
  note: string | null
  triggered: boolean
  created_at: string | null
  triggered_at: string | null
  current_price: number | null
}

export interface Company {
  symbol: string
  name: string
  sector: string | null
  exchange: string | null
}

export interface CompanyListResponse {
  total: number
  items: Company[]
}

export interface GraphLink {
  source: string
  target: string
  type: 'customer' | 'supplier'
  revenue_share: number | null
  confidence: string | null
  source_doc: string
  source_year: number | null
  description: string | null
}

export interface GraphData {
  center: string
  nodes: { symbol: string; name: string }[]
  links: GraphLink[]
  message: string | null
}

export interface WatchlistItem {
  id: number
  symbol: string
  notes: string | null
  added_at: string | null
}

// ── Eigener Score ────────────────────────────────────────────────────────────
export type Color = 'green' | 'yellow' | 'red' | 'grey'

export interface ScoreMetric {
  key: string
  label: string
  pillar: string
  enabled: boolean
  value: number | null
  peer_median: number | null
  peer_count: number
  percentile: number | null
  color: Color
  literature: string
  data_source: string | null
  reason: string | null
  damodaran?: number | null
}

export interface ScorePillar {
  label: string
  score: number | null
  color: Color
  weight: number
  metrics_used: number
  metrics_total: number
}

export interface ScoreResult {
  symbol: string
  available: boolean
  error?: string
  name: string
  disclaimer: string
  is_financial: boolean
  overall: number | null
  overall_color: Color
  overall_note: string | null
  coverage: number
  pillars: Record<string, ScorePillar>
  metrics: Record<string, ScoreMetric>
  info_metrics: Record<string, { label: string; value: number | null }>
  piotroski: { score: number | null; signals: Record<string, boolean | null>; note?: string } | null
  piotroski_absolute: { value: number; color: Color; rule: string } | null
  altman_absolute: { model: string; value: number; color: Color; rule: string } | null
  peer_group: { level: string; enough: boolean; source: string; fetched_at: string; with_data: number
                members: { symbol: string; name: string; country: string | null; market_cap_usd: number }[] }
  damodaran: { industry: string; updated: string | null; source: string; note: string } | null
  fundamentals: { source: string | null; currency: string | null; period_end: string | null; filed: string | null
                  deviations_vs_yahoo: { item: string; official: number; yahoo: number; deviation_pct: number }[] }
  market: { index: string; price_date: string | null }
  warnings: string[]
  computed_at: string
}

export interface ScoreResponse {
  status: 'running' | 'done' | 'error'
  message?: string
  progress?: number
  error?: string
  result?: ScoreResult
  cache_age_seconds?: number
}

export interface SupplyLink {
  other: string | null
  label: string
  anonymous: boolean
  type: 'customer' | 'supplier'
  revenue_share: number | null
  share_basis: string | null
  confidence: 'bestätigt' | 'wahrscheinlich'
  mapping_certain: boolean | null
  name_in_report: string | null
  source_doc: string
  source_year: number | null
  source_url: string | null
  section: string | null
  quote: string | null
  via: string
  method: string | null
}

export interface SupplyResponse {
  status: 'running' | 'done' | 'error'
  message?: string
  progress?: number
  graph: { center: string; links: SupplyLink[]; message: string | null }
}

export interface Rates {
  usd?: { rate?: number; date?: string; series?: string; source?: string; error?: string }
  chf?: { rate?: number; date?: string; series?: string; source?: string; error?: string }
}
