import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { watchlistApi, errorText } from '../../services/api'
import { useStore } from '../../store/useStore'
import { useQuotes } from '../../hooks/useQuotes'
import SymbolSearch from '../common/SymbolSearch'
import { dateTime, pct, price } from '../../lib/format'

type SortKey = 'symbol' | 'name' | 'price' | 'change_pct'

export default function WatchlistPage() {
  const navigate = useNavigate()
  const { watchlist, setWatchlist } = useStore()
  const quotes = useQuotes(watchlist.map(i => i.symbol))

  const [loading, setLoading] = useState(true)
  const [sortKey, setSortKey] = useState<SortKey>('symbol')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const refresh = () =>
    watchlistApi.get().then(setWatchlist).catch(() => setMessage({ ok: false, text: 'Server nicht erreichbar.' })).finally(() => setLoading(false))

  useEffect(() => { refresh() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir(key === 'symbol' || key === 'name' ? 'asc' : 'desc') }
  }

  const sorted = useMemo(() => {
    const val = (sym: string): string | number => {
      const q = quotes[sym]
      if (sortKey === 'symbol') return sym
      if (sortKey === 'name') return q?.name ?? sym
      if (sortKey === 'price') return q?.price ?? -Infinity
      return q?.change_pct ?? -Infinity
    }
    return [...watchlist].sort((a, b) => {
      const va = val(a.symbol), vb = val(b.symbol)
      const cmp = typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number)
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [watchlist, quotes, sortKey, sortDir])

  const add = async (symbol: string) => {
    setMessage(null)
    try {
      await watchlistApi.add(symbol)
      setMessage({ ok: true, text: `${symbol} hinzugefügt.` })
      refresh()
    } catch (e) {
      setMessage({ ok: false, text: errorText(e) })
    }
  }

  const remove = async (symbol: string) => {
    await watchlistApi.remove(symbol)
    refresh()
  }

  const Col = ({ k, label }: { k: SortKey; label: string }) => (
    <th onClick={() => handleSort(k)}
      className="text-left px-3 py-2 font-normal cursor-pointer hover:text-terminal-orange select-none whitespace-nowrap">
      {label}{sortKey === k ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
    </th>
  )

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="text-xs">
          <span className="text-terminal-orange font-semibold">WATCHLIST</span>
          <span className="text-terminal-text-dim ml-2">{watchlist.length} Wertpapiere</span>
        </div>
        <div className="flex items-center gap-3">
          {message && <span className={`text-xs ${message.ok ? 'text-terminal-green' : 'text-terminal-red'}`}>{message.text}</span>}
          <SymbolSearch onSelect={add} placeholder="Firmenname oder Ticker (z. B. Nestlé, Siemens) …" />
        </div>
      </div>

      {loading ? (
        <div className="text-terminal-text-dim text-sm">Lade Watchlist …</div>
      ) : watchlist.length === 0 ? (
        <div className="panel p-12 text-center text-sm text-terminal-text-dim">
          Die Watchlist ist leer. Oben eine Firma suchen und hinzufügen.
        </div>
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-terminal-border text-terminal-text-dim">
                <Col k="symbol" label="TICKER" />
                <Col k="name" label="NAME" />
                <Col k="price" label="KURS" />
                <Col k="change_pct" label="TAG %" />
                <th className="text-left px-3 py-2 font-normal">BÖRSE</th>
                <th className="text-left px-3 py-2 font-normal">STAND (Yahoo Finance)</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sorted.map(item => {
                const q = quotes[item.symbol]
                const ok = q?.available && q.price != null
                const up = (q?.change_pct ?? 0) >= 0
                return (
                  <tr key={item.symbol} onClick={() => navigate(`/asset/${encodeURIComponent(item.symbol)}`)}
                    className="border-b border-terminal-border/30 hover:bg-terminal-hover cursor-pointer">
                    <td className="px-3 py-2 text-terminal-orange font-semibold">{item.symbol}</td>
                    <td className="px-3 py-2 text-terminal-text truncate max-w-[220px]">{q?.name ?? '…'}</td>
                    <td className="px-3 py-2 tabular-nums">
                      {!q ? <span className="text-terminal-muted">lädt …</span>
                        : ok ? <>{price(q.price)} <span className="text-terminal-muted">{q.currency}</span>{q.stale && <span className="text-terminal-orange ml-1">VERALTET</span>}</>
                        : <span className="text-terminal-orange" title={q.error ?? ''}>nicht verfügbar</span>}
                    </td>
                    <td className={`px-3 py-2 tabular-nums ${ok ? (up ? 'text-terminal-green' : 'text-terminal-red') : 'text-terminal-muted'}`}>
                      {ok ? pct(q!.change_pct) : '–'}
                    </td>
                    <td className="px-3 py-2 text-terminal-text-dim">{q?.exchange ?? '–'}</td>
                    <td className="px-3 py-2 text-terminal-muted">
                      {ok ? <>{dateTime(q!.market_time)}{q!.from_cache && ' · Cache'}</> : '–'}
                    </td>
                    <td className="px-3 py-2">
                      <button onClick={e => { e.stopPropagation(); remove(item.symbol) }}
                        className="text-terminal-muted hover:text-terminal-red" title="Entfernen">✕</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="text-[11px] text-terminal-muted">Kurse je nach Börse bis ca. 15 Minuten verzögert. Keine Anlageberatung.</div>
    </div>
  )
}
