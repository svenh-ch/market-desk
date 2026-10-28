import { useState, useEffect } from 'react'
import { NavigateFunction } from 'react-router-dom'
import { useStore } from '../../store/useStore'
import { REFRESH_SECONDS } from '../../hooks/useQuotes'
import { time } from '../../lib/format'

interface Props {
  currentPath: string
  navigate: NavigateFunction
}

const NAV_ITEMS = [
  { label: 'MARKT',     path: '/',          key: 'F1' },
  { label: 'NEWS',      path: '/news',      key: 'F2' },
  { label: 'PORTFOLIO', path: '/portfolio', key: 'F3' },
  { label: 'WATCHLIST', path: '/watchlist', key: 'F4' },
  { label: 'EXPLORER',  path: '/explorer',  key: 'F5' },
]

export default function Header({ currentPath, navigate }: Props) {
  const lastRefresh = useStore(s => s.lastRefresh)
  const refreshError = useStore(s => s.refreshError)
  const [now, setNow] = useState(new Date())
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id) }, [])

  const activePath = '/' + currentPath.split('/')[1]

  return (
    <header className="flex items-center justify-between bg-terminal-header border-b border-terminal-border px-3 py-1.5 select-none shrink-0 gap-3">
      <div className="flex items-center gap-3">
        <div className="text-terminal-orange font-bold text-sm tracking-widest border border-terminal-orange px-2 py-0.5">
          MARKET DESK
        </div>
      </div>

      <nav className="flex items-center gap-0.5">
        {NAV_ITEMS.map(({ label, path, key }) => {
          const active = activePath === path || (path !== '/' && currentPath.startsWith(path))
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`px-2.5 py-1 text-xs border transition-colors ${
                active
                  ? 'bg-terminal-orange text-black border-terminal-orange font-bold'
                  : 'border-transparent text-terminal-text-dim hover:border-terminal-orange hover:text-terminal-orange'
              }`}
            >
              <span className="mr-1 text-xs opacity-60">{key}</span>
              {label}
            </button>
          )
        })}
      </nav>

      <div className="flex items-center gap-4 text-xs text-terminal-text-dim">
        <div
          className="flex items-center gap-1.5"
          title={`Kurse von Yahoo Finance, automatisch alle ${REFRESH_SECONDS} Sekunden aktualisiert.\nJe nach Börse bis ca. 15 Minuten verzögert.`}
        >
          <div className={`w-1.5 h-1.5 rounded-full ${refreshError ? 'bg-terminal-red' : lastRefresh ? 'bg-terminal-green' : 'bg-terminal-muted'}`} />
          <span className={refreshError ? 'text-terminal-red' : ''}>
            {refreshError ? 'KEINE VERBINDUNG' : lastRefresh ? `Aktualisiert ${time(lastRefresh)}` : 'Verbinde …'}
          </span>
          <span className="text-terminal-muted hidden xl:inline">· Kurse ggf. ~15 Min. verzögert</span>
        </div>
        <div className="text-terminal-text font-medium tabular-nums">
          {now.toLocaleTimeString('de-CH')}
        </div>
      </div>
    </header>
  )
}
