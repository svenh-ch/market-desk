import type { DataMeta } from '../../types'
import { age, dateTime } from '../../lib/format'

interface Props {
  meta: Partial<DataMeta> | null | undefined
  /** Zeitpunkt laut Börse (bei Kursen); sonst wird der Abrufzeitpunkt gezeigt */
  marketTime?: string | null
  className?: string
}

/**
 * Zeigt, woher Daten kommen und wie alt sie sind:
 * "Kurs 27.10.2026, 17:31 · Yahoo Finance · aus Cache (2 Min.)"
 * Veraltete Daten und Fehler werden deutlich markiert.
 */
export default function DataStamp({ meta, marketTime, className = '' }: Props) {
  if (!meta) return null
  const when = marketTime ? `Kurs ${dateTime(marketTime)}` : `Abgerufen ${dateTime(meta.fetched_at)}`
  const title = [
    `Quelle: ${meta.source ?? '–'}`,
    `Abgerufen: ${dateTime(meta.fetched_at)}`,
    marketTime ? `Zeitpunkt des Kurses laut Börse: ${dateTime(marketTime)}` : null,
    meta.from_cache ? `Aus Zwischenspeicher, ${age(meta.cache_age_seconds ?? 0)} alt` : 'Frisch abgerufen',
    'Kurse können je nach Börse bis ca. 15 Minuten verzögert sein.',
  ].filter(Boolean).join('\n')

  return (
    <span className={`text-[10px] leading-tight ${meta.stale ? 'text-terminal-orange' : 'text-terminal-muted'} ${className}`} title={title}>
      {meta.stale && <span className="font-bold">VERALTET · </span>}
      {when} · {meta.source}
      {meta.from_cache && <> · aus Cache ({age(meta.cache_age_seconds ?? 0)})</>}
    </span>
  )
}

/** Deutliche Meldung, wenn Daten fehlen. */
export function Unavailable({ text }: { text?: string | null }) {
  return (
    <div className="text-xs text-terminal-orange border border-terminal-orange/40 bg-terminal-orange/5 px-3 py-2">
      Daten nicht verfügbar{text ? ` – ${text}` : ''}
    </div>
  )
}
