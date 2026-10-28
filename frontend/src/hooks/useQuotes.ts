import { useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'
import { marketApi } from '../services/api'
import type { Quote } from '../types'

/** Alle 60 Sekunden aktualisieren – passend zum Kurs-Cache des Backends. */
export const REFRESH_SECONDS = 60

/**
 * Meldet Ticker als "sichtbar" an und gibt deren aktuelle Kurse zurück.
 * Die eigentliche Abfrage macht useQuotePoller (einmal für die ganze App).
 */
export function useQuotes(symbols: string[]): Record<string, Quote | undefined> {
  const subscribe = useStore(s => s.subscribe)
  const unsubscribe = useStore(s => s.unsubscribe)
  const quotes = useStore(s => s.quotes)
  const key = symbols.join(',')

  useEffect(() => {
    const syms = key ? key.split(',') : []
    subscribe(syms)
    return () => unsubscribe(syms)
  }, [key, subscribe, unsubscribe])

  const out: Record<string, Quote | undefined> = {}
  for (const s of symbols) out[s] = quotes[s]
  return out
}

/** Holt alle angemeldeten Kurse: sofort bei neuen Tickern, danach im festen Takt. */
export function useQuotePoller() {
  const subscriptions = useStore(s => s.subscriptions)
  const setQuotes = useStore(s => s.setQuotes)
  const setRefreshStatus = useStore(s => s.setRefreshStatus)
  const symbolsRef = useRef<string[]>([])
  symbolsRef.current = Object.keys(subscriptions)

  const fetchNow = async (symbols: string[]) => {
    if (!symbols.length) return
    try {
      // Backend nimmt maximal 60 Ticker pro Anfrage
      for (let i = 0; i < symbols.length; i += 60) {
        setQuotes(await marketApi.quotes(symbols.slice(i, i + 60)))
      }
      setRefreshStatus(new Date().toISOString(), null)
    } catch {
      setRefreshStatus(useStore.getState().lastRefresh, 'Server nicht erreichbar – Kurse werden nicht aktualisiert.')
    }
  }

  // Neue Ticker sofort laden (kurz gebündelt)
  const known = useStore(s => s.quotes)
  const missingKey = symbolsRef.current.filter(s => !known[s]).sort().join(',')
  useEffect(() => {
    if (!missingKey) return
    const t = setTimeout(() => fetchNow(missingKey.split(',')), 150)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missingKey])

  // Regelmässig alles Sichtbare aktualisieren
  useEffect(() => {
    const id = setInterval(() => fetchNow(symbolsRef.current), REFRESH_SECONDS * 1000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
