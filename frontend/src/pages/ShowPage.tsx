import { useEffect, useRef, useState } from 'react'
import { api, type PresentationView } from '../api/client'
import { PhaseView } from '../show/Phases'
import '../show/show.css'

/** Projector view. Reads only the public, phase-gated /presentation payload. */
export default function ShowPage() {
  const [sid, setSid] = useState<string | null>(() => new URLSearchParams(location.search).get('session'))
  const [view, setView] = useState<PresentationView | null>(null)
  const [received, setReceived] = useState(0)
  const [offline, setOffline] = useState(false)
  const [hint, setHint] = useState(true)
  const receivedRef = useRef(0)
  const viewRef = useRef<PresentationView | null>(null)

  useEffect(() => {
    document.title = 'MEDELTOMTEN'
    if (!sid) api.listSessions().then((l) => l[0] && setSid(l[0].id)).catch(() => setOffline(true))
    const t = setTimeout(() => setHint(false), 4000)
    const key = (e: KeyboardEvent) => { if (e.key === 'f' || e.key === 'F') toggleFullscreen() }
    window.addEventListener('keydown', key)
    return () => { clearTimeout(t); window.removeEventListener('keydown', key) }
  }, [sid])

  useEffect(() => {
    if (!sid) return
    let alive = true
    const poll = async () => {
      try {
        const v = await api.presentation(sid)
        if (!alive) return
        // Keep the local clock smooth: only resync on phase/pause change or noticeable drift.
        const old = viewRef.current
        const now = performance.now()
        const same = old && old.phase === v.phase && old.paused === v.paused && !v.paused && old.result_key === v.result_key
        if (same && Math.abs(old.phase_elapsed + (now - receivedRef.current) / 1000 - v.phase_elapsed) < 0.35) {
          v.phase_elapsed = old.phase_elapsed
        } else {
          receivedRef.current = now
        }
        viewRef.current = v
        setView(v)
        setReceived(receivedRef.current)
        setOffline(false)
      } catch {
        if (alive) setOffline(true)
      }
    }
    poll()
    const t = setInterval(poll, 500)
    return () => { alive = false; clearInterval(t) }
  }, [sid])

  return (
    <div className="show-root" onDoubleClick={toggleFullscreen}>
      <div className="stage">
        {view ? <PhaseView v={view} receivedAt={received} /> : <Blank text={sid ? '' : 'Ingen session vald'} />}
        {view?.demo && <div className="demo-tag">DEMO · SYNTETISKA TESTTECKNINGAR</div>}
        {offline && <div className="offline-dot" title="Ingen kontakt med servern" />}
        {hint && <div className="fs-hint">F / dubbelklick = helskärm</div>}
      </div>
    </div>
  )
}

function Blank({ text }: { text: string }) {
  return <div className="standby"><div className="standby-inner"><p className="kicker">{text}</p></div></div>
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
  else document.documentElement.requestFullscreen().catch(() => {})
}
