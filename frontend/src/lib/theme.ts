import { useSyncExternalStore } from 'react'

export type Theme = 'system' | 'light' | 'dark'

const KEY = 'schedler.theme' // also read by the inline script in index.html
const media = () => window.matchMedia('(prefers-color-scheme: dark)')
const listeners = new Set<() => void>()

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system' // storage blocked: follow the system
  }
}

function apply(theme: Theme) {
  const dark = theme === 'dark' || (theme === 'system' && media().matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}

export function setTheme(theme: Theme) {
  try {
    if (theme === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, theme)
  } catch {
    // not persisted; still applied for this visit
  }
  apply(theme)
  listeners.forEach((l) => l())
}

/** Follow OS changes while the choice is "system". Call once at startup. */
export function watchSystemTheme() {
  media().addEventListener('change', () => {
    if (read() === 'system') apply('system')
  })
}

export function useTheme(): Theme {
  return useSyncExternalStore((l) => {
    listeners.add(l)
    return () => listeners.delete(l)
  }, read)
}
