import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { newsApi } from '../../services/api'
import type { NewsResponse } from '../../types'
import DataStamp, { Unavailable } from '../common/DataStamp'
import { dateTime } from '../../lib/format'

const FILTERS = ['ALLE', 'AAPL', 'MSFT', 'NVDA', 'NESN.SW', 'UBSG.SW', 'NOVN.SW', 'SAP', 'BTC-USD']

export default function NewsFeed() {
  const navigate = useNavigate()
  const [news, setNews] = useState<NewsResponse | null>(null)
  const [filter, setFilter] = useState('ALLE')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setNews(null); setFailed(false)
    newsApi.feed(filter === 'ALLE' ? undefined : filter, 30).then(setNews).catch(() => setFailed(true))
  }, [filter])

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 text-xs">
          <span className="text-terminal-orange font-semibold">NACHRICHTEN</span>
          {news && <DataStamp meta={news} />}
        </div>
        <div className="flex gap-1 flex-wrap">
          {FILTERS.map(sym => (
            <button key={sym} onClick={() => setFilter(sym)}
              className={`px-2.5 py-1 text-xs border transition-colors ${filter === sym
                ? 'border-terminal-orange text-terminal-orange bg-terminal-orange/10'
                : 'border-terminal-border text-terminal-text-dim hover:border-terminal-text-dim'}`}>
              {sym}
            </button>
          ))}
        </div>
      </div>

      {failed && <Unavailable text="Server nicht erreichbar." />}
      {!news && !failed && <div className="text-terminal-text-dim text-sm">Lade Nachrichten …</div>}
      {news?.error && <Unavailable text={news.error} />}
      {news && news.items.length === 0 && !news.error && <div className="text-xs text-terminal-text-dim">Keine aktuellen Nachrichten gefunden.</div>}

      <div className="space-y-2">
        {news?.items.map(item => (
          <article key={item.id} className="panel p-3 hover:border-terminal-orange transition-all">
            <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-sm text-terminal-text leading-snug font-medium hover:text-terminal-orange">
              {item.headline} <span className="text-terminal-muted">↗</span>
            </a>
            <div className="flex items-center gap-3 mt-2 text-xs flex-wrap">
              <span className="text-terminal-orange">{item.source}</span>
              <span className="text-terminal-muted">{dateTime(item.published_at)}</span>
              {item.symbols.slice(0, 6).map(s => (
                <button key={s} onClick={() => navigate(`/asset/${encodeURIComponent(s)}`)}
                  className="text-terminal-cyan hover:text-terminal-orange">{s}</button>
              ))}
            </div>
          </article>
        ))}
      </div>
      <div className="text-[11px] text-terminal-muted">Schlagzeilen über die Yahoo-Finance-Suche; Klick öffnet den Originalartikel im Browser.</div>
    </div>
  )
}
