import type { DatesSetArg, EventContentArg, EventDropArg } from '@fullcalendar/core'
import idLocale from '@fullcalendar/core/locales/id'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'
import FullCalendar from '@fullcalendar/react'
import timeGridPlugin from '@fullcalendar/timegrid'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { PlatformDot } from '@/components/PlatformDot'
import { Button } from '@/components/ui/button'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { api, type Target } from '@/lib/api'
import { formatWIB, toWibInput } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { useMediaQuery } from '@/lib/useMediaQuery'

import { toChips, wallToUtcIso, type Chip } from './logic'

type View = 'week' | 'month'
const HALF_HOUR = 30 * 60_000

/** Chips span one 30-minute row; works on the WIB wall-time strings the calendar uses. */
const plusHalfHour = (wall: string) =>
  new Date(Date.parse(`${wall}:00Z`) + HALF_HOUR).toISOString().slice(0, 16)
const BUSY = new Set(['waiting_media', 'publishing'])

function ChipContent({ event, timeText }: EventContentArg) {
  const chip = event.extendedProps.chip as Chip
  return (
    <div
      className="flex h-full min-w-0 items-center gap-1.5 overflow-hidden px-1.5 text-[12px] leading-none"
      title={`${chip.labels.join(', ')} · ${chip.caption || 'Tanpa caption'}`}
    >
      <span className="flex shrink-0 -space-x-0.5">
        {chip.platforms.map((p) => (
          <PlatformDot key={p} platform={p} />
        ))}
      </span>
      <span className="shrink-0 tabular-nums">{timeText.replace(':', '.')}</span>
      <span className="text-muted-foreground truncate">
        {chip.caption.slice(0, 30) || 'Tanpa caption'}
      </span>
    </div>
  )
}

export function CalendarPage() {
  const queryClient = useQueryClient()
  const calendar = useRef<FullCalendar>(null)
  const phone = useMediaQuery('(max-width: 767px)')
  const [view, setView] = useState<View>('week')
  const [range, setRange] = useState({ start: '', end: '', title: '' })

  const targets = useQuery({
    queryKey: queryKeys.targetsRange(range.start, range.end),
    queryFn: () =>
      api<Target[]>(`/targets?${new URLSearchParams({ start: range.start, end: range.end })}`),
    enabled: Boolean(range.start),
    placeholderData: (prev) => prev,
    // Publishing happens in the background; refresh faster while something is moving.
    refetchInterval: (q) => (q.state.data?.some((t) => BUSY.has(t.status)) ? 5000 : 60_000),
  })

  const move = useMutation({
    mutationFn: ({ chip, at }: { chip: Chip; at: string; revert: () => void }) =>
      api<Target[]>('/targets/reschedule', {
        method: 'PATCH',
        json: { ids: chip.ids, scheduled_at: at },
      }),
    onSuccess: (_data, { at }) => toast.success(`Jadwal dipindah ke ${formatWIB(at)}.`),
    onError: (err, { revert }) => {
      revert() // the chip already moved on screen; put it back
      toast.error(err.message)
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: queryKeys.allTargets }),
  })

  const cal = () => calendar.current?.getApi()
  const viewName = view === 'month' ? 'dayGridMonth' : phone ? 'timeGridThreeDay' : 'timeGridWeek'

  function onDatesSet(arg: DatesSetArg) {
    setRange({ start: wallToUtcIso(arg.start), end: wallToUtcIso(arg.end), title: arg.view.title })
  }

  function onDrop(arg: EventDropArg) {
    const chip = arg.event.extendedProps.chip as Chip
    if (!arg.event.start) return arg.revert()
    move.mutate({ chip, at: wallToUtcIso(arg.event.start), revert: arg.revert })
  }

  const chips = toChips(targets.data ?? [])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="lg" onClick={() => cal()?.today()}>
          Hari ini
        </Button>
        <Button
          variant="ghost"
          size="icon-lg"
          aria-label="Sebelumnya"
          onClick={() => cal()?.prev()}
        >
          <ChevronLeft aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="icon-lg"
          aria-label="Berikutnya"
          onClick={() => cal()?.next()}
        >
          <ChevronRight aria-hidden />
        </Button>
        <h2
          aria-live="polite"
          className="order-first min-w-0 basis-full truncate font-medium md:order-none md:flex-1 md:basis-auto"
        >
          {range.title}
        </h2>
        <ToggleGroup
          type="single"
          variant="outline"
          className="ml-auto"
          value={view}
          onValueChange={(v) => v && setView(v as View)}
          aria-label="Tampilan kalender"
        >
          <ToggleGroupItem value="week" className="h-9 px-3">
            {phone ? '3 hari' : 'Minggu'}
          </ToggleGroupItem>
          <ToggleGroupItem value="month" className="h-9 px-3">
            Bulan
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      {targets.isError && (
        <div className="flex items-center justify-between gap-3 rounded-xl border px-4 py-3">
          <p className="text-destructive">{targets.error.message}</p>
          <Button variant="outline" size="lg" onClick={() => void targets.refetch()}>
            Coba lagi
          </Button>
        </div>
      )}

      <div
        aria-busy={targets.isFetching}
        className="schedler-calendar bg-card h-[calc(100svh-13rem)] min-h-[480px] overflow-hidden rounded-xl border lg:h-[calc(100svh-11rem)]"
      >
        <FullCalendar
          key={viewName} // switching views by key keeps the date range logic in one place
          ref={calendar}
          plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]}
          locale={idLocale}
          timeZone="UTC"
          now={() => toWibInput(new Date())}
          initialView={viewName}
          initialDate={range.start ? toWibInput(new Date(range.start)) : undefined}
          views={{ timeGridThreeDay: { type: 'timeGrid', duration: { days: 3 } } }}
          headerToolbar={false}
          firstDay={1}
          height="100%"
          allDaySlot={false}
          slotDuration="00:30:00"
          slotLabelInterval="01:00"
          slotLabelFormat={{ hour: '2-digit', minute: '2-digit', hour12: false }}
          eventTimeFormat={{ hour: '2-digit', minute: '2-digit', hour12: false }}
          displayEventEnd={false}
          scrollTime="18:00:00"
          nowIndicator
          dayMaxEvents={4}
          eventDurationEditable={false}
          events={chips.map((chip) => ({
            id: chip.key,
            start: chip.start,
            end: plusHalfHour(chip.start),
            startEditable: chip.movable,
            classNames: ['schedler-chip', `tone-${chip.status}`],
            extendedProps: { chip },
          }))}
          eventContent={(arg) => <ChipContent {...arg} />}
          eventDrop={onDrop}
          datesSet={onDatesSet}
        />
      </div>
      {targets.isSuccess && chips.length === 0 && (
        <p className="text-muted-foreground text-[13px]">
          Belum ada post di periode ini. Tekan N untuk buat post.
        </p>
      )}
    </div>
  )
}
