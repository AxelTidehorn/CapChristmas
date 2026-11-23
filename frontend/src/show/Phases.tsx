/* Presentation only: every image and id shown here comes from the server's stored result.
   Nothing in this file ranks, scores or picks anything. */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { assetUrl, type PresentationView, type Who } from '../api/client'

const STEPS = ['analyzing', 'composite', 'search', 'narrowing', 'match', 'result'] as const
const STEP_LABEL: Record<string, string> = {
  analyzing: 'ANALYS', composite: 'COMPOSITE BUILD', search: 'SUBJECT SEARCH', narrowing: 'NARROWING',
  match: 'MATCH FOUND', result: 'RESULTAT',
}

function useNow() {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    let id = 0
    const loop = () => { setNow(performance.now()); id = requestAnimationFrame(loop) }
    id = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(id)
  }, [])
  return now
}

function useClock() {
  const [c, setC] = useState(() => new Date().toLocaleTimeString('sv-SE'))
  useEffect(() => {
    const id = setInterval(() => setC(new Date().toLocaleTimeString('sv-SE')), 1000)
    return () => clearInterval(id)
  }, [])
  return c
}

function useReducedMotion() {
  const q = '(prefers-reduced-motion: reduce)'
  const [r, setR] = useState(() => window.matchMedia?.(q).matches ?? false)
  useEffect(() => {
    const m = window.matchMedia?.(q)
    if (!m) return
    const f = () => setR(m.matches)
    m.addEventListener('change', f)
    return () => m.removeEventListener('change', f)
  }, [])
  return r
}

const clamp = (x: number, a: number, b: number) => Math.max(a, Math.min(b, x))
const tag = (w: Who) => w.id.toUpperCase()
const reference = (v: PresentationView) => v.reference_asset ?? 'average_display'
const ai = (v: PresentationView) => v.result_mode === 'ai'

function preload(urls: string[]) {
  urls.forEach((u) => { const i = new Image(); i.src = u })
}

export function PhaseView({ v, receivedAt }: { v: PresentationView; receivedAt: number }) {
  const now = useNow()
  const dur = v.phase_duration ?? Infinity
  const t = clamp(v.phase_elapsed + (v.paused ? 0 : (now - receivedAt) / 1000), 0, dur)
  const key = v.result_key ?? ''
  const img = (asset: string) => assetUrl(v.session_id, asset, key)

  // Warm the cache one phase ahead so image swaps never show empty frames.
  const order = v.order
  useEffect(() => { if (order) preload(order.map((w) => img(`${w.id}-preview`))) }, [order]) // eslint-disable-line

  switch (v.phase) {
    case 'standby': return <Standby />
    case 'analyzing': return <Shell v={v} t={0}><Analyzing v={v} /></Shell>
    case 'composite': return <Shell v={v} t={t}>{ai(v) ? <Reconstruction v={v} t={t} img={img} /> : <Composite v={v} t={t} img={img} />}</Shell>
    case 'search': return <Shell v={v} t={t}><Search v={v} t={t} img={img} /></Shell>
    case 'narrowing': return <Shell v={v} t={t}><Narrowing v={v} t={t} img={img} /></Shell>
    case 'match': return <Shell v={v} t={t}><Match v={v} t={t} img={img} /></Shell>
    case 'result': return <Shell v={v} t={t}><Result v={v} img={img} /></Shell>
  }
}

function Standby() {
  return (
    <div className="standby">
      <div className="standby-inner">
        <p className="kicker">MEDELTOMTEN · UPPDRAG</p>
        <h1>RITA EN<br />GENOMSNITTS&shy;TOMTE.</h1>
        <hr />
        <p className="sub">Du har fem minuter på dig. Din teckning kommer att analyseras.</p>
        <p className="sub">Bedömningskriterierna offentliggörs efter avslutad uppgift.</p>
      </div>
    </div>
  )
}

function Shell({ v, t, children }: { v: PresentationView; t: number; children: ReactNode }) {
  const clock = useClock()
  const cur = STEPS.indexOf(v.phase as (typeof STEPS)[number])
  return (
    <div className={`csi phase-${v.phase}`}>
      <div className="csi-grid" />
      <header className="csi-head">
        <span>MEDELTOMTEN<i>//</i>FORENSISK KOMPOSITENHET</span>
        <span className="csi-title">{STEP_LABEL[v.phase]}{v.paused && <em> · PAUS</em>}</span>
        <span>ÄRENDE {v.session_id.slice(0, 6).toUpperCase()}<i>·</i>{clock}</span>
      </header>
      <main className="csi-body">{children}</main>
      <footer className="csi-foot">
        {STEPS.map((s, i) => (
          <span key={s} className={i < cur ? 'done' : i === cur ? 'cur' : ''}>{String(i).padStart(2, '0')} {STEP_LABEL[s]}</span>
        ))}
        <span className="t">T+{t.toFixed(1)}</span>
      </footer>
    </div>
  )
}

