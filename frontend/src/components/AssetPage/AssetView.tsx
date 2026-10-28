import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { assetApi, newsApi, watchlistApi, errorText } from '../../services/api'
import { useStore } from '../../store/useStore'
import { useQuotes } from '../../hooks/useQuotes'
import CandlestickChart from './CandlestickChart'
import KeyMetrics from './KeyMetrics'
import ScoreTab from './ScoreTab'
import SupplyChainTab from './SupplyChainTab'
import PriceCell from '../common/PriceCell'
import DataStamp, { Unavailable } from '../common/DataStamp'
import type { AssetInfo, History, IndicatorsResponse, NewsResponse } from '../../types'
import { dateTime, num, price } from '../../lib/format'

type Tab = 'CHART' | 'SCORE' | 'DES' | 'KENNZ' | 'TECH' | 'LIEFER' | 'NEWS'

const TABS: { id: Tab; label: string }[] = [
  { id: 'CHART', label: 'CHART' },
  { id: 'SCORE', label: 'SCORE' },
  { id: 'DES', label: 'PROFIL' },
  { id: 'KENNZ', label: 'KENNZAHLEN' },
  { id: 'TECH', label: 'TECHNIK' },
  { id: 'LIEFER', label: 'LIEFERKETTE' },
  { id: 'NEWS', label: 'NEWS' },
]

