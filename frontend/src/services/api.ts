import axios from 'axios'
import type {
  Quote, History, AssetInfo, IndicatorsResponse, NewsResponse, SearchResponse,
  PortfolioSummary, Position, Alert, CompanyListResponse, Company, WatchlistItem,
  ScoreResponse, SupplyResponse, Rates,
} from '../types'

export interface PositionCreate {
  symbol: string
  quantity: number
  avg_cost: number
  notes?: string
}

export interface AlertCreate {
  symbol: string
  condition: 'above' | 'below'
  threshold: number
  note?: string
}

const api = axios.create({ baseURL: '/api' })

/** Verständliche Fehlermeldung aus einer Backend-Antwort ziehen. */
export function errorText(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail ?? 'Server nicht erreichbar.'
}

export const marketApi = {
  quotes: (symbols: string[]) =>
    api.get<Quote[]>('/market/quotes', { params: { symbols: symbols.join(',') } }).then(r => r.data),
  search: (q: string) => api.get<SearchResponse>('/market/search', { params: { q } }).then(r => r.data),
}

export const assetApi = {
  quote:      (symbol: string) => api.get<Quote>(`/assets/${encodeURIComponent(symbol)}/quote`).then(r => r.data),
  info:       (symbol: string) => api.get<AssetInfo>(`/assets/${encodeURIComponent(symbol)}/info`).then(r => r.data),
  history:    (symbol: string, days = 365) =>
    api.get<History>(`/assets/${encodeURIComponent(symbol)}/history`, { params: { days } }).then(r => r.data),
  indicators: (symbol: string) =>
    api.get<IndicatorsResponse>(`/assets/${encodeURIComponent(symbol)}/indicators`).then(r => r.data),
}

export const newsApi = {
  feed:      (symbol?: string, limit = 20) =>
    api.get<NewsResponse>('/news', { params: { symbol, limit } }).then(r => r.data),
  forSymbol: (symbol: string) => api.get<NewsResponse>(`/news/${encodeURIComponent(symbol)}`).then(r => r.data),
}

export const portfolioApi = {
  get:    () => api.get<PortfolioSummary>('/portfolio').then(r => r.data),
  add:    (body: PositionCreate) => api.post<Position>('/portfolio/positions', body).then(r => r.data),
  remove: (id: string) => api.delete(`/portfolio/positions/${id}`),
}

export const alertsApi = {
  list:   () => api.get<Alert[]>('/alerts').then(r => r.data),
  create: (body: AlertCreate) => api.post<Alert>('/alerts', body).then(r => r.data),
  delete: (id: string) => api.delete(`/alerts/${id}`),
}

export const companiesApi = {
  list: (params?: { sector?: string; search?: string; limit?: number; offset?: number }) =>
    api.get<CompanyListResponse>('/companies', { params }).then(r => r.data),
  sectors: () => api.get<string[]>('/companies/sectors').then(r => r.data),
  get: (symbol: string) => api.get<Company>(`/companies/${encodeURIComponent(symbol)}`).then(r => r.data),
}

export const relationshipsApi = {
  get: (symbol: string) => api.get<SupplyResponse>(`/relationships/${encodeURIComponent(symbol)}`).then(r => r.data),
}

export const scoreApi = {
  get: (symbol: string, refresh = false) =>
    api.get<ScoreResponse>(`/score/${encodeURIComponent(symbol)}`, { params: { refresh } }).then(r => r.data),
}

export const ratesApi = {
  get: () => api.get<Rates>('/rates').then(r => r.data),
}

export const watchlistApi = {
  get:    () => api.get<WatchlistItem[]>('/watchlist').then(r => r.data),
  add:    (symbol: string) => api.post<WatchlistItem>('/watchlist', { symbol }).then(r => r.data),
  remove: (symbol: string) => api.delete(`/watchlist/${encodeURIComponent(symbol)}`),
}