function Analyzing({ v }: { v: PresentationView }) {
  const a = v.analysis
  const failed = a?.status === 'failed'
  const pct = a?.total ? (100 * (a.done ?? 0)) / a.total : 0
  return (
    <div className="analyzing">
      <h1 className={failed ? 'bad' : ''}>{failed ? 'ANALYS AVBRUTEN' : 'ANALYZING'}<span className="cursor">_</span></h1>
      <p className="big-step">{a?.step ?? 'Initierar'}</p>
      <div className="meter"><div style={{ width: `${pct}%` }} /></div>
      <p className="meter-label">{a?.done ?? 0} / {a?.total ?? 0} BERÄKNINGSSTEG · {v.n_uploaded ?? 0} INKOMNA BIDRAG</p>
      <ul className="log">{(a?.log ?? []).map((l, i) => <li key={i}>&gt; {l}</li>)}</ul>
      {failed && <p className="bad">{a?.error}</p>}
    </div>
  )
}

function Panel({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`csi-panel ${className}`}>
      <h3>{title}</h3>
      <div className="csi-panel-body">{children}</div>
    </section>
  )
}

function Brackets() {
  return <><i className="br tl" /><i className="br tr" /><i className="br bl" /><i className="br br2" /></>
}

function Composite({ v, t, img }: { v: PresentationView; t: number; img: (a: string) => string }) {
  const stages = v.stages ?? []
  const D = v.phase_duration ?? 7
  const build = Math.max(1, D - 2.6)
  const f = clamp((t / build) * stages.length, 0, stages.length)
  const cur = stages[Math.min(stages.length - 1, Math.floor(f))]
  const final = t >= build
  const showDisplay = t >= build + 1.3
  return (
    <div className="composite">
      <Panel title={final ? (showDisplay ? 'MEDELBILD · VISNINGSFÖRSTÄRKT' : 'MEDELBILD · RÅ M(x,y)') : 'ACKUMULERAT MEDELVÄRDE · VISNINGSFÖRSTÄRKT'} className="main-img">
        <div className="frame">
          {stages.map((s, i) => (
            <img key={s.asset} src={img(s.asset)} alt="" style={{ opacity: final ? 0 : clamp(f - i, 0, 1) }} />
          ))}
          <img src={img('average_raw')} alt="" style={{ opacity: final && !showDisplay ? 1 : 0 }} />
          <img src={img(reference(v))} alt="" style={{ opacity: showDisplay ? 1 : 0 }} />
          <Brackets />
        </div>
      </Panel>
      <div className="side">
        <Panel title="INDATA">
          <p className="huge">{final ? v.n : cur?.count ?? 0}<small> / {v.n}</small></p>
          <p className="dim">REGISTRERADE TECKNINGAR</p>
        </Panel>
        <Panel title="SENAST TILLAGD" className="added">
          {cur && !final && (
            <>
              <img src={img(`${cur.added.id}-preview`)} alt="" />
              <p>+ {tag(cur.added)}{cur.added.label && ` · ${cur.added.label}`}</p>
            </>
          )}
          {final && <p className="ok">ALLA {v.n} BIDRAG MEDELVÄRDESBILDADE</p>}
        </Panel>
        <Panel title="METOD">
          <p className="formula">M(x,y) = (1/N) · Σ I<sub>i</sub>(x,y)</p>
        </Panel>
      </div>
    </div>
  )
}

