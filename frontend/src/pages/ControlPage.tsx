import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  api, assetUrl, exportUrl, fmtD, statusText,
  type Drawing, type PresentationView, type Results, type Session, type SessionSummary,
} from '../api/client'
import DrawingModal from '../components/DrawingModal'
import './control.css'

const LAST = 'medeltomten.session'
const store = {
  get: () => { try { return localStorage.getItem(LAST) } catch { return null } },
  set: (v: string | null) => { try { if (v) localStorage.setItem(LAST, v); else localStorage.removeItem(LAST) } catch { /* private mode */ } },
}

const PHASE_SV: Record<string, string> = {
  standby: 'Standby', analyzing: 'Analyserar', composite: 'Composite build', search: 'Subject search',
  narrowing: 'Narrowing', match: 'Match found', result: 'Resultat',
}

export default function ControlPage() {
  const [sid, setSid] = useState<string | null>(() => new URLSearchParams(location.search).get('session') ?? store.get())
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    if (!sid) return
    try {
      setSession(await api.getSession(sid))
    } catch (e) {
      if ((e as { status?: number }).status === 404) { store.set(null); setSid(null); setSession(null) }
      else setError((e as Error).message)
    }
  }, [sid])

  useEffect(() => {
    document.title = 'MEDELTOMTEN – kontroll'
    if (sid) store.set(sid)
    refresh()
  }, [sid, refresh])

  const running = session?.analysis.status === 'queued' || session?.analysis.status === 'running'
  useEffect(() => {
    if (!sid) return
    const t = setInterval(refresh, running ? 600 : 2000)
    return () => clearInterval(t)
  }, [sid, running, refresh])

  if (!sid || !session) return <SessionPicker onOpen={setSid} error={error} />
  return <Workspace session={session} refresh={refresh} close={() => { store.set(null); setSid(null); setSession(null) }} />
}

function SessionPicker({ onOpen, error }: { onOpen: (id: string) => void; error: string }) {
  const [list, setList] = useState<SessionSummary[]>([])
  const [name, setName] = useState('')
  const [demo, setDemo] = useState(false)
  const [err, setErr] = useState(error)
  const load = () => api.listSessions().then(setList).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  return (
    <div className="control">
      <Header />
      <main className="picker">
        <section className="panel">
          <h2>Ny session</h2>
          <label>Namn <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Julfesten 2026" /></label>
          <label className="check">
            <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} />
            Demoläge – endast syntetiska testteckningar (blandas aldrig med riktiga bidrag)
          </label>
          <button className="primary" onClick={async () => {
            try { onOpen((await api.createSession(name, demo)).id) } catch (e) { setErr((e as Error).message) }
          }}>Skapa session</button>
          <p className="muted"><a href="/print" target="_blank">Skriv ut ritmall (A4) ↗</a></p>
        </section>
        <section className="panel">
          <h2>Återuppta</h2>
          {list.length === 0 && <p className="muted">Inga sparade sessioner.</p>}
          <ul className="sessions">
            {list.map((s) => (
              <li key={s.id}>
                <button onClick={() => onOpen(s.id)}>{s.name}</button>
                {s.demo && <span className="badge demo">DEMO</span>}
                <span className="muted">{s.drawings} bidrag · {new Date(s.created_at * 1000).toLocaleString('sv-SE')}</span>
                <button className="danger small" onClick={async () => {
                  if (!confirm(`Radera sessionen "${s.name}" med alla bilder permanent?`)) return
                  await api.deleteSession(s.id).catch((e) => setErr(e.message))
                  load()
                }}>Radera</button>
              </li>
            ))}
          </ul>
        </section>
        {err && <p className="error">{err}</p>}
      </main>
    </div>
  )
}

function Header({ session, close }: { session?: Session; close?: () => void }) {
  return (
    <header className="top">
      <h1>MEDELTOMTEN<span>kontrollpanel</span></h1>
      {session && (
        <div className="who">
          <b>{session.name}</b>
          {session.demo && <span className="badge demo">DEMO · SYNTETISKA TECKNINGAR</span>}
          <button className="small" onClick={close}>Byt session</button>
        </div>
      )}
    </header>
  )
}

