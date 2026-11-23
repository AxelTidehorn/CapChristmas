import { useEffect, useState } from 'react'
import { api, assetUrl, exportUrl, type AIConfig, type Session } from '../api/client'

const composition: Record<string, string> = { head_only: 'Huvud', bust: 'Huvud / överkropp', full_body: 'Helkropp', other: 'Annat', uncertain: 'Osäkert' }
const features: Record<string, string> = { hat: 'Mössa', beard: 'Skägg', nose: 'Näsa', eyes: 'Ögon', torso: 'Kropp', arms: 'Armar', legs: 'Ben', accessories: 'Tillbehör' }

export default function AIWorkflow({ session: s, refresh }: { session: Session; refresh: () => void }) {
  const a = s.ai
  const [config, setConfig] = useState<AIConfig | null>(null)
  const [note, setNote] = useState('')
  const [variation, setVariation] = useState('')
  const [winnerNote, setWinnerNote] = useState('')
  const [candidate, setCandidate] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const busy = sending || a.job.status === 'running' || a.job.status === 'queued' || s.analysis.status === 'running' || s.analysis.status === 'queued'
  const consensus = a.consensus
  const reference = a.versions.find((v) => v.id === a.approved_reference)
  const match = a.match && a.match.reference_id === reference?.id ? a.match : undefined
  const selected = match?.ranking.find((r) => r.id === (candidate || match.approval?.winner)) ?? match?.ranking[0]

  useEffect(() => {
    api.aiConfig(s.counts.ok).then(setConfig).catch((e) => setError(e.message))
  }, [s.counts.ok])

  async function run(action: string, body = {}) {
    setError(''); setMessage(''); setSending(true)
    try { await api.aiAction(s.id, action, body); refresh() }
    catch (e) { setError((e as Error).message) }
    finally { setSending(false) }
  }

  return <section className="panel ai-workflow">
    <h2>V2 · Från gruppens teckningar till fantombild</h2>
    <p className="workflow-path">Importera → Granska → Analysera gruppen → Konsensus → Generera → Godkänn bild → Matcha → Godkänn vinnare → Starta show</p>
    <p>{config?.notice}</p>
    <p className="muted">{config?.estimate} Cirka {config?.estimated_calls ?? '…'} anrop för en hel förberedelse utan cachade steg.</p>
    {config?.config && <p className="muted">Analys: {config.config.vision_model} · Bild: {config.config.image_model} · Match: {config.config.match_model}</p>}
    {!config?.configured && <p className="warn">{config?.error || 'Läser serverkonfiguration …'} Tidigare färdig show kan fortfarande spelas offline.</p>}
    <div className="row">
      <button disabled={busy || !config?.configured} onClick={async () => {
        setSending(true); setError('')
        try { await api.aiCheck(); setMessage('Valda modeller är åtkomliga. Inga bilder genererades; saldo och bildkvalitet återstår att testa.') }
        catch (e) { setError((e as Error).message) } finally { setSending(false) }
      }}>Kontrollera modellåtkomst</button>
      <button className="primary" disabled={busy || !config?.configured || s.counts.needs_review > 0 || s.counts.ok < 2}
        onClick={() => run('consensus')}>1. Analysera gruppen / återuppta</button>
    </div>
    {a.stale && <p className="warn">Bilduppsättningen har ändrats. Konsensus, syntes och matchning behöver göras om. Tidigare AI-bilder ligger kvar.</p>}
    {a.job.status !== 'none' && <div role="status" aria-live="polite" className="ai-status">
      <b>{a.job.step}</b> · {a.job.done ?? 0}/{a.job.total ?? 0} färdiga steg · {a.job.status}
      <progress value={a.job.done ?? 0} max={a.job.total || 1} />
      {a.job.error && <p className="error">{a.job.error}</p>}
      {busy && <button onClick={() => run('cancel')}>Avbryt efter pågående anrop</button>}
      {a.job.status === 'failed' && <p className="muted">Starta samma steg igen. Färdiga observationer och jämförelser återanvänds när indata och konfiguration är oförändrade.</p>}
    </div>}
    {consensus && <div className="ai-step">
      <h3>2. Granska konsensus</h3>
      <p>{consensus.visual_summary}</p>
      <p className="muted">{consensus.uncertainty}</p>
      <div className="consensus-counts">{Object.entries(consensus.composition).map(([k, n]) => <span key={k}><b>{n}</b> {composition[k] || k}</span>)}</div>
      <table><thead><tr><th>Drag</th><th>Observerat</th><th>Osäkert</th><th>Utbredning</th></tr></thead><tbody>
        {consensus.features.map((f) => <tr key={f.key}><td>{features[f.key]}</td><td>{f.present_count}/{consensus.included_count}</td><td>{f.uncertain_count}</td><td>{{common: 'Vanligt', occasional: 'Ibland', rare: 'Sällsynt', uncertain: 'Osäkert'}[f.level]}</td></tr>)}
      </tbody></table>
      <details><summary>Granskningsunderlag per bidrag ({consensus.observations.length})</summary>
        {consensus.observations.map((o) => <p key={o.id}><a href={assetUrl(s.id, `${o.id}-preview`)} target="_blank">{o.id}</a> · {composition[o.composition]} · {o.description}</p>)}
      </details>
      <label>Korrigera grova visuella missförstånd (valfritt, ändrar inte observerade antal)
        <textarea maxLength={800} value={note} onChange={(e) => setNote(e.target.value)} placeholder={consensus.approval?.correction || 'Exempel: majoritetens mössor hänger åt vänster.'} />
      </label>
      {consensus.approval && <p className="ok-msg">Konsensus godkänd. {consensus.approval.correction}</p>}
      <button disabled={busy || a.stale} onClick={() => run('approve-consensus', { note })}>Godkänn konsensus{consensus.approval ? ' på nytt (ny bild krävs)' : ''}</button>
    </div>}
    {consensus?.approval && <div className="ai-step">
      <h3>3. Generera och godkänn en tomte</h3>
      <p className="muted">{config?.generation_estimate} Varje klick beställer en ny version. Befintlig godkänd referens ändras först när du godkänner en annan bild.</p>
      <label>Kort bildönskemål (valfritt)<textarea value={variation} maxLength={800} onChange={(e) => setVariation(e.target.value)} placeholder="Exempel: lite enklare pennstreck." /></label>
      <button className="primary" disabled={busy || a.stale || !config?.configured} onClick={() => run('generate', { note: variation })}>
        {a.versions.length ? 'Generera igen (ny API-kostnad)' : 'Generera tomte (API-kostnad)'}</button>
      <div className="ai-versions">{a.versions.map((v, i) => <figure key={v.id}>
        <img src={assetUrl(s.id, v.asset)} alt={`Genererad genomsnittstomte, version ${i + 1}`} />
        <figcaption>Version {i + 1} · {new Date(v.created_at * 1000).toLocaleTimeString('sv-SE')} {reference?.id === v.id && '· GODKÄND'}</figcaption>
        <button disabled={busy || v.fingerprint !== a.fingerprint} onClick={() => { setCandidate(''); run('approve-reference', { version: v.id }) }}>Godkänn version {i + 1}</button>
      </figure>)}</div>
    </div>}
    {reference && <div className="ai-step">
      <h3>4. Matcha alla original mot godkänd version</h3>
      <p className="muted">Två bedömningar per bidrag med samma skala. Index mäter likhet, inte säkerhet. V1-pixelmedlet används enbart som separat diagnostik.</p>
      <button className="primary" disabled={busy || a.stale || !config?.configured} onClick={() => run('match')}>Matcha / återuppta ({s.counts.ok} bidrag)</button>
    </div>}
    {match && <div className="ai-step">
      <h3>5. Förhandsgranska match och godkänn vinnare</h3>
      {match.review_required && <p className="warn">Nära poäng eller osäker modellbedömning: granska kandidaterna visuellt innan du väljer.</p>}
      <div className="ai-pair">
        <figure><img src={assetUrl(s.id, reference!.asset)} alt="Godkänd AI-referens" /><figcaption>Godkänd genomsnittstomte</figcaption></figure>
        {selected && <figure><img src={assetUrl(s.id, `${selected.id}-preview`)} alt="Kandidatens verkliga teckning" /><figcaption>{selected.id} · {selected.label} · modellplacering #{selected.position}</figcaption></figure>}
      </div>
      {selected && <p>{selected.explanation} {!selected.reliable && <span className="warn">Modellbedömningarna är osäkra eller skiljer sig åt.</span>}</p>}
      <label>Välj bland topp 5<select value={selected?.id || ''} onChange={(e) => setCandidate(e.target.value)}>
        {match.ranking.slice(0, 5).map((r) => <option key={r.id} value={r.id}>#{r.position} {r.id} {r.label} · index {r.score.toFixed(3)}</option>)}
      </select></label>
      <label>Notering (krävs för annan än modellens förstaval)<input maxLength={800} value={winnerNote} onChange={(e) => setWinnerNote(e.target.value)} /></label>
      <button className="primary" disabled={busy || a.stale || !selected} onClick={() => run('approve-winner', { winner: selected?.id, note: winnerNote })}>Godkänn vinnare och lokalt showpaket</button>
      {match.approval && <p className="ok-msg">Godkänd: {match.approval.winner}. {match.approval.override && `Arrangörsval: ${match.approval.note}`}</p>}
      <details><summary>Alla {match.ranking.length} jämförelser · index, inte sannolikhet</summary><table><thead><tr><th>Plats</th><th>Bidrag</th><th>Index</th><th>Förklaring</th></tr></thead><tbody>
        {match.ranking.map((r) => <tr key={r.id}><td>{r.position}</td><td>{r.id}</td><td>{r.score.toFixed(3)}</td><td>{r.explanation}</td></tr>)}
      </tbody></table></details>
    </div>}
    {a.ready && <div className="ai-step">
      <h3>Klar för offline-show</h3>
      {s.result_mode !== 'ai' && <button className="primary" disabled={busy} onClick={() => run('activate')}>Använd sparad AI-show</button>}
      <p>Referens, kandidatbilder, vald vinnare och showordning är sparade lokalt. Starta showen i presentationspanelen.</p>
      <div className="row">{s.result_mode === 'ai' && ['results.json', 'results.csv', 'consensus.json', 'provenance.json', 'gallery.zip'].map((name) => <a className="button" key={name} href={exportUrl(s.id, name)}>{name}</a>)}
        {reference && <a className="button" href={assetUrl(s.id, reference.asset)} download="reference.png">AI-referens (PNG)</a>}
      </div>
    </div>}
    {message && <p role="status" className="ok-msg">{message}</p>}
    {error && <p role="alert" className="error">{error}</p>}
  </section>
}
