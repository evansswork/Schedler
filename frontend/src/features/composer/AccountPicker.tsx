import { PlatformDot } from '@/components/PlatformDot'
import type { Account } from '@/lib/api'
import { cn } from '@/lib/utils'

type Props = {
  accounts: Account[]
  selected: string[]
  onChange: (ids: string[]) => void
  warnings: string[]
}

export function AccountPicker({ accounts, selected, onChange, warnings }: Props) {
  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id])

  return (
    <section aria-labelledby="accounts-title" className="space-y-3">
      <h3 id="accounts-title" className="font-medium">
        Akun tujuan
      </h3>
      {accounts.length === 0 ? (
        <p className="text-muted-foreground text-[13px]">
          Belum ada akun. Jalankan <code>python -m app.cli seed-accounts</code> di backend.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {accounts.map((a) => {
            const on = selected.includes(a.id)
            return (
              <button
                key={a.id}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(a.id)}
                className={cn(
                  'focus-visible:ring-ring/50 inline-flex h-9 items-center gap-2 rounded-full border px-3 text-sm outline-none focus-visible:ring-3',
                  on
                    ? 'border-primary bg-primary/10 text-foreground'
                    : 'text-muted-foreground hover:bg-muted',
                )}
              >
                <PlatformDot platform={a.platform} />
                {a.label}
              </button>
            )
          })}
        </div>
      )}
      {warnings.length > 0 && (
        <ul className="text-status-waiting space-y-1 text-[13px]">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