function Workspace({ session, refresh, close }: { session: Session; refresh: () => void; close: () => void }) {
  const sid = session.id
  const [open, setOpen] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'needs_review' | 'excluded'>('all')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [results, setResults] = useState<Results | null>(null)
  const [pres, setPres] = useState<PresentationView | null>(null)
  const a = session.analysis

  useEffect(() => {
    if (a.status === 'completed') api.results(sid).then(setResults).catch(() => setResults(null))
    else setResults(null)
  }, [sid, a.status, a.finished_at, session.revision])

  useEffect(() => {
    const tick = () => api.presentation(sid).then(setPres).catch(() => {})
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [sid])

  const drawings = useMemo(() => Object.values(session.drawings), [session.drawings])
  const shown = drawings.filter((d) => filter === 'all' || d.status === filter)

  const run = async (f: () => Promise<unknown>, ok?: string) => {
    setErr('')
    try { await f(); if (ok) setMsg(ok); refresh() } catch (e) { setErr((e as Error).message) }
  }
  const cmd = (action: string) => run(async () => setPres(await api.command(sid, action)))
  const projector = `/show?session=${sid}`

  return (
    <div className="control">
      <Header session={session} close={close} />
      <main className="work">
        <aside>
          <section className="panel stats">
            <Stat n={session.counts.total} t="uppladdade" />
            <Stat n={session.counts.ok} t="godkända" />
            <Stat n={session.counts.needs_review} t="granska" warn={session.counts.needs_review > 0} />
            <Stat n={session.counts.excluded} t="uteslutna" />
          </section>

          <Uploader session={session} onDone={(m) => { setMsg(m); refresh() }} onError={setErr} />

          <section className="panel">
            <h2>Analys</h2>
            {session.counts.needs_review > 0 && (
              <p className="warn">{session.counts.needs_review} bidrag väntar på granskning. Godkänn, rätta eller uteslut dem innan analysen.</p>
            )}
            {session.analysis_stale && <p className="warn">Bidragen har ändrats efter senaste analysen – beräkna igen före showen.</p>}
            <div className="col">
              <button className="primary big" disabled={a.status === 'running' || a.status === 'queued'}
                onClick={() => run(() => api.analyze(sid, true), 'Analys startad – projektorn visar analysen.')}>
                Beräkna och starta show
              </button>
              <button disabled={a.status === 'running' || a.status === 'queued'}
                onClick={() => run(() => api.analyze(sid, false), 'Analys startad.')}>Beräkna endast</button>
            </div>
            <AnalysisStatus a={a} />
          </section>

          <section className="panel">
            <h2>Presentation</h2>
            <p>
              <a href={projector} target="medeltomten-show"
                onClick={(e) => { e.preventDefault(); window.open(projector, 'medeltomten-show', 'popup,width=1280,height=720') }}>
                Öppna projektorvy ↗
              </a>
              <span className="muted"> – dra fönstret till projektorn och tryck F (helskärm).</span>
            </p>
            <p className="phase">Fas: <b>{pres ? PHASE_SV[pres.phase] : '–'}</b>{pres?.paused && ' · PAUSAD'}
              {pres?.phase_duration ? ` · ${Math.min(pres.phase_elapsed, pres.phase_duration).toFixed(0)}/${pres.phase_duration} s` : ''}</p>
            <div className="grid-buttons">
              <button onClick={() => cmd('start')}>Starta</button>
              <button onClick={() => cmd('pause')} disabled={pres?.mode !== 'show' || pres.paused}>Paus</button>
              <button onClick={() => cmd('resume')} disabled={!pres?.paused}>Fortsätt</button>
              <button onClick={() => cmd('advance')} disabled={pres?.mode !== 'show' || pres.phase === 'result'}>Nästa fas</button>
              <button onClick={() => cmd('replay')}>Spela om</button>
              <button onClick={() => cmd('reset')}>Återställ</button>
            </div>
          </section>

          <section className="panel">
            <h2>Övrigt</h2>
            <p><a href="/print" target="_blank">Skriv ut ritmall (A4) ↗</a></p>
            <button className="danger" onClick={async () => {
              if (!confirm(`Radera sessionen "${session.name}"? Alla bilder och resultat tas bort permanent från datorn.`)) return
              await run(() => api.deleteSession(sid))
              close()
            }}>Radera session</button>
          </section>
          {msg && <p className="ok-msg" onClick={() => setMsg('')}>{msg}</p>}
          {err && <p className="error" onClick={() => setErr('')}>{err}</p>}
        </aside>

        <div className="content">
          {results && <ResultsPanel sid={sid} r={results} drawings={session.drawings} onOpen={setOpen} />}
          <section className="panel">
            <div className="row spread">
              <h2>Bidrag</h2>
              <div className="tabs">
                {(['all', 'needs_review', 'excluded'] as const).map((f) => (
                  <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
                    {f === 'all' ? 'Alla' : f === 'needs_review' ? 'Granska' : 'Uteslutna'}
                  </button>
                ))}
              </div>
            </div>
            {shown.length === 0 && <p className="muted">Inga bidrag här ännu.</p>}
            <div className="cards">
              {shown.map((d) => <Card key={d.id} sid={sid} d={d} onOpen={() => setOpen(d.id)} />)}
            </div>
          </section>
        </div>
      </main>
      {open && session.drawings[open] && (
        <DrawingModal sid={sid} drawing={session.drawings[open]} onClose={() => setOpen(null)} onChanged={refresh} />
      )}
    </div>
  )
}

function Stat({ n, t, warn }: { n: number; t: string; warn?: boolean }) {
  return <div className={`stat ${warn ? 'warn' : ''}`}><b>{n}</b><span>{t}</span></div>
}

function AnalysisStatus({ a }: { a: Session['analysis'] }) {
  if (a.status === 'none') return <p className="muted">Ingen analys körd.</p>
  const pct = a.total ? Math.round(((a.done ?? 0) / a.total) * 100) : 0
  return (
    <div className="analysis">
      <p>Status: <b>{{ queued: 'i kö', running: 'pågår', completed: 'klar', failed: 'misslyckades', none: '' }[a.status]}</b> · {a.step}</p>
      {(a.status === 'running' || a.status === 'queued') && <div className="bar"><div style={{ width: `${pct}%` }} /></div>}
      {a.error && <p className="error">{a.error}</p>}
    </div>
  )
}

function Card({ sid, d, onOpen }: { sid: string; d: Drawing; onOpen: () => void }) {
  return (
    <button className={`card ${d.status}`} onClick={onOpen}>
      <img src={assetUrl(sid, `${d.id}-thumb`)} alt="" loading="lazy" />
      <div className="meta">
        <b>{d.id.toUpperCase()}</b>
        {d.label && <span className="label">{d.label}</span>}
        <span className={`badge ${d.status}`}>{statusText(d.status)}</span>
      </div>
      {d.status === 'needs_review' && <p className="reason">{d.review_reasons[0]}</p>}
      {d.status === 'excluded' && <p className="reason">{d.exclude_reason}</p>}
    </button>
  )
}

function Uploader({ session, onDone, onError }: { session: Session; onDone: (m: string) => void; onError: (m: string) => void }) {
  const [progress, setProgress] = useState<[number, number] | null>(null)
  const [errors, setErrors] = useState<{ filename: string; error: string }[]>([])
  const [over, setOver] = useState(false)
  const [count, setCount] = useState(75)
  const [problems, setProblems] = useState(false)

  const upload = async (files: File[]) => {
    files = files.filter((f) => /\.(jpe?g|png|webp)$/i.test(f.name) || /^image\/(jpeg|png|webp)$/.test(f.type))
    if (!files.length) return
    setErrors([])
    const errs: typeof errors = []
    let added = 0
    // Small batches: steady progress, and one bad file never takes the rest down with it.
    for (let i = 0; i < files.length; i += 3) {
      setProgress([i, files.length])
      try {
        const r = await api.upload(session.id, files.slice(i, i + 3))
        added += r.added.length
        errs.push(...r.errors)
      } catch (e) {
        files.slice(i, i + 3).forEach((f) => errs.push({ filename: f.name, error: (e as Error).message }))
      }
    }
    setProgress(null)
    setErrors(errs)
    onDone(`${added} bild(er) importerade${errs.length ? `, ${errs.length} avvisade` : ''}.`)
  }

  if (session.demo) {
    return (
      <section className="panel">
        <h2>Syntetiska testteckningar</h2>
        <p className="muted">Genereras som "fotograferade" mallar och går genom exakt samma registrering och analys.</p>
        <div className="row">
          <input type="number" min={1} max={100} value={count} onChange={(e) => setCount(+e.target.value)} style={{ width: 80 }} />
          <button className="primary" disabled={!!progress} onClick={async () => {
            setProgress([0, count])
            try {
              let left = count
              while (left > 0) {
                const n = Math.min(left, 10)
                await api.demoDrawings(session.id, n, problems && left === count)
                left -= n
                setProgress([count - left, count])
              }
              onDone(`${count} syntetiska teckningar skapade.`)
            } catch (e) { onError((e as Error).message) } finally { setProgress(null) }
          }}>Generera</button>
        </div>
        <label className="check"><input type="checkbox" checked={problems} onChange={(e) => setProblems(e.target.checked)} />
          + två problemfall (tomt ark, saknade markörer)</label>
        {progress && <div className="bar"><div style={{ width: `${(progress[0] / progress[1]) * 100}%` }} /></div>}
      </section>
    )
  }
  return (
    <section className="panel">
      <h2>Importera foton</h2>
      <label className={`drop ${over ? 'over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); upload([...e.dataTransfer.files]) }}>
        <input type="file" multiple accept="image/jpeg,image/png,image/webp" hidden
          onChange={(e) => { upload([...(e.target.files ?? [])]); e.target.value = '' }} />
        Dra hit foton eller klicka för att välja<br /><small>JPG, PNG, WebP · max 20 MB/st · flera omgångar går bra</small>
      </label>
      {progress && (<><div className="bar"><div style={{ width: `${(progress[0] / progress[1]) * 100}%` }} /></div>
        <p className="muted">Bearbetar {progress[0]}/{progress[1]} …</p></>)}
      {errors.length > 0 && (
        <ul className="errors">{errors.map((e, i) => <li key={i}><b>{e.filename}</b>: {e.error}</li>)}</ul>
      )}
    </section>
  )
}

function ResultsPanel({ sid, r, drawings, onOpen }: {
  sid: string; r: Results; drawings: Record<string, Drawing>; onOpen: (id: string) => void
}) {
  const key = r.created_at
  const w = r.ranking[0]
  const dev = r.ranking[r.ranking.length - 1]
  const name = (x: { id: string; label: string }) => `${x.id.toUpperCase()}${x.label ? ` · ${x.label}` : ''}`
  return (
    <section className="panel results">
      <div className="row spread">
        <h2>Resultat {r.stale && <span className="badge needs_review">INAKTUELLT</span>} {r.demo && <span className="badge demo">DEMO</span>}</h2>
        <div className="row">
          <a className="button" href={exportUrl(sid, 'results.csv')}>CSV</a>
          <a className="button" href={exportUrl(sid, 'results.json')}>JSON</a>
          <a className="button" href={assetUrl(sid, 'average_raw', key)} download="average_raw.png">Medelbild (rå)</a>
          <a className="button" href={assetUrl(sid, 'average_display', key)} download="average_display.png">Medelbild (förstärkt)</a>
          <a className="button" href={exportUrl(sid, 'gallery.zip')}>Galleri (zip)</a>
        </div>
      </div>
      <div className="result-top">
        <figure><img src={assetUrl(sid, 'average_raw', key)} alt="" /><figcaption>average_raw (verkligt medel, N={r.n_included})</figcaption></figure>
        <figure><img src={assetUrl(sid, 'average_display', key)} alt="" /><figcaption>average_display (visningsförstärkt)</figcaption></figure>
        <figure><img src={assetUrl(sid, `${w.id}-preview`, key)} alt="" /><figcaption>#1 {name(w)}{w.tied && ' (delad)'}</figcaption></figure>
        <figure><img src={assetUrl(sid, `${dev.id}-preview`, key)} alt="" /><figcaption>Mest avvikande: {name(dev)}</figcaption></figure>
      </div>
      <details>
        <summary>Fullständig ranking ({r.ranking.length}) · {r.algorithm_version} · seed {r.seed}</summary>
        <table>
          <thead><tr><th>Plats</th><th>Bidrag</th><th>Etikett</th><th>D (rå)</th><th>σ-komponenter</th><th>Reg.</th></tr></thead>
          <tbody>
            {r.ranking.map((x) => (
              <tr key={x.id} onClick={() => drawings[x.id] && onOpen(x.id)}>
                <td>{x.position}{x.tied ? ` (=${x.rank})` : ''}</td><td>{x.id.toUpperCase()}</td><td>{x.label}</td>
                <td className="mono">{fmtD(x.distance)}</td>
                <td className="mono">{x.components?.map(fmtD).join(' / ')}</td><td>{x.registration}</td>
              </tr>
            ))}
            {r.excluded.map((x) => (
              <tr key={x.id} className="excl"><td>–</td><td>{x.id.toUpperCase()}</td><td>{x.label}</td><td colSpan={3}>Utesluten: {x.reason}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}
