import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import ControlPage from './pages/ControlPage.tsx'
import PrintPage from './pages/PrintPage.tsx'
import ShowPage from './pages/ShowPage.tsx'

// Three fixed routes; no router dependency needed.
const path = window.location.pathname.replace(/\/+$/, '')
const Page = path === '/show' ? ShowPage : path === '/print' ? PrintPage : ControlPage

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
)
