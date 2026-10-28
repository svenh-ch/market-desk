import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { portfolioApi, alertsApi, errorText } from '../../services/api'
import type { PortfolioSummary, Alert } from '../../types'
import { REFRESH_SECONDS } from '../../hooks/useQuotes'
import { dateTime, num, pct, price } from '../../lib/format'

const signed = (n: number | null) => (n == null ? '–' : `${n >= 0 ? '+' : ''}${num(n)}`)
const color = (n: number | null) => (n == null ? 'text-terminal-muted' : n >= 0 ? 'text-terminal-green' : 'text-terminal-red')

export default function Portfolio() {
  const navigate = useNavigate()
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loadError, setLoadError] = useState('')
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [addForm, setAddForm] = useState({ symbol: '', quantity: '', avg_cost: '' })
  const [alertForm, setAlertForm] = useState({ symbol: '', condition: 'above' as 'above' | 'below', threshold: '' })
  const [addError, setAddError] = useState('')
  const [alertError, setAlertError] = useState('')

  const refresh = () =>
    Promise.all([portfolioApi.get(), alertsApi.list()])
      .then(([p, a]) => { setPortfolio(p); setAlerts(a); setLoadError(''); setUpdatedAt(new Date().toISOString()) })
      .catch(() => setLoadError('Server nicht erreichbar.'))

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, REFRESH_SECONDS * 1000)
    return () => clearInterval(id)
  }, [])

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setAddError('')
    const quantity = parseFloat(addForm.quantity), avg_cost = parseFloat(addForm.avg_cost)
    if (!addForm.symbol.trim() || isNaN(quantity) || isNaN(avg_cost)) { setAddError('Bitte alle Felder ausfüllen.'); return }
    try {
      await portfolioApi.add({ symbol: addForm.symbol.trim().toUpperCase(), quantity, avg_cost })
      setAddForm({ symbol: '', quantity: '', avg_cost: '' })
      refresh()
    } catch (err) { setAddError(errorText(err)) }
  }

  const handleAddAlert = async (e: React.FormEvent) => {
    e.preventDefault()
    setAlertError('')
    const threshold = parseFloat(alertForm.threshold)
    if (!alertForm.symbol.trim() || isNaN(threshold)) { setAlertError('Bitte Ticker und Preis angeben.'); return }
    try {
      await alertsApi.create({ symbol: alertForm.symbol.trim().toUpperCase(), condition: alertForm.condition, threshold })
      setAlertForm({ symbol: '', condition: 'above', threshold: '' })
      refresh()
    } catch (err) { setAlertError(errorText(err)) }
  }

  if (!portfolio) return (
    <div className="flex items-center justify-center h-full text-sm text-terminal-text-dim">
      {loadError || 'Lade Portfolio …'}
    </div>
  )

  const p = portfolio
  const cur = p.currency ?? ''

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'PORTFOLIOWERT', value: p.total_value != null ? `${num(p.total_value)} ${cur}` : '–', cls: 'text-terminal-text' },
          { label: 'GEWINN/VERLUST', value: p.total_pnl != null ? `${signed(p.total_pnl)} ${cur} (${pct(p.total_pnl_pct)})` : '–', cls: color(p.total_pnl) },
          { label: 'HEUTE', value: p.day_pnl != null ? `${signed(p.day_pnl)} ${cur}` : '–', cls: color(p.day_pnl) },
          { label: 'POSITIONEN', value: String(p.positions.length), cls: 'text-terminal-orange' },
        ].map(card => (
          <div key={card.label} className="panel p-3">
            <div className="text-xs text-terminal-text-dim mb-1">{card.label}</div>
            <div className={`text-base font-semibold ${card.cls}`}>{card.value}</div>
          </div>
        ))}
      </div>
      <div className="text-[11px] text-terminal-muted">
        {p.totals_note && <span className="text-terminal-orange mr-2">{p.totals_note}</span>}
        Kurse: Yahoo Finance · zuletzt aktualisiert {dateTime(updatedAt)} · je nach Börse bis ca. 15 Min. verzögert
        {loadError && <span className="text-terminal-red ml-2">{loadError}</span>}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 panel p-0 overflow-hidden">
          <div className="px-4 py-2 border-b border-terminal-border text-xs text-terminal-cyan font-semibold">POSITIONEN</div>
          {p.positions.length === 0 ? (
            <div className="text-center py-12 text-terminal-text-dim text-sm">Noch keine Positionen. Unten eine erfassen.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-terminal-border text-terminal-text-dim">
                    {['TICKER', 'ANZAHL', 'EINSTAND', 'KURS', 'WERT', 'G/V', 'HEUTE', ''].map(h => (
                      <th key={h} className="text-left px-3 py-2 font-normal">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {p.positions.map(pos => (
                    <tr key={pos.id} className="border-b border-terminal-border/30 hover:bg-terminal-hover">
                      <td className="px-3 py-2">
                        <button onClick={() => navigate(`/asset/${encodeURIComponent(pos.symbol)}`)}
                          className="text-terminal-orange font-semibold hover:underline">{pos.symbol}</button>
                        <div className="text-terminal-text-dim truncate max-w-[120px]">{pos.name}</div>
                      </td>
                      <td className="px-3 py-2">{num(pos.quantity, 0)}</td>
                      <td className="px-3 py-2">{price(pos.avg_cost)} <span className="text-terminal-muted">{pos.currency}</span></td>
                      <td className="px-3 py-2" title={pos.quote_time ? `Kurs vom ${dateTime(pos.quote_time)}` : ''}>
                        {pos.current_price != null ? price(pos.current_price) : <span className="text-terminal-orange" title={pos.quote_error ?? ''}>nicht verfügbar</span>}
                      </td>
                      <td className="px-3 py-2 font-medium">{pos.market_value != null ? num(pos.market_value) : '–'}</td>
                      <td className={`px-3 py-2 font-medium ${color(pos.pnl)}`}>
                        {signed(pos.pnl)}<br /><span className="opacity-75">{pct(pos.pnl_pct)}</span>
                      </td>
                      <td className={`px-3 py-2 ${color(pos.day_pnl)}`}>{signed(pos.day_pnl)}</td>
                      <td className="px-3 py-2">
                        <button onClick={async () => { await portfolioApi.remove(pos.id); refresh() }}
                          className="text-terminal-muted hover:text-terminal-red" title="Entfernen">✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="border-t border-terminal-border px-4 py-3">
            <div className="text-xs text-terminal-cyan font-semibold mb-2">POSITION ERFASSEN</div>
            <form onSubmit={handleAdd} className="flex flex-wrap gap-2 items-end">
              {[
                { key: 'symbol', label: 'TICKER', ph: 'NESN.SW', w: 'w-28', type: 'text' },
                { key: 'quantity', label: 'ANZAHL', ph: '10', w: 'w-24', type: 'number' },
                { key: 'avg_cost', label: 'EINSTANDSPREIS (in Handelswährung)', ph: '85.00', w: 'w-40', type: 'number' },
              ].map(f => (
                <div key={f.key}>
                  <div className="text-xs text-terminal-text-dim mb-1">{f.label}</div>
                  <input type={f.type} step="any" min="0" placeholder={f.ph}
                    value={addForm[f.key as keyof typeof addForm]}
                    onChange={e => setAddForm(v => ({ ...v, [f.key]: e.target.value }))}
                    className={`bg-terminal-bg border border-terminal-border px-2 py-1 text-xs text-terminal-text outline-none focus:border-terminal-orange ${f.w}`} />
                </div>
              ))}
              <button type="submit" className="px-4 py-1 text-xs border border-terminal-orange text-terminal-orange hover:bg-terminal-orange hover:text-black">
                ERFASSEN
              </button>
              {addError && <span className="text-terminal-red text-xs">{addError}</span>}
            </form>
          </div>
        </div>

        <div className="panel overflow-hidden">
          <div className="px-4 py-2 border-b border-terminal-border text-xs text-terminal-cyan font-semibold">PREISALARME</div>
          <div className="p-4 space-y-2 max-h-64 overflow-y-auto">
            {alerts.length === 0 && <div className="text-terminal-text-dim text-xs">Keine Alarme gesetzt.</div>}
            {alerts.map(a => (
              <div key={a.id} className={`flex items-center justify-between text-xs px-2 py-1.5 border ${
                a.triggered ? 'border-terminal-orange bg-terminal-orange/10' : 'border-terminal-border'}`}>
                <div>
                  <span className="text-terminal-orange font-semibold">{a.symbol}</span>
                  <span className="text-terminal-text-dim mx-1">{a.condition === 'above' ? 'über' : 'unter'}</span>
                  <span>{price(a.threshold)}</span>
                  {a.current_price != null && <span className="text-terminal-muted ml-2">(aktuell {price(a.current_price)})</span>}
                  {a.triggered && <span className="ml-2 text-terminal-orange">⚡ AUSGELÖST {dateTime(a.triggered_at)}</span>}
                </div>
                <button onClick={async () => { await alertsApi.delete(a.id); refresh() }} className="text-terminal-muted hover:text-terminal-red">✕</button>
              </div>
            ))}
          </div>
          <div className="border-t border-terminal-border px-4 py-3">
            <div className="text-xs text-terminal-cyan font-semibold mb-2">ALARM SETZEN</div>
            <form onSubmit={handleAddAlert} className="space-y-2">
              <input value={alertForm.symbol} onChange={e => setAlertForm(f => ({ ...f, symbol: e.target.value }))}
                placeholder="Ticker (z. B. AAPL)" className="w-full bg-terminal-bg border border-terminal-border px-2 py-1 text-xs text-terminal-text outline-none focus:border-terminal-orange uppercase" />
              <div className="flex gap-2">
                <select value={alertForm.condition} onChange={e => setAlertForm(f => ({ ...f, condition: e.target.value as 'above' | 'below' }))}
                  className="flex-1 bg-terminal-bg border border-terminal-border px-2 py-1 text-xs text-terminal-text outline-none">
                  <option value="above">Kurs über</option>
                  <option value="below">Kurs unter</option>
                </select>
                <input type="number" step="any" min="0" placeholder="Preis" value={alertForm.threshold}
                  onChange={e => setAlertForm(f => ({ ...f, threshold: e.target.value }))}
                  className="w-24 bg-terminal-bg border border-terminal-border px-2 py-1 text-xs text-terminal-text outline-none" />
              </div>
              <button type="submit" className="w-full py-1 text-xs border border-terminal-orange text-terminal-orange hover:bg-terminal-orange hover:text-black">
                ALARM SETZEN
              </button>
              {alertError && <div className="text-terminal-red text-xs">{alertError}</div>}
            </form>
            <div className="text-[10px] text-terminal-muted mt-2">Alarme werden nur geprüft, solange die App offen ist.</div>
          </div>
        </div>
      </div>
    </div>
  )
}
