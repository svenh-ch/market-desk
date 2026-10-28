import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Quote, WatchlistItem } from '../types'

interface AppState {
  // Kurse aller gerade sichtbaren Wertpapiere (vom Backend, mit Zeitstempel)
  quotes: Record<string, Quote>
  setQuotes: (qs: Quote[]) => void
  // Welche Ticker gerade irgendwo angezeigt werden (Zähler pro Ticker)
  subscriptions: Record<string, number>
  subscribe: (symbols: string[]) => void
  unsubscribe: (symbols: string[]) => void
  lastRefresh: string | null      // Zeitpunkt der letzten erfolgreichen Abfrage
  refreshError: string | null
  setRefreshStatus: (at: string | null, error: string | null) => void

  // Befehlszeile
  terminalOpen: boolean
  setTerminalOpen: (open: boolean) => void
  terminalInput: string
  setTerminalInput: (v: string) => void

  // Watchlist (im Backend gespeichert, hier zwischengespeichert)
  watchlist: WatchlistItem[]
  setWatchlist: (items: WatchlistItem[]) => void
  isWatched: (symbol: string) => boolean

  // Startseite: frei wählbare Wertpapiere (lokal gespeichert)
  dashboardSymbols: string[]
  addDashboardSymbol: (symbol: string) => void
  removeDashboardSymbol: (symbol: string) => void
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      quotes: {},
      setQuotes: (qs) => set((s) => {
        const next = { ...s.quotes }
        for (const q of qs) next[q.symbol] = q
        return { quotes: next }
      }),
      subscriptions: {},
      subscribe: (symbols) => set((s) => {
        const next = { ...s.subscriptions }
        for (const sym of symbols) next[sym] = (next[sym] ?? 0) + 1
        return { subscriptions: next }
      }),
      unsubscribe: (symbols) => set((s) => {
        const next = { ...s.subscriptions }
        for (const sym of symbols) {
          next[sym] = (next[sym] ?? 1) - 1
          if (next[sym] <= 0) delete next[sym]
        }
        return { subscriptions: next }
      }),
      lastRefresh: null,
      refreshError: null,
      setRefreshStatus: (at, error) => set({ lastRefresh: at, refreshError: error }),

      terminalOpen: false,
      setTerminalOpen: (open) => set({ terminalOpen: open }),
      terminalInput: '',
      setTerminalInput: (v) => set({ terminalInput: v }),

      watchlist: [],
      setWatchlist: (items) => set({ watchlist: items }),
      isWatched: (symbol) => get().watchlist.some(i => i.symbol === symbol),

      dashboardSymbols: ['^GSPC', '^SSMI', '^GDAXI', 'AAPL', 'MSFT', 'NVDA', 'NESN.SW', 'NOVN.SW', 'ROP.SW', 'UBSG.SW', 'SAP', 'ASML', 'BTC-USD'],
      addDashboardSymbol: (symbol) =>
        set((s) => ({ dashboardSymbols: s.dashboardSymbols.includes(symbol) ? s.dashboardSymbols : [...s.dashboardSymbols, symbol] })),
      removeDashboardSymbol: (symbol) =>
        set((s) => ({ dashboardSymbols: s.dashboardSymbols.filter(sym => sym !== symbol) })),
    }),
    {
      name: 'market-desk-store',
      // Kurse werden bewusst NICHT gespeichert – nach dem Start immer frisch laden
      partialize: (s) => ({ dashboardSymbols: s.dashboardSymbols }),
    }
  )
)
