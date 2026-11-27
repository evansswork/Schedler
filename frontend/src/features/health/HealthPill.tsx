import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { pageHref } from '@/app/route'
import { cn } from '@/lib/utils'

import { useHealth } from './useHealth'

const META = {
  ok: { label: 'Semua aman', dot: 'bg-status-published' },
  warn: { label: 'Perlu dicek', dot: 'bg-status-waiting' },
  error: { label: 'Ada masalah', dot: 'bg-status-failed' },
} as const

export function HealthPill() {
  const health = useHealth()
  if (!health.data) return null
  const { status, problems } = health.data
  const meta = META[status]
  return (
    <Popover>
      <PopoverTrigger
        className="hover:bg-accent inline-flex h-9 items-center gap-2 rounded-full border px-3 text-[13px]"
        aria-label={`Kesehatan sistem: ${meta.label}`}
      >
        <span aria-hidden className={cn('size-2 rounded-full', meta.dot)} />
        {meta.label}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 space-y-3 text-[13px]">
        {problems.length === 0 ? (
          <p>Semua aman. Nggak ada yang perlu kamu urus.</p>
        ) : (
          <ul className="list-disc space-y-1 pl-4">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        <div className="flex gap-3">
          <a
            className="text-primary underline-offset-4 hover:underline"
            href={pageHref('perhatian')}
          >
            Perlu perhatian
          </a>
          <a
            className="text-primary underline-offset-4 hover:underline"
            href={pageHref('pengaturan')}
          >
            Pengaturan
          </a>
        </div>
      </PopoverContent>
    </Popover>
  )
}
