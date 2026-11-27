import { useEffect } from 'react'

import { pageHref, type Page } from './route'

const GO: Record<string, Page> = {
  c: 'kalender',
  a: 'antrian',
  p: 'perhatian',
  k: 'akun',
  s: 'pengaturan',
}
export const QUEUE_SEARCH_ID = 'queue-search'

function isTyping(el: EventTarget | null) {
  return (
    el instanceof HTMLElement &&
    (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))
  )
}

/** N new post, / search Antrian, G then C/A/P/K/S to switch pages (DESIGN §7). */
export function useShortcuts(openComposer: () => void) {
  useEffect(() => {
    let goUntil = 0
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return
      const key = e.key.toLowerCase()
      if (Date.now() < goUntil && GO[key]) {
        e.preventDefault()
        goUntil = 0
        window.location.hash = pageHref(GO[key])
      } else if (key === 'g') {
        goUntil = Date.now() + 1500
      } else if (key === 'n') {
        e.preventDefault()
        openComposer()
      } else if (key === '/') {
        e.preventDefault()
        window.location.hash = pageHref('antrian')
        // The search box mounts with the page; focus it on the next frame.
        requestAnimationFrame(() => document.getElementById(QUEUE_SEARCH_ID)?.focus())
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openComposer])
}