function Reconstruction({ v, t, img }: { v: PresentationView; t: number; img: (a: string) => string }) {
  const reduced = useReducedMotion()
  const fragments = v.fragments ?? []
  const progress = clamp(t / Math.max(1, (v.phase_duration ?? 7) - 2), 0, 1)
  const final = reduced || progress >= 1
  return <div className="composite reconstruction">
    <Panel title={final ? 'GRUPPENS FANTOMBILD · GODKÄND AI-REKONSTRUKTION' : 'VISUELL REKONSTRUKTION · DELTAGARNAS PENNSTRECK'} className="main-img">
      <div className="frame">
        {!reduced && fragments.map((w, i) => {
          const enter = i / Math.max(1, fragments.length) * .65
          const alpha = clamp((progress - enter) * 6, 0, 1) * (1 - clamp((progress - .72) / .28, 0, 1))
          return <img key={w.id} src={img(`${w.id}-preview`)} alt="" style={{ opacity: alpha * .65,
            mixBlendMode: 'multiply', transform: `translate(${(1 - progress) * ((i % 3) - 1) * 10}%, ${(1 - progress) * ((i % 2) ? 8 : -8)}%)` }} />
        })}
        <img src={img(reference(v))} alt="Gruppens sparade AI-genererade genomsnittstomte" style={{ opacity: reduced ? 1 : clamp((progress - .55) / .45, 0, 1) }} />
        <Brackets />
      </div>
    </Panel>
    <div className="side">
      <Panel title="UNDERLAG"><p className="huge">{v.n}</p><p>VERKLIGA TECKNINGAR</p></Panel>
      <Panel title="UR GRUPPENS ARKIV"><div className="fragment-grid">{fragments.map((w) => <img key={w.id} src={img(`${w.id}-preview`)} alt={tag(w)} />)}</div></Panel>
      <Panel title="FANTOMBILD"><p className="formula">MÖSSA · ANSIKTE · SKÄGG</p><p className="dim">Gruppens vanligaste drag samlade i en figur.</p><p className="montage-note">Visuellt montage · analysen är förberedd</p></Panel>
    </div>
  </div>
}

function Search({ v, t, img }: { v: PresentationView; t: number; img: (a: string) => string }) {
  const reduced = useReducedMotion()
  const c = v.candidates ?? []
  const D = v.phase_duration ?? 16
  const p = clamp((t / D) * c.length, 0, c.length - 0.001)
  const idx = Math.floor(p)
  const cand = c[idx]
  const frac = p - idx
  const ITEM = 7.2 // em
  return (
    <div className="search">
      <div className="search-top">
        <Panel title={ai(v) ? 'REFERENS · GRUPPENS FANTOMBILD' : 'REFERENS · LEGACY MEDELBILD'} className="ref">
          <div className="frame"><img src={img(reference(v))} alt="" /><Brackets /></div>
        </Panel>
        <div className="vs">
          <p>JÄMFÖR</p>
          <div className="vs-bars">{[0, 1, 2].map((i) => <span key={i} style={{ width: `${30 + 70 * Math.abs(Math.sin(p * 2.3 + i))}%` }} />)}</div>
          <p className="dim">{ai(v) ? 'FORM · PROPORTION · DRAG' : 'σ 4 · 16 · 40 PX'}</p>
        </div>
        <Panel title={`KANDIDAT ${cand ? tag(cand) : ''}`} className="cand">
          <div className="frame">
            {cand && <img src={img(`${cand.id}-preview`)} alt="" />}
            {!reduced && <i className="scanline" style={{ top: `${frac * 100}%` }} />}
            <Brackets />
          </div>
        </Panel>
        <div className="side">
          <Panel title="SKANNADE">
            <p className="huge">{idx + 1}<small> / {c.length}</small></p>
          </Panel>
          <Panel title="SUBJEKT">
            <p className="subject">{cand ? tag(cand) : '—'}</p>
            <p className="dim">{cand?.label || 'ingen etikett'}</p>
          </Panel>
          <Panel title="STATUS"><p className="ok">SÖKER I ARKIVET …</p></Panel>
        </div>
      </div>
      <div className="strip">
        <div className="strip-inner" style={{ transform: `translateX(calc(50% - ${(reduced ? idx + 0.5 : p) * ITEM}em))` }}>
          {c.map((w, i) => (
            <div key={w.id} className={`strip-item ${i === idx ? 'on' : i < idx ? 'seen' : ''}`}>
              <img src={img(`${w.id}-preview`)} alt="" loading="eager" />
              <span>{tag(w)}</span>
            </div>
          ))}
        </div>
        <i className="strip-reticle" />
      </div>
    </div>
  )
}

function Narrowing({ v, t, img }: { v: PresentationView; t: number; img: (a: string) => string }) {
  const s = v.shortlist ?? []
  const reduced = useReducedMotion()
  const hop = Math.floor(t * (reduced ? 1 : 3)) % Math.max(1, s.length)
  return (
    <div className="narrowing">
      <p className="narrow-title">{v.n} BIDRAG ANALYSERADE · {s.length} KANDIDATER KVARSTÅR</p>
      <div className="short">
        {s.map((w, i) => (
          <div key={w.id} className={`short-item ${i === hop ? 'on' : ''}`}>
            <div className="frame"><img src={img(`${w.id}-preview`)} alt="" /><Brackets /></div>
            <p>{tag(w)}</p>
          </div>
        ))}
      </div>
      <p className="dim center">KORSREFERERAR MOT REFERENS · SLUTLIG LÅSNING FÖRBEREDS</p>
    </div>
  )
}

