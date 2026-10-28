/** Zahlen und Zeiten einheitlich formatieren (Schweizer Schreibweise). */

const LOCALE = 'de-CH'

export function num(n: number | null | undefined, dec = 2): string {
  if (n == null || Number.isNaN(n)) return '–'
  return n.toLocaleString(LOCALE, { minimumFractionDigits: dec, maximumFractionDigits: dec })
}

/** Sinnvolle Nachkommastellen für einen Kurs */
export function price(n: number | null | undefined): string {
  if (n == null) return '–'
  return num(n, n >= 1000 ? 2 : n < 1 ? 4 : 2)
}

export function pct(n: number | null | undefined, dec = 2): string {
  if (n == null) return '–'
  return `${n >= 0 ? '+' : ''}${num(n, dec)} %`
}

export function large(n: number | null | undefined): string {
  if (n == null) return '–'
  const a = Math.abs(n)
  if (a >= 1e12) return `${num(n / 1e12)} Bio.`
  if (a >= 1e9) return `${num(n / 1e9)} Mrd.`
  if (a >= 1e6) return `${num(n / 1e6)} Mio.`
  return num(n, 0)
}

export function time(iso: string | null | undefined): string {
  if (!iso) return '–'
  return new Date(iso).toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' })
}

/** Datum + Uhrzeit, z. B. "27.10.2026, 17:31" */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '–'
  return new Date(iso).toLocaleString(LOCALE, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function age(seconds: number): string {
  if (seconds < 60) return `${seconds} s`
  if (seconds < 3600) return `${Math.round(seconds / 60)} Min.`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} Std.`
  return `${Math.round(seconds / 86400)} Tg.`
}
