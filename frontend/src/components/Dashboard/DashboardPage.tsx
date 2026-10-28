import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ratesApi } from '../../services/api'
import type { Rates } from '../../types'
import { useStore } from '../../store/useStore'
import { useQuotes } from '../../hooks/useQuotes'
import SymbolSearch from '../common/SymbolSearch'
import PriceCell from '../common/PriceCell'
import DataStamp from '../common/DataStamp'
import type { Quote } from '../../types'

function SecurityTile({ symbol, q, onRemove }: { symbol: string; q: Quote | undefined; onRemove: () => void }) {
  const navigate = useNavigate()
  return (
    <div
      className="panel p-3 text-left hover:border-terminal-orange transition-all group relative cursor-pointer flex flex-col gap-1"
      onClick={() => navigate(`/asset/${encodeURIComponent(symbol)}`)}
    >
      <button
        onClick={e => { e.stopPropagation(); onRemove() }}
        className="absolute top-1.5 right-2 text-terminal-muted opacity-0 group-hover:opacity-100 hover:text-terminal-red transition-colors text-xs"
        title="Von der Startseite entfernen"
      >
        ✕
      </button>
      <div className="text-terminal-orange font-bold text-sm pr-4 truncate">{symbol}</div>
      <div className="text-terminal-text-dim text-xs truncate">{q?.name ?? ''}</div>
      <PriceCell q={q} />
      {q?.available && <DataStamp meta={q} marketTime={q.market_time} />}
    </div>
  )
}

export default function DashboardPage() {
  const { dashboardSymbols, addDashboardSymbol, removeDashboardSymbol } = useStore()
  const quotes = useQuotes(dashboardSymbols)
  const [rates, setRates] = useState<Rates | null>(null)
  useEffect(() => { ratesApi.get().then(setRates).catch(() => setRates(null)) }, [])

  const loaded = dashboardSymbols.map(s => quotes[s]).filter(q => q?.available)
  const gainers = loaded.filter(q => (q!.change_pct ?? 0) > 0).length
  const losers = loaded.filter(q => (q!.change_pct ?? 0) < 0).length

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 text-xs">
          <span className="text-terminal-orange font-semibold">STARTSEITE</span>
          <span className="text-terminal-green">{gainers} ▲</span>
          <span className="text-terminal-text-dim">/</span>
          <span className="text-terminal-red">{losers} ▼</span>
          <span className="text-terminal-muted">· {dashboardSymbols.length} Wertpapiere</span>
        </div>
        <SymbolSearch onSelect={addDashboardSymbol} placeholder="Wertpapier hinzufügen (Name oder Ticker) …" />
      </div>

      <div className="text-[11px] text-terminal-muted">
        Kurse von Yahoo Finance, automatisch jede Minute aktualisiert. Je nach Börse bis ca. 15 Minuten verzögert. Keine Anlageberatung.
        {rates && (
          <span className="ml-3" title={`${rates.usd?.source ?? ''}\n${rates.chf?.source ?? ''}`}>
            · Risikofreier Zins USD {rates.usd?.rate != null ? `${rates.usd.rate.toFixed(2)} %` : '–'} ({rates.usd?.series}, {rates.usd?.date})
            · CHF {rates.chf?.rate != null ? `${rates.chf.rate.toFixed(2)} %` : '–'} ({rates.chf?.series}, {rates.chf?.date})
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
        {dashboardSymbols.map(symbol => (
          <SecurityTile key={symbol} symbol={symbol} q={quotes[symbol]} onRemove={() => removeDashboardSymbol(symbol)} />
        ))}
      </div>

      {dashboardSymbols.length === 0 && (
        <div className="panel p-12 text-center text-sm text-terminal-text-dim">
          Die Startseite ist leer. Oben ein Wertpapier suchen und hinzufügen.
        </div>
      )}
    </div>
  )
}