function Match({ v, t, img }: { v: PresentationView; t: number; img: (a: string) => string }) {
  const reduced = useReducedMotion()
  const w = v.winner
  if (!w) return null
  const lock = 3.2
  if (t < lock && !reduced) {
    const k = t / lock
    return (
      <div className="locking">
        <div className="frame" style={{ ['--k' as string]: k }}>
          <img src={img(`${w.id}-preview`)} alt="" style={{ filter: `blur(${(1 - k) * 1.2}em)`, opacity: 0.3 + 0.7 * k }} />
          <i className="lock-ring" style={{ transform: `translate(-50%,-50%) scale(${2.4 - 1.4 * k})` }} />
          <Brackets />
        </div>
        <p className="lock-text">LÅSER MÅL …</p>
      </div>
    )
  }
  return (
    <div className="match">
      <h1 className="match-found">MATCH FOUND</h1>
      <div className="match-grid">
        <figure>
          <div className="frame"><img src={img(reference(v))} alt="" /><Brackets /></div>
          <figcaption>{ai(v) ? 'GRUPPENS GENOMSNITTSTOMTE' : 'LEGACY MEDELBILD'} · N={v.n}</figcaption>
        </figure>
        <div className="match-eq">≈</div>
        <figure className="winner">
          <div className="frame"><img src={img(`${w.id}-preview`)} alt="" /><Brackets /></div>
          <figcaption>BIDRAG {tag(w)}</figcaption>
        </figure>
      </div>
      <p className="verdict">{ai(v) ? 'MEST LIK GENOMSNITTSTOMTEN' : 'MEST GENOMSNITTLIG'}</p>
      {ai(v) && <p className="match-reason">{v.explanation}</p>}
      <p className="who">{w.label || `Bidrag nr ${w.number}`}{v.winner_tied && ' · delad förstaplats, avgjord på bidrags-ID'}</p>
    </div>
  )
}

function Result({ v, img }: { v: PresentationView; img: (a: string) => string }) {
  const top = v.top ?? []
  const dev = v.most_deviant
  const gallery = v.gallery ?? []
  const m = v.method
  const name = (w: Who) => `${tag(w)}${w.label ? ` · ${w.label}` : ''}`
  const cols = useMemo(() => Math.max(20, Math.ceil(gallery.length / 2)), [gallery.length])
  return (
    <div className="result">
      <div className="result-main">
        <figure>
          <div className="frame"><img src={img(reference(v))} alt="" /></div>
          <figcaption>Medeltomten · N={v.n}</figcaption>
        </figure>
        <figure className="winner">
          <div className="frame"><img src={img(`${v.winner?.id ?? top[0]?.id}-preview`)} alt="" /></div>
          <figcaption>VALD MATCH · {v.winner && name(v.winner)}</figcaption>
        </figure>
      </div>
      <Panel title={ai(v) ? 'TOPPKANDIDATER · VISUELL LIKHET' : 'TOPP 5 · MEST GENOMSNITTLIGA'} className="top5">
        <ol>
          {top.map((w) => (
            <li key={w.id}>
              <img src={img(`${w.id}-preview`)} alt="" />
              <span className="pos">{ai(v) ? w.id === v.winner?.id ? 'VALD' : '·' : `#${w.position}`}</span>
              <span>{name(w)}{!ai(v) && w.tied && ' (delad)'}</span>
            </li>
          ))}
        </ol>
      </Panel>
      <div className="result-side">
        {dev && (
          <Panel title="MEST AVVIKANDE" className="dev">
            <img src={img(`${dev.id}-preview`)} alt="" />
            <p>#{dev.position} av {v.n} · {name(dev)}</p>
          </Panel>
        )}
        <Panel title="METOD" className="method">
          {ai(v) ? <><p>{m?.description}</p><p>{v.explanation}</p></> : <><p>Varje foto rätas upp via markörerna och blir en bläckkarta 0–1 på {m?.canvas.join('×')} px. Medelbilden är
            det verkliga pixelmedelvärdet av alla {v.n} godkända teckningar.</p>
          <p>Avstånd D = {m?.weights?.map((w, i) => `${w.toFixed(2)}·MSE(σ${m.sigmas_px?.[i]})`).join(' + ')} mellan
            suddade versioner av teckning och medelbild. Lägst D vinner. {v.excluded_count ? `${v.excluded_count} uteslutna. ` : ''}
            {m?.algorithm_version}</p></>}
        </Panel>
      </div>
      <div className="gallery" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {gallery.map((w) => (
          <div key={w.id} className={w.id === v.winner?.id ? 'g1' : ''}>
            <img src={img(`${w.id}-preview`)} alt="" loading="lazy" />
            <span>{ai(v) ? w.id.toUpperCase() : w.position}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
