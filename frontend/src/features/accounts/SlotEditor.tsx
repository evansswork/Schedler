import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { api, type Account, type AccountUpdate } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

const DAYS = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'] // ISO weekday 1..7

const same = (a: readonly unknown[], b: readonly unknown[]) =>
  a.length === b.length && a.every((v, i) => v === b[i])

export function SlotEditor({ account }: { account: Account }) {
  const queryClient = useQueryClient()
  const [slots, setSlots] = useState(account.slots)
  const [weekdays, setWeekdays] = useState(account.weekdays)
  const [draft, setDraft] = useState('')
  const save = useMutation({
    mutationFn: (body: AccountUpdate) =>
      api<Account>(`/accounts/${account.id}`, { method: 'PATCH', json: body }),
    onSuccess: (saved) => {
      toast.success(`Slot ${saved.label} disimpan.`)
      setSlots(saved.slots)
      setWeekdays(saved.weekdays)
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts })
    },
  })
  const dirty = !same(slots, account.slots) || !same(weekdays, account.weekdays)

  function addSlot() {
    if (draft && !slots.includes(draft)) setSlots([...slots, draft].sort())
    setDraft('')
  }

  return (
    <div className="space-y-3">
      <ToggleGroup
        type="multiple"
        variant="outline"
        value={weekdays.map(String)}
        onValueChange={(v) => setWeekdays(v.map(Number).sort())}
        aria-label={`Hari posting ${account.label}`}
        className="flex-wrap"
      >
        {DAYS.map((day, i) => (
          <ToggleGroupItem key={day} value={String(i + 1)} className="h-9 min-w-11 px-2">
            {day}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      <ul aria-label={`Jam slot ${account.label}`} className="flex flex-wrap gap-2">
        {slots.map((s) => (
          <li
            key={s}
            className="inline-flex h-8 items-center gap-1 rounded-full border pr-1 pl-3 tabular-nums"
          >
            {s.replace(':', '.')}
            <Button
              variant="ghost"
              size="icon-sm"
              className="rounded-full"
              aria-label={`Hapus slot ${s.replace(':', '.')}`}
              onClick={() => setSlots(slots.filter((x) => x !== s))}
            >
              <X aria-hidden />
            </Button>
          </li>
        ))}
        {slots.length === 0 && (
          <li className="text-muted-foreground text-[13px]">
            Belum ada slot. Tambahkan jam supaya mode otomatis bisa dipakai.
          </li>
        )}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="time"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addSlot()
            }
          }}
          aria-label={`Jam slot baru untuk ${account.label}`}
          className="h-9 w-32"
        />
        <Button variant="outline" size="lg" onClick={addSlot} disabled={!draft}>
          <Plus aria-hidden /> Tambah
        </Button>
        {dirty && (
          <Button
            size="lg"
            className="ml-auto"
            disabled={save.isPending || weekdays.length === 0}
            title={weekdays.length === 0 ? 'Pilih minimal satu hari' : undefined}
            onClick={() => save.mutate({ slots, weekdays })}
          >
            {save.isPending ? 'Menyimpan…' : 'Simpan slot'}
          </Button>
        )}
      </div>
      {save.isError && (
        <p role="alert" className="text-destructive text-[13px]">
          {save.error.message}
        </p>
      )}
    </div>
  )
}
