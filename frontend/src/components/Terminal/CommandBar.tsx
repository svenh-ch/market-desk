import { useState, useEffect, useRef, KeyboardEvent } from 'react'
import { NavigateFunction } from 'react-router-dom'
import { useStore } from '../../store/useStore'
import { marketApi } from '../../services/api'
import type { SearchResult } from '../../types'

interface Props { navigate: NavigateFunction }

const HELP_LINES = [
  '  <TICKER>           → Detailseite öffnen (z. B. AAPL, NESN.SW, BTC-USD)',
  '  Firmenname tippen  → Vorschläge erscheinen, mit TAB übernehmen',
  '  WATCH / F4         → Watchlist',
  '  XPLORE / F5        → Explorer (Auswahlliste)',
  '  PORT / F3          → Portfolio',
  '  NEWS / F2          → Nachrichten',
  '  HOME / F1          → Startseite',
  '  HELP               → diese Hilfe',
]

export default function CommandBar({ navigate }: Props) {
  const { terminalInput, setTerminalInput, setTerminalOpen } = useStore()
  const [history,     setHistory]     = useState<string[]>([])
  const [histIdx,     setHistIdx]     = useState(-1)
  const [output,      setOutput]      = useState<string[]>(['Market Desk  —  HELP für Befehle'])
  const [suggestions, setSuggestions] = useState<SearchResult[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  useEffect(() => {
    const v = terminalInput.trim()
    if (v.length < 2) { setSuggestions([]); return }
    const t = setTimeout(() => {
      marketApi.search(v).then(r => setSuggestions(r.results)).catch(() => setSuggestions([]))
    }, 250)
    return () => clearTimeout(t)
  }, [terminalInput])

  const close = () => { setTerminalOpen(false); setTerminalInput('') }

  const execute = (raw: string) => {
    const line  = raw.trim().toUpperCase()
    if (!line) return
    setHistory(h => [line, ...h.slice(0, 49)])
    setHistIdx(-1)
    setOutput(o => [...o, `> ${line}`])

    const parts = line.split(/\s+/)
    const sym   = parts[0]
    const cmd   = parts[1]

    if (line === 'HELP') { setOutput(o => [...o, ...HELP_LINES]); return }
    if (['PORT', 'PORTFOLIO'].includes(line)) { navigate('/portfolio'); close(); return }
    if (['NEWS'].includes(line))              { navigate('/news');      close(); return }
    if (['MRKT', 'MARKET', 'HOME'].includes(line)) { navigate('/'); close(); return }
    if (['WATCH', 'WATCHLIST'].includes(line)) { navigate('/watchlist'); close(); return }
    if (['XPLORE', 'EXPLORER', 'SCREEN'].includes(line)) { navigate('/explorer'); close(); return }

    if (sym.length >= 1 && !cmd) {
      navigate(`/asset/${encodeURIComponent(sym)}`)
      close()
      return
    }
    setOutput(o => [...o, `  Unbekannt: ${line}. HELP für Hilfe.`])
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      // Firmenname eingegeben (kein exakter Ticker)? Dann den ersten Suchtreffer nehmen
      const typed = terminalInput.trim().toUpperCase()
      const isCommand = ['HELP', 'PORT', 'PORTFOLIO', 'NEWS', 'MRKT', 'MARKET', 'HOME', 'WATCH', 'WATCHLIST', 'XPLORE', 'EXPLORER', 'SCREEN'].includes(typed)
      const exact = suggestions.some(s => s.symbol === typed)
      execute(!isCommand && !exact && suggestions.length ? suggestions[0].symbol : terminalInput)
      setTerminalInput(''); setSuggestions([])
    }
    else if (e.key === 'Escape') { close() }
    else if (e.key === 'ArrowUp') {
      e.preventDefault()
      const next = Math.min(histIdx + 1, history.length - 1)
      setHistIdx(next); setTerminalInput(history[next] ?? '')
    }
    else if (e.key === 'ArrowDown') {
      e.preventDefault()
      const next = Math.max(histIdx - 1, -1)
      setHistIdx(next); setTerminalInput(next === -1 ? '' : history[next])
    }
    else if (e.key === 'Tab' && suggestions.length > 0) {
      e.preventDefault()
      setTerminalInput(suggestions[0].symbol)
      setSuggestions([])
    }
  }

  return (
    <div className="border-b border-terminal-border bg-terminal-panel animate-fade-in shrink-0">
      {/* Output log */}
      <div className="px-4 py-2 max-h-28 overflow-y-auto text-xs space-y-0.5">
        {output.map((line, i) => (
          <div key={i} className={line.startsWith('>') ? 'text-terminal-orange' : 'text-terminal-text-dim'}>
            {line}
          </div>
        ))}
      </div>

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <div className="border-t border-terminal-border px-4 py-1 flex gap-4 flex-wrap items-center">
          {suggestions.slice(0, 10).map(s => (
            <button key={s.symbol}
              onMouseDown={() => { setTerminalInput(s.symbol); setSuggestions([]) }}
              className="text-xs text-terminal-cyan hover:text-terminal-orange transition-colors"
            >
              {s.symbol} <span className="text-terminal-muted">{s.name.slice(0, 22)}</span>
            </button>
          ))}
          <span className="text-terminal-muted text-xs ml-auto">TAB übernimmt</span>
        </div>
      )}

      {/* Input */}
      <div className="flex items-center gap-2 px-4 py-2 border-t border-terminal-border">
        <span className="text-terminal-orange font-bold text-sm select-none">›</span>
        <input ref={inputRef}
          value={terminalInput}
          onChange={e => setTerminalInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ticker, Firmenname oder Befehl (HELP)"
          className="flex-1 bg-transparent outline-none text-terminal-text text-sm placeholder-terminal-muted caret-terminal-orange"
          spellCheck={false} autoComplete="off"
        />
        <span className="text-terminal-muted text-xs">ESC schliessen · ↑↓ Verlauf</span>
      </div>
    </div>
  )
}
