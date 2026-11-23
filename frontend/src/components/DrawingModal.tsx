import { useRef, useState } from 'react'
import { api, assetUrl, statusText, type Drawing } from '../api/client'

const METHOD: Record<string, string> = {
  aruco: 'ArUco, 4 markörer',
  aruco3: 'ArUco, 3 markörer',
  frame: 'ramdetektion (osäker)',
  manual: 'manuella hörn',
  none: 'ingen registrering',
}

function defaultCorners([w, h]: [number, number]): number[][] {
  const mx = w * 0.15
  const my = h * 0.15
  return [[mx, my], [w - mx, my], [w - mx, h - my], [mx, h - my]]
}

/** Drag four points on the working image: the corners of the printed frame (TL, TR, BR, BL). */
function CornerEditor({ src, size, initial, onSave, onCancel }: {
  src: string
  size: [number, number]
  initial: number[][]
  onSave: (c: number[][]) => void
  onCancel: () => void
}) {
  const [pts, setPts] = useState(initial.map((p) => [...p]))
  const [drag, setDrag] = useState<number | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const [w, h] = size
  const r = Math.max(w, h) / 90
  const move = (e: React.PointerEvent) => {
    if (drag === null || !svg.current) return
    const m = svg.current.getScreenCTM()
    if (!m) return
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse())
    setPts((old) => old.map((q, i) => (i === drag ? [Math.max(0, Math.min(w, p.x)), Math.max(0, Math.min(h, p.y))] : q)))
  }
  const names = ['Övre vänster', 'Övre höger', 'Nedre höger', 'Nedre vänster']
  return (
    <div className="corner-editor">
      <p className="hint">
        Dra de fyra punkterna till <b>ritramens hörn</b> (den tunna ramen runt ritytan), i ordningen övre vänster →
        övre höger → nedre höger → nedre vänster sett från teckningens upprätta läge. Saknas ram: använd ritytans hörn.
      </p>
      <svg ref={svg} viewBox={`0 0 ${w} ${h}`} onPointerMove={move} onPointerUp={() => setDrag(null)}
        onPointerLeave={() => setDrag(null)} style={{ touchAction: 'none' }}>
        <image href={src} width={w} height={h} />
        <polygon points={pts.map((p) => p.join(',')).join(' ')} fill="rgba(0,200,180,0.12)" stroke="#00d0b0"
          strokeWidth={r / 3} />
        {pts.map((p, i) => (
          <g key={i} onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); setDrag(i) }}
            style={{ cursor: 'grab' }}>
            <circle cx={p[0]} cy={p[1]} r={r * 1.6} fill="rgba(0,0,0,0.001)" stroke="#ff3b6b" strokeWidth={r / 3} />
            <circle cx={p[0]} cy={p[1]} r={r / 3} fill="#ff3b6b" />
            <text x={p[0] + r * 2} y={p[1] - r * 2} fill="#ff3b6b" fontSize={r * 2.2} fontWeight={700}>
              {i + 1} {names[i]}
            </text>
          </g>
        ))}
      </svg>
      <div className="row">
        <button className="primary" onClick={() => onSave(pts)}>Spara hörn och normalisera om</button>
        <button onClick={onCancel}>Avbryt</button>
      </div>
    </div>
  )
}

export default function DrawingModal({ sid, drawing, onClose, onChanged }: {
  sid: string
  drawing: Drawing
  onClose: () => void
  onChanged: () => void
}) {
  const d = drawing
  const [editing, setEditing] = useState(false)
  const [label, setLabel] = useState(d.label)
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [v, setV] = useState(0)
  const act = async (patch: Record<string, unknown>) => {
    setBusy(true)
    setErr('')
    try {
      await api.patchDrawing(sid, d.id, patch)
      setV((x) => x + 1)
      onChanged()
      return true
    } catch (e) {
      setErr((e as Error).message)
      return false
    } finally {
      setBusy(false)
    }
  }
  const key = `${d.registration.method}-${(d.registration.corners ?? []).flat().join('-')}-${v}`
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>{d.id.toUpperCase()} <span className={`badge ${d.status}`}>{statusText(d.status)}</span></h2>
          <button onClick={onClose} aria-label="Stäng">✕</button>
        </header>
        {editing ? (
          <CornerEditor src={assetUrl(sid, `${d.id}-work`)} size={d.work_size}
            initial={d.registration.corners ?? defaultCorners(d.work_size)}
            onCancel={() => setEditing(false)}
            onSave={async (c) => { if (await act({ corners: c })) setEditing(false) }} />
        ) : (
          <>
            <div className="pair">
              <figure>
                <OriginalWithCorners sid={sid} d={d} />
                <figcaption>Original (arbetskopia) · {d.filename || '–'}</figcaption>
              </figure>
              <figure>
                {d.has_inkmap
                  ? <img className="preview" src={assetUrl(sid, `${d.id}-preview`, key)} alt="Normaliserad ink map" />
                  : <div className="noimg">Ingen normaliserad bild – sätt hörn manuellt.</div>}
                <figcaption>Normaliserad ink map (det som analyseras)</figcaption>
              </figure>
            </div>
            <dl className="facts">
              <dt>Registrering</dt><dd>{METHOD[d.registration.method] ?? d.registration.method}</dd>
              <dt>Täckning</dt><dd>{d.quality.coverage !== undefined ? `${(d.quality.coverage * 100).toFixed(2)} %` : '–'}</dd>
              <dt>Skärpa</dt><dd>{d.quality.sharpness ?? '–'}</dd>
              {d.review_reasons.length > 0 && <><dt>Att granska</dt><dd>{d.review_reasons.join(' ')}</dd></>}
              {d.exclude_reason && <><dt>Utesluten</dt><dd>{d.exclude_reason}</dd></>}
            </dl>
            <div className="row">
              <label>Etikett / namn
                <input value={label} maxLength={60} onChange={(e) => setLabel(e.target.value)} />
              </label>
              <button disabled={busy || label === d.label} onClick={() => act({ label })}>Spara etikett</button>
            </div>
            <div className="row">
              <button onClick={() => setEditing(true)}>Justera hörn manuellt</button>
              {d.status === 'needs_review' && (
                <button className="primary" disabled={busy || !d.has_inkmap} onClick={() => act({ action: 'approve' })}>
                  Godkänn som den är
                </button>
              )}
              {d.status === 'excluded' ? (
                <button disabled={busy} onClick={() => act({ action: 'include' })}>Återinkludera</button>
              ) : (
                <>
                  <input placeholder="Anledning till uteslutning" value={reason} onChange={(e) => setReason(e.target.value)} />
                  <button className="danger" disabled={busy || !reason.trim()} onClick={() => act({ action: 'exclude', reason })}>
                    Uteslut
                  </button>
                </>
              )}
            </div>
          </>
        )}
        {err && <p className="error">{err}</p>}
      </div>
    </div>
  )
}

function OriginalWithCorners({ sid, d }: { sid: string; d: Drawing }) {
  const [w, h] = d.work_size
  const c = d.registration.corners
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="original">
      <image href={assetUrl(sid, `${d.id}-work`)} width={w} height={h} />
      {c && <polygon points={c.map((p) => p.join(',')).join(' ')} fill="none" stroke="#00d0b0" strokeWidth={Math.max(w, h) / 250} />}
    </svg>
  )
}
