import { useQuery } from '@tanstack/react-query'

import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { api, type Account, type ScheduleMode } from '@/lib/api'
import { formatWIB } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'

type Props = {
  mode: ScheduleMode
  onMode: (mode: ScheduleMode) => void
  accounts: Account[]
  accountIds: string[]
  count: number
}

export function SchedulePicker({ mode, onMode, accounts, accountIds, count }: Props) {
  const preview = useQuery({
    queryKey: queryKeys.slotsPreview(accountIds, count),
    queryFn: () =>
      api<Record<string, string[]>>(
        `/slots/preview?${new URLSearchParams([
          ...accountIds.map((id) => ['account_ids', id]),
          ['count', String(count)],
        ])}`,
      ),
    enabled: mode === 'slot' && count > 0 && accountIds.length > 0,
    retry: false,
  })
  const label = (id: string) => accounts.find((a) => a.id === id)?.label ?? 'Akun'
  const earliest = Object.values(preview.data ?? {})
    .flat()
    .sort()[0]

  return (
    <section aria-labelledby="schedule-title" className="space-y-3">
      <h3 id="schedule-title" className="font-medium">
        Jadwal
      </h3>
      <ToggleGroup
        type="single"
        variant="outline"
        value={mode}
        onValueChange={(v) => v && onMode(v as ScheduleMode)}
        aria-label="Cara menjadwalkan"
        className="w-full"
      >
        <ToggleGroupItem value="slot" className="h-9 flex-1">
          Slot berikutnya (otomatis)
        </ToggleGroupItem>
        <ToggleGroupItem value="exact" className="h-9 flex-1">
          Pilih waktu
        </ToggleGroupItem>
      </ToggleGroup>

      {mode === 'exact' ? (
        <p className="text-muted-foreground text-[13px]">Atur waktu tayang di setiap video.</p>
      ) : count === 0 || accountIds.length === 0 ? (
        <p className="text-muted-foreground text-[13px]">
          Tambahkan video dan pilih akun untuk melihat slotnya.
        </p>
      ) : preview.isError ? (
        <p role="alert" className="text-destructive text-[13px]">
          {preview.error.message}
        </p>
      ) : preview.isPending ? (
        <p className="text-muted-foreground text-[13px]">Mencari slot kosong…</p>
      ) : (
        <div className="space-y-2 text-[13px]" aria-live="polite">
          {earliest && (
            <p>
              {count} video akan disebar ke slot kosong mulai {formatWIB(earliest)}.
            </p>
          )}
          <ul className="text-muted-foreground space-y-1">
            {accountIds.map((id) => {
              const times = preview.data[id] ?? []
              return (
                <li key={id} className="tabular-nums">
                  <span className="text-foreground">{label(id)}</span>:{' '}
                  {times.length > 1
                    ? `${formatWIB(times[0])} sampai ${formatWIB(times[times.length - 1])}`
                    : times[0] && formatWIB(times[0])}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
