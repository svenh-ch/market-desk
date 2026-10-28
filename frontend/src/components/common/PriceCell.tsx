import type { Quote } from '../../types'
import { num, pct, price } from '../../lib/format'

/** Kurs mit Währung und Tagesveränderung – oder klar "nicht verfügbar". */
export default function PriceCell({ q, big = false }: { q: Quote | undefined; big?: boolean }) {
  if (!q) return <span className="text-terminal-muted text-xs animate-pulse">lädt …</span>
  if (!q.available || q.price == null) {
    return <span className="text-terminal-orange text-xs" title={q.error ?? ''}>nicht verfügbar</span>
  }
  const up = (q.change_pct ?? 0) >= 0
  return (
    <span className="inline-flex flex-col">
      <span className="inline-flex items-baseline gap-1">
        <span className={`${big ? 'text-3xl font-bold' : 'text-sm font-semibold'} text-terminal-text tabular-nums`}>{price(q.price)}</span>
        <span className={`${big ? 'text-sm' : 'text-[10px]'} text-terminal-muted`}>{q.currency ?? ''}</span>
        {q.stale && <span className="text-[10px] text-terminal-orange font-bold" title={q.error ?? ''}>VERALTET</span>}
      </span>
      {q.change_pct != null && (
        <span className={`${big ? 'text-sm' : 'text-xs'} tabular-nums ${up ? 'text-terminal-green' : 'text-terminal-red'}`}>
          {up ? '▲' : '▼'} {q.price < 1 ? price(Math.abs(q.change ?? 0)) : num(Math.abs(q.change ?? 0))} ({pct(q.change_pct)})
        </span>
      )}
    </span>
  )
}
