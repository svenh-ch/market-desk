import { useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { useQuotePoller } from './hooks/useQuotes'
import { useStore } from './store/useStore'
import { watchlistApi } from './services/api'
import Header from './components/common/Header'
import StatusBar from './components/common/StatusBar'
import CommandBar from './components/Terminal/CommandBar'
import DashboardPage from './components/Dashboard/DashboardPage'
import AssetView from './components/AssetPage/AssetView'
import NewsFeed from './components/NewsFeed/NewsFeed'
import Portfolio from './components/Portfolio/Portfolio'
import WatchlistPage from './components/Watchlist/WatchlistPage'
import CompanyExplorer from './components/Dashboard/CompanyExplorer'

export default function App() {
  useQuotePoller()

  const navigate = useNavigate()
  const location = useLocation()
  const { terminalOpen, setTerminalOpen, setTerminalInput, setWatchlist } = useStore()

  useEffect(() => {
    watchlistApi.get().then(setWatchlist).catch(() => {})
  }, [setWatchlist])

  // Tastatur: F1–F5 wechseln die Seite, jede Taste öffnet die Befehlszeile
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.metaKey || e.ctrlKey || e.altKey) return

      if (e.key === 'Escape') { setTerminalOpen(false); setTerminalInput(''); return }
      if (e.key === 'F1') { navigate('/'); return }
      if (e.key === 'F2') { navigate('/news'); return }
      if (e.key === 'F3') { navigate('/portfolio'); return }
      if (e.key === 'F4') { navigate('/watchlist'); return }
      if (e.key === 'F5') { navigate('/explorer'); return }

      if (!terminalOpen && e.key.length === 1) {
        setTerminalOpen(true)
        setTerminalInput(e.key)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [terminalOpen, navigate, setTerminalOpen, setTerminalInput])

  return (
    <div className="flex flex-col h-screen bg-terminal-bg text-terminal-text font-mono overflow-hidden">
      <Header currentPath={location.pathname} navigate={navigate} />
      {terminalOpen && <CommandBar navigate={navigate} />}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/"              element={<DashboardPage />} />
          <Route path="/asset/:symbol" element={<AssetView />} />
          <Route path="/news"          element={<NewsFeed />} />
          <Route path="/portfolio"     element={<Portfolio />} />
          <Route path="/watchlist"     element={<WatchlistPage />} />
          <Route path="/explorer"      element={<CompanyExplorer />} />
        </Routes>
      </main>
      <StatusBar />
    </div>
  )
}
