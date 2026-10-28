import type { AssetInfo } from '../../types'
import { large, num } from '../../lib/format'
import DataStamp, { Unavailable } from '../common/DataStamp'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-terminal-border/50 text-xs">
      <span className="text-terminal-text-dim">{label}</span>
      <span className={value === '–' ? 'text-terminal-muted' : 'text-terminal-text font-medium'}>{value}</span>
    </div>
  )
}

/**
 * Kennzahlen direkt von Yahoo Finance – ohne eigene Bewertung.
 * (Eine farbige, branchenrelative Einordnung kommt im nächsten Ausbauschritt.)
 * Fehlende Werte erscheinen als "–".
 */
export default function KeyMetrics({ info }: { info: AssetInfo }) {
  if (!info.available) return <Unavailable text={info.error} />
  const cur = info.currency ?? ''
  const fin = info.financial_currency ?? cur
  const missing = [
    ['KGV', info.pe_ratio], ['KBV', info.price_to_book], ['EV/EBITDA', info.ev_ebitda], ['Marktkap.', info.market_cap],
  ].filter(([, v]) => v == null).map(([k]) => k)

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs text-terminal-cyan font-semibold">KENNZAHLEN</div>
        <DataStamp meta={info} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
        <div>
          <Row label="Marktkapitalisierung" value={info.market_cap != null ? `${large(info.market_cap)} ${cur}` : '–'} />
          <Row label="KGV (letzte 12 Mte.)" value={info.pe_ratio != null ? `${num(info.pe_ratio, 1)}x` : '–'} />
          <Row label="Kurs/Buchwert (KBV)" value={info.price_to_book != null ? `${num(info.price_to_book, 2)}x` : '–'} />
          <Row label="EV/EBITDA" value={info.ev_ebitda != null ? `${num(info.ev_ebitda, 1)}x` : '–'} />
          <Row label="Gewinn je Aktie" value={info.eps != null ? `${num(info.eps)} ${fin}` : '–'} />
          <Row label="Dividendenrendite" value={info.dividend_yield != null ? `${num(info.dividend_yield)} %` : '–'} />
        </div>
        <div>
          <Row label="Umsatz (12 Mte.)" value={info.revenue != null ? `${large(info.revenue)} ${fin}` : '–'} />
          <Row label="52-Wochen-Hoch" value={info.week_52_high != null ? `${num(info.week_52_high)} ${cur}` : '–'} />
          <Row label="52-Wochen-Tief" value={info.week_52_low != null ? `${num(info.week_52_low)} ${cur}` : '–'} />
          <Row label="Ø Volumen" value={info.avg_volume != null ? num(info.avg_volume, 0) : '–'} />
          <Row label="Mitarbeitende" value={info.employees != null ? num(info.employees, 0) : '–'} />
          <Row label="Branche" value={info.industry ?? '–'} />
        </div>
      </div>
      {missing.length > 0 && (
        <div className="text-[11px] text-terminal-orange">Von Yahoo nicht geliefert: {missing.join(', ')}</div>
      )}
      {fin !== cur && fin && (
        <div className="text-[11px] text-terminal-muted">Hinweis: Kurs in {cur}, Finanzberichte in {fin}.</div>
      )}
      <div className="text-[11px] text-terminal-muted">Reine Kennzahlen ohne Bewertung. Keine Anlageberatung.</div>
    </div>
  )
}
