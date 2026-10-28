import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { scoreApi } from '../../services/api'
import type { Color, ScoreMetric, ScoreResponse } from '../../types'
import { dateTime, num } from '../../lib/format'

const COLOR_TEXT: Record<Color, string> = {
  green: 'text-terminal-green', yellow: 'text-yellow-400', red: 'text-terminal-red', grey: 'text-terminal-muted',
}
const COLOR_BG: Record<Color, string> = {
  green: 'bg-terminal-green', yellow: 'bg-yellow-400', red: 'bg-terminal-red', grey: 'bg-terminal-muted',
}
const PILLAR_ORDER = ['quality', 'value', 'momentum', 'safety']
const PERCENT_KEYS = new Set(['gpoa', 'roe', 'roa', 'margin_stability', 'fcf_yield', 'earnings_yield', 'mom_12_1', 'leverage', 'volatility'])

function fmtValue(m: ScoreMetric, v: number | null | undefined): string {
  if (v == null) return '–'
  if (m.key === 'piotroski_f') return String(v)
  if (PERCENT_KEYS.has(m.key)) return `${num(v * 100, 1)} %`
  return num(v, 2)
}

function Dot({ c }: { c: Color }) {
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${COLOR_BG[c]}`} />
}

export default function ScoreTab({ symbol }: { symbol: string }) {
  const navigate = useNavigate()
  const [resp, setResp] = useState<ScoreResponse | null>(null)
  const [failed, setFailed] = useState(false)
  const [showPeers, setShowPeers] = useState(false)

  const load = (refresh = false) => {
    setFailed(false)
    scoreApi.get(symbol, refresh).then(setResp).catch(() => setFailed(true))
  }
  useEffect(() => { setResp(null); load() }, [symbol]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {  // während der Berechnung alle 2 s nachfragen
    if (resp?.status !== 'running') return
    const t = setTimeout(() => load(), 2000)
    return () => clearTimeout(t)
  }, [resp]) // eslint-disable-line react-hooks/exhaustive-deps

  if (failed) return <div className="text-xs text-terminal-red">Server nicht erreichbar.</div>
  if (!resp || resp.status === 'running') {
    return (
      <div className="panel p-6 space-y-2">
        <div className="text-xs text-terminal-text-dim">Score wird berechnet (Vergleichsfirmen, Berichte, Kurse) …</div>
        <div className="h-1.5 bg-terminal-border rounded"><div className="h-1.5 bg-terminal-orange rounded transition-all" style={{ width: `${resp?.progress ?? 2}%` }} /></div>
        <div className="text-[11px] text-terminal-muted">{resp?.message}</div>
      </div>
    )
  }
  if (resp.status === 'error' || !resp.result) return <div className="text-xs text-terminal-red">{resp.error ?? 'Fehler'}</div>
  const r = resp.result
  if (!r.available) return <div className="text-xs text-terminal-orange">Score nicht verfügbar – {r.error}</div>

  const enabled = Object.values(r.metrics).filter(m => m.enabled)
  const counts = { green: 0, yellow: 0, red: 0, grey: 0 } as Record<Color, number>
  enabled.forEach(m => { counts[m.color] += 1 })

  return (
    <div className="space-y-3">
      <div className="text-xs border border-terminal-orange/50 bg-terminal-orange/10 text-terminal-orange px-3 py-2">
        {r.disclaimer}
      </div>

      {/* Gesamtscore + Säulen */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
        <div className="panel p-4 flex flex-col items-center justify-center text-center">
          <div className="text-[11px] text-terminal-text-dim">GESAMTSCORE (0–100)</div>
          <div className={`text-4xl font-bold ${COLOR_TEXT[r.overall_color]}`}>{r.overall != null ? num(r.overall, 0) : '–'}</div>
          <div className="text-[11px] text-terminal-muted mt-1">Datenabdeckung {r.coverage} %</div>
          {r.overall_note && <div className="text-[11px] text-terminal-orange mt-1">{r.overall_note}</div>}
          <div className="flex gap-2 mt-2 text-[11px]">
            <span className="text-terminal-green">{counts.green} grün</span>
            <span className="text-yellow-400">{counts.yellow} gelb</span>
            <span className="text-terminal-red">{counts.red} rot</span>
            <span className="text-terminal-muted">{counts.grey} grau</span>
          </div>
        </div>
        {PILLAR_ORDER.map(k => {
          const p = r.pillars[k]
          return (
            <div key={k} className="panel p-4" title={`Gewicht ${num(p.weight * 100, 0)} % · ${p.metrics_used}/${p.metrics_total} Kennzahlen mit Daten`}>
              <div className="text-[11px] text-terminal-text-dim">{p.label.toUpperCase()}</div>
              <div className={`text-2xl font-bold ${COLOR_TEXT[p.color]}`}>{p.score != null ? num(p.score, 0) : '–'}</div>
              <div className="h-1.5 bg-terminal-border rounded mt-2">
                <div className={`h-1.5 rounded ${COLOR_BG[p.color]}`} style={{ width: `${p.score ?? 0}%` }} />
              </div>
              <div className="text-[10px] text-terminal-muted mt-1">{p.metrics_used}/{p.metrics_total} Kennzahlen · Gewicht {num(p.weight * 100, 0)} %</div>
            </div>
          )
        })}
      </div>

      {/* Vergleichsgruppe */}
      <div className="panel p-3 text-xs space-y-1">
        <div className="flex justify-between flex-wrap gap-2">
          <span><span className="text-terminal-text-dim">Vergleichsgruppe: </span>{r.peer_group.level} · {r.peer_group.with_data} Firmen mit Daten
            {!r.peer_group.enough && <span className="text-terminal-orange"> (weniger als 8 – unsicher)</span>}</span>
          <button onClick={() => setShowPeers(v => !v)} className="text-terminal-cyan hover:text-terminal-orange">{showPeers ? 'ausblenden' : 'Firmen anzeigen'}</button>
        </div>
        {showPeers && (
          <div className="flex flex-wrap gap-2 pt-1">
            {r.peer_group.members.map(m => (
              <button key={m.symbol} onClick={() => navigate(`/asset/${encodeURIComponent(m.symbol)}`)}
                className="border border-terminal-border px-2 py-0.5 hover:border-terminal-orange" title={`${m.name} · ${m.country ?? ''}`}>
                {m.symbol}
              </button>
            ))}
          </div>
        )}
        <div className="text-[10px] text-terminal-muted">
          Quelle Gruppe: {r.peer_group.source} ({dateTime(r.peer_group.fetched_at)}) · Bilanz: {r.fundamentals.source} {r.fundamentals.currency},
          Geschäftsjahr bis {r.fundamentals.period_end}{r.fundamentals.filed ? `, eingereicht ${r.fundamentals.filed}` : ''} · Kurse bis {r.market.price_date} (Index {r.market.index})
          {r.damodaran && <> · Branchenwert: {r.damodaran.source}, „{r.damodaran.industry}“, Stand {r.damodaran.updated}</>}
        </div>
      </div>

      {/* Kennzahlen je Säule */}
      {PILLAR_ORDER.map(pk => (
        <div key={pk} className="panel overflow-x-auto">
          <div className="px-3 py-2 border-b border-terminal-border text-xs text-terminal-cyan font-semibold">{r.pillars[pk].label.toUpperCase()}</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-terminal-text-dim border-b border-terminal-border/50">
                <th className="text-left px-3 py-1.5 font-normal">Kennzahl</th>
                <th className="text-right px-3 py-1.5 font-normal">Firma</th>
                <th className="text-right px-3 py-1.5 font-normal">Median Gruppe</th>
                <th className="text-right px-3 py-1.5 font-normal">Damodaran</th>
                <th className="text-left px-3 py-1.5 font-normal w-48">Perzentil in der Gruppe</th>
              </tr>
            </thead>
            <tbody>
              {Object.values(r.metrics).filter(m => m.pillar === pk).map(m => (
                <tr key={m.key} className="border-b border-terminal-border/30"
                  title={[`Begründung: ${m.literature}`, `Daten: ${m.data_source ?? '–'}`,
                          `Vergleichswerte: ${m.peer_count}`, m.reason ? `Hinweis: ${m.reason}` : null,
                          !m.enabled ? 'Fliesst nicht in den Score ein.' : null].filter(Boolean).join('\n')}>
                  <td className="px-3 py-1.5"><span className="inline-flex items-center gap-2"><Dot c={m.color} />{m.label}{!m.enabled && <span className="text-terminal-muted"> (nur Info)</span>}</span></td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{fmtValue(m, m.value)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-terminal-text-dim">{fmtValue(m, m.peer_median)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-terminal-text-dim">{m.damodaran != null ? num(m.damodaran, m.key === 'roe' ? 3 : 1) : '–'}</td>
                  <td className="px-3 py-1.5">
                    {m.percentile != null ? (
                      <span className="flex items-center gap-2">
                        <span className="flex-1 h-1.5 bg-terminal-border rounded"><span className={`block h-1.5 rounded ${COLOR_BG[m.color]}`} style={{ width: `${m.percentile}%` }} /></span>
                        <span className={`w-10 text-right ${COLOR_TEXT[m.color]}`}>{num(m.percentile, 0)}</span>
                      </span>
                    ) : <span className="text-terminal-muted">{m.reason ?? '–'}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {/* Absolute Einordnungen */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="panel p-3 text-xs space-y-1">
          <div className="text-terminal-cyan font-semibold">ALTMAN – ABSOLUTE ZONE</div>
          {r.altman_absolute ? <>
            <div className={COLOR_TEXT[r.altman_absolute.color]}><Dot c={r.altman_absolute.color} /> {r.altman_absolute.model}: <b>{num(r.altman_absolute.value, 2)}</b></div>
            <div className="text-[10px] text-terminal-muted">{r.altman_absolute.rule}</div>
          </> : <div className="text-terminal-muted">Nicht berechenbar (Daten fehlen oder Finanzfirma).</div>}
        </div>
        <div className="panel p-3 text-xs space-y-1">
          <div className="text-terminal-cyan font-semibold">PIOTROSKI F-SCORE – 9 SIGNALE</div>
          {r.piotroski_absolute && (
            <div className={COLOR_TEXT[r.piotroski_absolute.color]}><Dot c={r.piotroski_absolute.color} /> F-Score <b>{r.piotroski_absolute.value}</b> von 9 <span className="text-[10px] text-terminal-muted">({r.piotroski_absolute.rule})</span></div>
          )}
          {r.piotroski ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
              {Object.entries(r.piotroski.signals).map(([k, v]) => (
                <div key={k} className={v == null ? 'text-terminal-muted' : v ? 'text-terminal-green' : 'text-terminal-red'}>
                  {v == null ? '○' : v ? '✓' : '✗'} {k}
                </div>
              ))}
            </div>
          ) : <div className="text-terminal-muted">Nicht berechenbar (mind. 3 Geschäftsjahre nötig).</div>}
          {r.piotroski?.note && <div className="text-[10px] text-terminal-orange">{r.piotroski.note}</div>}
        </div>
      </div>

      {(r.warnings.length > 0 || r.fundamentals.deviations_vs_yahoo.length > 0) && (
        <div className="panel p-3 text-xs space-y-1">
          <div className="text-terminal-orange font-semibold">HINWEISE ZU DEN DATEN</div>
          {r.warnings.map((w, i) => <div key={i} className="text-terminal-text-dim">• {w}</div>)}
          {r.fundamentals.deviations_vs_yahoo.map((d, i) => (
            <div key={i} className="text-terminal-orange">• {d.item}: Bericht {num(d.official, 0)} vs. Yahoo {num(d.yahoo, 0)} (Abweichung {num(d.deviation_pct, 1)} %)</div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-[10px] text-terminal-muted">
        <span>Berechnet {dateTime(r.computed_at)}{resp.cache_age_seconds ? ' · aus Cache' : ''} · Methodik: SCORE_METHODIK.md · Grenzwerte: backend/app/scoring_config.py</span>
        <button onClick={() => { setResp(null); load(true) }} className="text-terminal-cyan hover:text-terminal-orange">Neu berechnen</button>
      </div>
    </div>
  )
}
