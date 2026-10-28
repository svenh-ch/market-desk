import { useEffect, useRef, useState } from 'react'
import { marketApi } from '../../services/api'
import type { SearchResult } from '../../types'

interface Props {
  onSelect: (symbol: string) => void
  placeholder?: string
  buttonLabel?: string
  className?: string
}

/** Suchfeld für Firmenname oder Ticker (Yahoo-Suche + eigene Auswahlliste). */
export default function SymbolSearch({ onSelect, placeholder = 'Firmenname oder Ticker …', buttonLabel = '+ HINZUFÜGEN', className = '' }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const term = q.trim()
    if (term.length < 2) { setResults([]); setError(null); return }
    setLoading(true)
    const t = setTimeout(() => {
      marketApi.search(term)
        .then(r => { setResults(r.results); setError(r.error) })
        .catch(() => { setResults([]); setError('Suche nicht erreichbar.') })
        .finally(() => setLoading(false))
    }, 300)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const pick = (symbol: string) => {
    onSelect(symbol)
    setQ(''); setResults([]); setOpen(false)
  }

  const submit = () => {
    const typed = q.trim().toUpperCase()
    if (!typed) return
    // Exakter Ticker → direkt; sonst erster Treffer
    pick(results.find(r => r.symbol === typed)?.symbol ?? results[0]?.symbol ?? typed)
  }

  return (
    <div ref={ref} className={`relative ${className}`}>
      <div className="flex items-center gap-2">
        <input
          value={q}
          onChange={e => { setQ(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={e => { if (e.key === 'Enter') submit() }}
          placeholder={placeholder}
          className="bg-terminal-bg border border-terminal-border px-3 py-1 text-xs text-terminal-text outline-none focus:border-terminal-orange w-64"
        />
        <button
          onClick={submit}
          className="px-3 py-1 text-xs border border-terminal-orange text-terminal-orange hover:bg-terminal-orange hover:text-black transition-colors"
        >
          {buttonLabel}
        </button>
      </div>

      {open && q.trim().length >= 2 && (
        <div className="absolute right-0 top-full mt-1 z-50 bg-terminal-panel border border-terminal-border w-[28rem] shadow-lg max-h-80 overflow-y-auto">
          {loading && results.length === 0 && <div className="px-3 py-2 text-xs text-terminal-muted">Suche …</div>}
          {!loading && results.length === 0 && <div className="px-3 py-2 text-xs text-terminal-muted">Keine Treffer.</div>}
          {results.map(r => (
            <button
              key={r.symbol}
              type="button"
              onMouseDown={() => pick(r.symbol)}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-terminal-hover transition-colors text-left"
            >
              <span className="text-terminal-orange font-bold w-24 shrink-0 truncate">{r.symbol}</span>
              <span className="text-terminal-text truncate flex-1">{r.name}</span>
              <span className="text-terminal-muted shrink-0">{r.exchange ?? ''}</span>
            </button>
          ))}
          {error && <div className="px-3 py-2 text-[10px] text-terminal-orange border-t border-terminal-border">{error}</div>}
        </div>
      )}
    </div>
  )
}