export default function AssetView() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const sym = decodeURIComponent(symbol ?? '').toUpperCase()
  const q = useQuotes([sym])[sym]
  const { watchlist, setWatchlist } = useStore()

  const [tab, setTab] = useState<Tab>('CHART')
  const [days, setDays] = useState(365)
  const [info, setInfo] = useState<AssetInfo | null>(null)
  const [history, setHistory] = useState<History | null>(null)
  const [indicators, setIndicators] = useState<IndicatorsResponse | null>(null)
  const [news, setNews] = useState<NewsResponse | null>(null)
  const [watchMsg, setWatchMsg] = useState('')
  const watched = watchlist.some(i => i.symbol === sym)

  useEffect(() => {
    setInfo(null); setIndicators(null); setNews(null)
    assetApi.info(sym).then(setInfo).catch(() => setInfo(null))
    assetApi.indicators(sym).then(setIndicators).catch(() => setIndicators(null))
  }, [sym])

  useEffect(() => {
    setHistory(null)
    assetApi.history(sym, days).then(setHistory).catch(() => setHistory(null))
  }, [sym, days])

  useEffect(() => {
    if (tab === 'NEWS' && !news) newsApi.forSymbol(sym).then(setNews).catch(() => setNews(null))
  }, [tab, sym, news])

  const toggleWatchlist = async () => {
    setWatchMsg('')
    try {
      if (watched) await watchlistApi.remove(sym)
      else await watchlistApi.add(sym)
      setWatchlist(await watchlistApi.get())
    } catch (e) { setWatchMsg(errorText(e)) }
  }

  // Ticker existiert nicht / keine Daten
  if (q && !q.available && info && !info.available) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
        <div className="text-terminal-orange text-sm">Für „{sym}“ liefert Yahoo Finance keine Daten.</div>
        <div className="text-xs text-terminal-text-dim max-w-md text-center">{q.error}</div>
        <button onClick={() => navigate('/')}
          className="text-terminal-orange text-xs border border-terminal-orange px-3 py-1 hover:bg-terminal-orange hover:text-black">
          ← ZUR STARTSEITE
        </button>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-3 animate-fade-in">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-terminal-orange text-2xl font-bold tracking-wider">{sym}</h1>
            {q?.exchange && <span className="text-xs border border-terminal-border px-2 py-0.5 text-terminal-text-dim">{q.exchange}</span>}
            {info?.sector && <span className="text-xs text-terminal-cyan border border-terminal-cyan/30 px-2 py-0.5">{info.sector}</span>}
          </div>
          <div className="text-terminal-text-dim text-sm mt-0.5">{q?.name ?? info?.name ?? ''}</div>
        </div>
        <div className="flex items-end gap-3">
          <div className="flex flex-col items-end gap-1">
            <button onClick={toggleWatchlist}
              className={`text-xs px-3 py-1.5 border transition-colors ${watched
                ? 'border-terminal-orange bg-terminal-orange/10 text-terminal-orange'
                : 'border-terminal-border text-terminal-text-dim hover:border-terminal-orange hover:text-terminal-orange'}`}>
              {watched ? '★ AUF WATCHLIST' : '☆ ZUR WATCHLIST'}
            </button>
            {watchMsg && <span className="text-[10px] text-terminal-red">{watchMsg}</span>}
          </div>
          <div className="text-right">
            <PriceCell q={q} big />
            {q?.available && <div><DataStamp meta={q} marketTime={q.market_time} /></div>}
          </div>
        </div>
      </div>

      {q?.available && (q.day_low != null || q.prev_close != null) && (
        <div className="flex gap-4 text-xs text-terminal-text-dim flex-wrap">
          <span>Vortag: <span className="text-terminal-text">{price(q.prev_close)}</span></span>
          <span>Tagestief: <span className="text-terminal-text">{price(q.day_low)}</span></span>
          <span>Tageshoch: <span className="text-terminal-text">{price(q.day_high)}</span></span>
          <span>Volumen: <span className="text-terminal-text">{num(q.volume, 0)}</span></span>
        </div>
      )}

      <div className="flex gap-0 border-b border-terminal-border">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-1.5 text-xs border-b-2 transition-colors whitespace-nowrap ${
              tab === t.id ? 'border-terminal-orange text-terminal-orange font-semibold' : 'border-transparent text-terminal-text-dim hover:text-terminal-text'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'CHART' && (
        <div className="panel p-3 space-y-3">
          <div className="flex items-center gap-2 text-xs text-terminal-text-dim flex-wrap">
            <span>Zeitraum:</span>
            {[30, 90, 180, 365, 1825].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={`px-2 py-0.5 border transition-colors ${days === d ? 'border-terminal-orange text-terminal-orange' : 'border-terminal-border hover:border-terminal-text-dim'}`}>
                {d === 1825 ? '5J' : d === 365 ? '1J' : `${Math.round(d / 30)}M`}
              </button>
            ))}
            <span className="ml-4 text-terminal-blue">— SMA20</span>
            <span className="text-yellow-400">— SMA50</span>
            <span className="text-terminal-red">— SMA200</span>
            {history && <DataStamp meta={history} className="ml-auto" />}
          </div>
          {!history ? <div className="text-xs text-terminal-muted py-20 text-center">Lade Kursverlauf …</div>
            : !history.available ? <Unavailable text={history.error} />
            : <>
                <CandlestickChart candles={history.candles} indicators={indicators?.available ? indicators.indicators : []} />
                <div className="text-[10px] text-terminal-muted">Tageskurse in {history.currency ?? '–'} (Schlusskurse, nicht dividendenbereinigt).</div>
              </>}
        </div>
      )}

      {tab === 'DES' && (
        !info ? <div className="text-xs text-terminal-muted">Lade Profil …</div>
        : !info.available ? <Unavailable text={info.error} />
        : <div className="panel p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs text-terminal-cyan font-semibold">PROFIL</div>
              <DataStamp meta={info} />
            </div>
            <p className="text-sm text-terminal-text leading-relaxed">{info.description ?? 'Keine Beschreibung von Yahoo Finance geliefert.'}</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div><span className="text-terminal-text-dim">Branche: </span>{info.industry ?? '–'}</div>
              <div><span className="text-terminal-text-dim">Land: </span>{info.country ?? '–'}</div>
              <div><span className="text-terminal-text-dim">Börse: </span>{info.exchange ?? '–'}</div>
              <div><span className="text-terminal-text-dim">Währung: </span>{info.currency ?? '–'}</div>
            </div>
            {info.website && (
              <a href={info.website} target="_blank" rel="noopener noreferrer" className="inline-block text-xs text-terminal-orange hover:underline">
                {info.website} ↗
              </a>
            )}
          </div>
      )}

      {tab === 'KENNZ' && (!info ? <div className="text-xs text-terminal-muted">Lade Kennzahlen …</div> : <KeyMetrics info={info} />)}

      {tab === 'TECH' && (
        !indicators ? <div className="text-xs text-terminal-muted">Berechne Indikatoren …</div>
        : !indicators.available ? <Unavailable text={indicators.error} />
        : <div className="space-y-4">
            <div className="panel p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs text-terminal-cyan font-semibold">GLEITENDE DURCHSCHNITTE (SMA50 / SMA200)</div>
                <DataStamp meta={indicators} />
              </div>
              <div className={`text-lg font-bold mb-1 ${indicators.signal === 'BUY' ? 'text-terminal-green' : indicators.signal === 'SELL' ? 'text-terminal-red' : 'text-terminal-text-dim'}`}>
                {indicators.signal === 'BUY' ? 'AUFWÄRTSTREND' : indicators.signal === 'SELL' ? 'ABWÄRTSTREND' : 'NEUTRAL'}
              </div>
              <div className="text-xs text-terminal-text-dim">{indicators.signal_reason}</div>
              <div className="text-[11px] text-terminal-muted mt-2">Rein technische Berechnung aus dem Kursverlauf. Keine Anlageberatung.</div>
            </div>
            <div className="panel p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
              {indicators.indicators.filter(i => ['SMA20', 'SMA50', 'SMA200', 'RSI14'].includes(i.name)).map(ind => {
                const last = ind.values[ind.values.length - 1]
                const isRsi = ind.name === 'RSI14'
                return (
                  <div key={ind.name} className="border border-terminal-border p-3">
                    <div className="text-xs text-terminal-text-dim mb-1">{ind.name}</div>
                    <div className="text-base font-semibold">{last ? (isRsi ? num(last.value, 1) : price(last.value)) : '–'}</div>
                    {isRsi && last && <div className="text-xs text-terminal-muted mt-0.5">
                      {last.value > 70 ? 'überkauft (>70)' : last.value < 30 ? 'überverkauft (<30)' : 'neutral'}</div>}
                  </div>
                )
              })}
            </div>
          </div>
      )}

      {tab === 'SCORE' && <ScoreTab symbol={sym} />}

      {tab === 'LIEFER' && <SupplyChainTab symbol={sym} />}

      {tab === 'NEWS' && (
        !news ? <div className="text-xs text-terminal-muted">Lade Nachrichten …</div>
        : <div className="space-y-2">
            <DataStamp meta={news} />
            {news.error && <Unavailable text={news.error} />}
            {news.items.length === 0 && !news.error && <div className="text-xs text-terminal-text-dim">Keine aktuellen Nachrichten gefunden.</div>}
            {news.items.map(item => (
              <a key={item.id} href={item.url} target="_blank" rel="noopener noreferrer"
                className="block panel p-3 hover:border-terminal-orange transition-colors">
                <div className="text-sm text-terminal-text leading-snug">{item.headline} <span className="text-terminal-muted">↗</span></div>
                <div className="flex gap-3 mt-1 text-xs text-terminal-muted">
                  <span className="text-terminal-orange">{item.source}</span>
                  <span>{dateTime(item.published_at)}</span>
                </div>
              </a>
            ))}
          </div>
      )}
    </div>
  )
}
