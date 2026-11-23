import { useEffect } from 'react'
import './print.css'

export default function PrintPage() {
  useEffect(() => {
    document.title = 'MEDELTOMTEN – ritmall A4'
  }, [])
  return (
    <div className="print-root">
      <div className="print-toolbar no-print">
        <button onClick={() => window.print()}>Skriv ut</button>
        <span>
          A4 stående · skala 100 % / “faktisk storlek” · inga sidhuvuden. Markörerna i hörnen måste synas helt på
          fotot. Mallen kommer från samma geometri som bildanalysen använder.
        </span>
        <a href="/control">← Tillbaka</a>
      </div>
      <img className="sheet" src="/api/template.svg" alt="Ritmall A4 med fyra markörer och ritram" />
    </div>
  )
}
