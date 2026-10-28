import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { relationshipsApi } from '../../services/api'
import type { SupplyLink, SupplyResponse } from '../../types'
import { num } from '../../lib/format'

const W = 900, H = 520, CX = W / 2, CY = H / 2

/** Netzwerk: Lieferanten links, Kunden rechts. Linienstärke = Umsatzanteil, gestrichelt = unsicher. */
export default function SupplyChainTab({ symbol }: { symbol: string }) {
  const navigate = useNavigate()
  const [resp, setResp] = useState<SupplyResponse | null>(null)
  const [selected, setSelected] = useState<SupplyLink | null>(null)

  const load = () => relationshipsApi.get(symbol).then(setResp).catch(() => setResp(null))
  useEffect(() => { setResp(null); setSelected(null); load() }, [symbol]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (resp?.status !== 'running') return
    const t = setTimeout(load, 3000)
    return () => clearTimeout(t)
  }, [resp]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!resp) return <div className="text-xs text-terminal-muted">Lade …</div>
  const links = resp.graph.links
  const running = resp.status === 'running'

  if (!links.length) {
    return (
      <div className="panel p-8 text-center space-y-2">
        {running ? <>
          <div className="text-sm text-terminal-text-dim">Berichte werden ausgewertet …</div>
          <div className="text-xs text-terminal-muted">{resp.message}</div>
        </> : <>
          <div className="text-sm text-terminal-text">Keine öffentlichen Lieferkettendaten gefunden.</div>
          <div className="text-xs text-terminal-muted">Geprüft: eigener SEC-/ESEF-Jahresbericht (falls vorhanden) und Nennungen in Berichten anderer Firmen. Es wird nichts ergänzt oder geschätzt.</div>
        </>}
      </div>
    )
  }

  const suppliers = links.filter(l => l.type === 'supplier')
  const customers = links.filter(l => l.type === 'customer')
  const pos = (i: number, n: number, side: -1 | 1) => ({
    x: CX + side * 330, y: n === 1 ? CY : 40 + (i * (H - 80)) / (n - 1),
  })
  const uncertain = (l: SupplyLink) => l.confidence !== 'bestätigt' || l.mapping_certain === false
  const width = (l: SupplyLink) => (l.revenue_share ? Math.min(2 + l.revenue_share / 3, 12) : 1.5)

  const renderSide = (list: SupplyLink[], side: -1 | 1) => list.map((l, i) => {
    const p = pos(i, list.length, side)
    const color = side === -1 ? '#10b981' : '#3b82f6'
    const active = selected === l
    return (
      <g key={`${side}-${i}`}>
        <line x1={CX} y1={CY} x2={p.x} y2={p.y} stroke={color} strokeOpacity={active ? 1 : 0.6}
          strokeWidth={width(l) + (active ? 1.5 : 0)} strokeDasharray={uncertain(l) ? '6 5' : undefined}
          className="cursor-pointer" onClick={() => setSelected(l)} />
        {/* breiter, unsichtbarer Klickbereich */}
        <line x1={CX} y1={CY} x2={p.x} y2={p.y} stroke="transparent" strokeWidth={14} className="cursor-pointer" onClick={() => setSelected(l)} />
        {l.revenue_share != null && (
          <text x={(CX + p.x) / 2} y={(CY + p.y) / 2 - 4} textAnchor="middle" fontSize="10" fill={color}>{num(l.revenue_share, 1)} %</text>
        )}
        <g className={l.other ? 'cursor-pointer' : ''} onClick={() => l.other ? navigate(`/asset/${encodeURIComponent(l.other)}`) : setSelected(l)}>
          <rect x={p.x - 70} y={p.y - 13} width={140} height={26} rx={4} fill="#0d1117" stroke={color} strokeDasharray={l.anonymous ? '3 3' : undefined} />
          <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize="11" fill="#e2e8f0">{l.label.length > 20 ? l.label.slice(0, 19) + '…' : l.label}</text>
        </g>
      </g>
    )
  })

  return (
    <div className="space-y-3">
      <div className="flex justify-between text-[11px] text-terminal-text-dim flex-wrap gap-2">
        <span><span className="text-terminal-green">■</span> Lieferanten (links) · <span className="text-terminal-blue">■</span> Kunden (rechts) · Linienstärke = Umsatzanteil · gestrichelt = „wahrscheinlich“ bzw. unsichere Ticker-Zuordnung</span>
        <span>{running ? 'Wird noch ergänzt …' : 'Klick auf eine Linie zeigt die Quelle, Klick auf eine Firma öffnet sie'}</span>
      </div>
      <div className="panel overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[640px]" style={{ height: H }}>
          <text x={CX - 330} y={18} textAnchor="middle" fontSize="10" fill="#10b981" letterSpacing="2">LIEFERANTEN</text>
          <text x={CX + 330} y={18} textAnchor="middle" fontSize="10" fill="#3b82f6" letterSpacing="2">KUNDEN</text>
          {renderSide(suppliers, -1)}
          {renderSide(customers, 1)}
          <circle cx={CX} cy={CY} r={34} fill="#f59e0b" />
          <text x={CX} y={CY + 4} textAnchor="middle" fontSize="12" fontWeight="bold" fill="#000">{symbol}</text>
        </svg>
      </div>

      {selected && (
        <div className="panel p-3 text-xs space-y-1 border-terminal-orange">
          <div className="flex justify-between">
            <span className="text-terminal-orange font-semibold">
              {selected.label} – {selected.type === 'customer' ? 'Kunde' : 'Lieferant'} von {symbol} ({selected.confidence})
            </span>
            <button onClick={() => setSelected(null)} className="text-terminal-muted hover:text-terminal-red">✕</button>
          </div>
          {selected.revenue_share != null && <div>Umsatzanteil: <b>{num(selected.revenue_share, 1)} %</b> ({selected.share_basis})</div>}
          <div>Quelle: {selected.source_doc} · {selected.section ?? '–'} · {selected.via}</div>
          {selected.name_in_report && <div>Name im Bericht: „{selected.name_in_report}“{selected.mapping_certain === false && <span className="text-terminal-orange"> – Ticker-Zuordnung unsicher</span>}</div>}
          {selected.quote && <blockquote className="border-l-2 border-terminal-border pl-2 text-terminal-text-dim italic">„{selected.quote}“</blockquote>}
          <div className="text-[10px] text-terminal-muted">Methode: {selected.method}</div>
          {selected.source_url && <a href={selected.source_url} target="_blank" rel="noopener noreferrer" className="text-terminal-cyan hover:text-terminal-orange">Originalbericht öffnen ↗</a>}
        </div>
      )}
      <div className="text-[10px] text-terminal-muted">
        Nur Verbindungen mit Beleg aus offiziellen Berichten (SEC 10-K/20-F, ESEF). Anonyme Grosskunden („one direct customer“) werden nicht zugeordnet.
        Ein Umsatzanteil bezieht sich immer auf den Umsatz des berichtenden Unternehmens.
      </div>
    </div>
  )
}
