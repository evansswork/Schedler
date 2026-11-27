import { Plus } from 'lucide-react'

import { cn } from '@/lib/utils'

import { ICONS, PAGES, pageHref, type Page } from './route'

const SHORT: Record<Page, string> = {
  kalender: 'Kalender',
  antrian: 'Antrian',
  perhatian: 'Perhatian',
  akun: 'Akun',
}

export function Count({ n, className }: { n: number; className?: string }) {
  if (!n) return null
  return (
    <span
      className={cn(
        'bg-status-failed text-background rounded-full px-1.5 text-[11px] leading-4 font-medium tabular-nums',
        className,
      )}
    >
      {n}
    </span>
  )
}

type BarProps = { page: Page; attention: number; onCreate: () => void }

/** Phone navigation (DESIGN §2): Kalender, Antrian, +Buat, Perhatian, Akun. */
export function TabBar({ page, attention, onCreate }: BarProps) {
  const pages = Object.keys(PAGES) as Page[]
  return (
    <nav
      aria-label="Menu utama"
      className="bg-background fixed inset-x-0 bottom-0 z-40 grid h-16 grid-cols-5 border-t lg:hidden"
    >
      {pages.slice(0, 2).map((p) => (
        <TabLink key={p} page={p} current={page} />
      ))}
      <button
        type="button"
        onClick={onCreate}
        className="text-primary flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium"
      >
        <span className="bg-primary text-primary-foreground flex size-8 items-center justify-center rounded-full">
          <Plus aria-hidden className="size-4" />
        </span>
        Buat
      </button>
      {pages.slice(2).map((p) => (
        <TabLink key={p} page={p} current={page} count={p === 'perhatian' ? attention : 0} />
      ))}
    </nav>
  )
}

function TabLink({ page, current, count = 0 }: { page: Page; current: Page; count?: number }) {
  const Icon = ICONS[page]
  return (
    <a
      href={pageHref(page)}
      aria-current={page === current ? 'page' : undefined}
      className={cn(
        'text-muted-foreground relative flex flex-col items-center justify-center gap-1 text-[11px]',
        page === current && 'text-foreground font-medium',
      )}
    >
      <Icon aria-hidden className="size-5" />
      {SHORT[page]}
      <Count n={count} className="absolute top-1.5 left-1/2 ml-1.5" />
    </a>
  )
}
