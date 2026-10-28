import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { companiesApi, watchlistApi } from '../../services/api'
import { useStore } from '../../store/useStore'
import { useQuotes } from '../../hooks/useQuotes'
import PriceCell from '../common/PriceCell'
import type { Company } from '../../types'

const LIMIT = 24

export default function CompanyExplorer() {
  const navigate = useNavigate()
  const { watchlist, setWatchlist } = useStore()

  const [companies, setCompanies] = useState<Company[]>([])
  const [total, setTotal] = useState(0)
  const [sectors, setSectors] = useState<string[]>([])
  const [sector, setSector] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)

  const quotes = useQuotes(companies.map(c => c.symbol))

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => { companiesApi.sectors().then(s => setSectors(['', ...s])).catch(() => {}) }, [])
  useEffect(() => { setOffset(0) }, [sector, debouncedSearch])

  useEffect(() => {
    setLoading(true)
    companiesApi.list({ sector: sector || undefined, search: debouncedSearch || undefined, limit: LIMIT, offset })
      .then(r => { setCompanies(r.items); setTotal(r.total) })
      .catch(() => { setCompanies([]); setTotal(0) })
      .finally(() => setLoading(false))
  }, [sector, debouncedSearch, offset])

  const watched = (sym: string) => watchlist.some(i => i.symbol === sym)
  const toggleWatch = async (sym: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      if (watched(sym)) await watchlistApi.remove(sym)
      else await watchlistApi.add(sym)
      setWatchlist(await watchlistApi.get())
    } catch { /* Meldung erscheint in der Watchlist selbst */ }
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-terminal-orange font-semibold text-xs">EXPLORER</span>
        <span className="text-terminal-text-dim text-xs">{total} Wertpapiere in der Auswahlliste</span>
        <div className="flex-1 flex items-center gap-2 flex-wrap justify-end">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Name oder Ticker filtern …"
            className="bg-terminal-bg border border-terminal-border px-3 py-1 text-xs text-terminal-text outline-none focus:border-terminal-orange w-52"
          />
          <select
            value={sector}
            onChange={e => setSector(e.target.value)}
            className="bg-terminal-bg border border-terminal-border px-2 py-1 text-xs text-terminal-text outline-none focus:border-terminal-orange"
          >
            {sectors.map(s => <option key={s} value={s}>{s || 'Alle Branchen'}</option>)}
          </select>
        </div>
      </div>
      <div className="text-[11px] text-terminal-muted">
        Weitere Wertpapiere weltweit findest du über die Suche auf der Startseite oder in der Befehlszeile (einfach lostippen).
      </div>

      {loading ? (
        <div className="text-terminal-text-dim text-sm">Lade Auswahlliste …</div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {companies.map(c => (
              <div
                key={c.symbol}
                onClick={() => navigate(`/asset/${encodeURIComponent(c.symbol)}`)}
                className="panel p-3 text-left hover:border-terminal-orange transition-all group relative cursor-pointer"
              >
                <button
                  onClick={(e) => toggleWatch(c.symbol, e)}
                  title={watched(c.symbol) ? 'Von der Watchlist entfernen' : 'Zur Watchlist hinzufügen'}
                  className={`absolute top-2 right-2 text-xs transition-colors ${
                    watched(c.symbol) ? 'text-terminal-orange' : 'text-terminal-muted opacity-0 group-hover:opacity-100'
                  }`}
                >
                  {watched(c.symbol) ? '★' : '☆'}
                </button>
                <div className="text-terminal-orange font-bold text-sm">{c.symbol}</div>
                <div className="text-terminal-text-dim text-xs truncate mb-2 pr-4">{c.name}</div>
                <PriceCell q={quotes[c.symbol]} />
                <div className="mt-2 flex items-center justify-between text-[10px] text-terminal-muted">
                  <span>{c.sector}</span>
                  <span>{c.exchange}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs text-terminal-text-dim">
            <span>{total ? `${offset + 1}–${Math.min(offset + LIMIT, total)} von ${total}` : 'Keine Treffer'}</span>
            <div className="flex gap-2">
              <button disabled={offset === 0} onClick={() => setOffset(o => Math.max(0, o - LIMIT))}
                className="px-3 py-1 border border-terminal-border disabled:opacity-30 hover:border-terminal-orange transition-colors">
                ← Zurück
              </button>
              <button disabled={offset + LIMIT >= total} onClick={() => setOffset(o => o + LIMIT)}
                className="px-3 py-1 border border-terminal-border disabled:opacity-30 hover:border-terminal-orange transition-colors">
                Weiter →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
