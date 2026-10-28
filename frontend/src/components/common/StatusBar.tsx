import { useNavigate } from 'react-router-dom'
import { useQuotes } from '../../hooks/useQuotes'
import { pct, price } from '../../lib/format'

// Laufband: wichtige Indizes und Kryptowährungen
const TICKERS = ['^GSPC', '^IXIC', '^DJI', '^SSMI', '^GDAXI', '^FTSE', 'BTC-USD', 'ETH-USD']
const LABELS: Record<string, string> = {
  '^GSPC': 'S&P 500', '^IXIC': 'NASDAQ', '^DJI': 'DOW', '^SSMI': 'SMI', '^GDAXI': 'DAX', '^FTSE': 'FTSE 100',
}

export default function StatusBar() {
  const quotes = useQuotes(TICKERS)
  const navigate = useNavigate()
  const items = TICKERS.map(s => quotes[s]).filter(q => q?.available)

  return (
    <footer className="bg-terminal-header border-t border-terminal-border px-3 py-1 flex items-center justify-between shrink-0 overflow-hidden">
      <div className="flex-1 overflow-hidden relative">
        {items.length === 0 ? (
          <span className="text-xs text-terminal-muted">Marktdaten werden geladen …</span>
        ) : (
          <div className="flex gap-6 animate-ticker whitespace-nowrap">
            {[...items, ...items].map((q, i) => {
              const up = (q!.change_pct ?? 0) >= 0
              return (
                <button
                  key={i}
                  onClick={() => navigate(`/asset/${encodeURIComponent(q!.symbol)}`)}
                  className="inline-flex items-center gap-1.5 text-xs hover:opacity-80 transition-opacity"
                >
                  <span className="text-terminal-orange font-semibold">{LABELS[q!.symbol] ?? q!.symbol}</span>
                  <span className="text-terminal-text tabular-nums">{price(q!.price)}</span>
                  <span className="text-terminal-muted">{q!.currency}</span>
                  <span className={up ? 'text-terminal-green' : 'text-terminal-red'}>{pct(q!.change_pct)}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="shrink-0 flex items-center gap-3 text-xs text-terminal-muted pl-4 border-l border-terminal-border ml-4">
        <span>Quelle: Yahoo Finance</span>
        <span>Keine Anlageberatung</span>
        <span><kbd className="text-terminal-text">ESC</kbd> schliessen</span>
      </div>
    </footer>
  )
}
