import { CalendarDays, CircleAlert, ListVideo, Settings, UserCog } from 'lucide-react'
import { useSyncExternalStore, type ComponentType } from 'react'

export const PAGES = {
  kalender: 'Kalender',
  antrian: 'Antrian',
  perhatian: 'Perlu perhatian',
  akun: 'Akun & slot',
  pengaturan: 'Pengaturan',
} as const
export type Page = keyof typeof PAGES

export const ICONS: Record<Page, ComponentType<{ className?: string; 'aria-hidden'?: boolean }>> = {
  kalender: CalendarDays,
  antrian: ListVideo,
  perhatian: CircleAlert,
  akun: UserCog,
  pengaturan: Settings,
}

/** "#/antrian" → "antrian"; anything unknown falls back to the calendar. */
export function parsePage(hash: string): Page {
  const name = hash.replace(/^#\/?/, '')
  return Object.hasOwn(PAGES, name) ? (name as Page) : 'kalender'
}

export const pageHref = (page: Page) => `#/${page}`

function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

export function usePage(): Page {
  return useSyncExternalStore(subscribe, () => parsePage(window.location.hash))
}
