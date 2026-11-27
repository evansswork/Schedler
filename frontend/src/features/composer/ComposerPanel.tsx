import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useFieldArray, useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { api, type Account, type Media, type PostBatch, type Target } from '@/lib/api'
import { fromWibInput } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'

import { AccountPicker } from './AccountPicker'
import { accountWarnings, apiOverrides, nextTimes, submitError, type ComposerValues } from './logic'
import { SchedulePicker } from './SchedulePicker'
import { SourceInput } from './SourceInput'
import { VideoRow } from './VideoRow'

const DRAFT_KEY = 'schedler.composer.draft'
const ACCOUNTS_KEY = 'schedler.composer.accounts'
const IN_PROGRESS = new Set(['pending', 'downloading', 'processing'])

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback // storage blocked or corrupted draft: start fresh
  }
}

function emptyValues(): ComposerValues {
  return { rows: [], accountIds: readJson<string[]>(ACCOUNTS_KEY, []), mode: 'slot' }
}

function savedValues(): ComposerValues {
  // Drafts saved before schedule modes existed have no `mode`.
  return { ...emptyValues(), ...readJson<Partial<ComposerValues>>(DRAFT_KEY, {}) }
}

type Props = { open: boolean; onOpenChange: (open: boolean) => void; accounts: Account[] }

export function ComposerPanel({ open, onOpenChange, accounts }: Props) {
  const queryClient = useQueryClient()
  const form = useForm<ComposerValues>({
    defaultValues: savedValues(),
  })
  const { fields, append, remove } = useFieldArray({ control: form.control, name: 'rows' })
  const rows = useWatch({ control: form.control, name: 'rows' })
  const accountIds = useWatch({ control: form.control, name: 'accountIds' })
  const mode = useWatch({ control: form.control, name: 'mode' })
  const [submitMessage, setSubmitMessage] = useState<string | null>(null)

  const mediaIds = rows.map((r) => r.mediaId)
  const mediaQuery = useQuery({
    queryKey: queryKeys.media(mediaIds),
    queryFn: () => api<Media[]>(`/media?${new URLSearchParams(mediaIds.map((id) => ['ids', id]))}`),
    enabled: mediaIds.length > 0,
    refetchInterval: (q) => (q.state.data?.some((m) => IN_PROGRESS.has(m.status)) ? 3000 : false),
  })
  const media = useMemo(
    () => new Map((mediaQuery.data ?? []).map((m) => [m.id, m])),
    [mediaQuery.data],
  )

  // Autosave so closing the panel or reloading never loses work.
  useEffect(() => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ rows, accountIds, mode }))
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accountIds))
  }, [rows, accountIds, mode])

  // Prefill each caption from TikTok once it is known, unless the owner already typed one.
  useEffect(() => {
    rows.forEach((row, i) => {
      const caption = media.get(row.mediaId)?.source_caption
      if (caption && !row.captionTouched && !row.caption) {
        form.setValue(`rows.${i}.caption`, caption)
      }
    })
  }, [media, rows, form])

  function addMedia(added: Media[]) {
    const known = new Set(mediaIds)
    const fresh = added.filter((m) => !known.has(m.id))
    const times = nextTimes(fresh.length, new Date(), rows.at(-1)?.time)
    append(
      fresh.map((m, i) => ({
        mediaId: m.id,
        caption: m.source_caption ?? '',
        time: times[i] ?? '',
        captionTouched: false,
      })),
    )
    setSubmitMessage(null)
  }

  const schedule = useMutation({
    mutationFn: (batch: PostBatch) => api<Target[]>('/posts', { method: 'POST', json: batch }),
    onSuccess: () => {
      toast.success(`Beres! ${rows.length} video terjadwal.`)
      form.reset(emptyValues())
      localStorage.removeItem(DRAFT_KEY)
      void queryClient.invalidateQueries({ queryKey: queryKeys.allTargets })
      onOpenChange(false)
    },
    onError: (err) => setSubmitMessage(err.message),
  })

  function submit() {
    const values = form.getValues()
    const problem = submitError(values, media, new Date())
    setSubmitMessage(problem)
    if (problem || schedule.isPending) return
    schedule.mutate({
      account_ids: values.accountIds,
      schedule_mode: values.mode,
      items: values.rows.map((r) => ({
        media_id: r.mediaId,
        caption: r.caption,
        scheduled_at: values.mode === 'exact' ? fromWibInput(r.time) : null,
        overrides: apiOverrides(r),
      })),
    })
  }

  const readyMedia = [...media.values()].filter((m) => m.status === 'ready')
  const platforms = [
    ...new Set(accounts.filter((a) => accountIds.includes(a.id)).map((a) => a.platform)),
  ]
  const warnings = accountWarnings(accounts, accountIds, readyMedia)
  const summary =
    rows.length && accountIds.length
      ? `${rows.length} video siap dijadwalkan ke ${accountIds.length} akun`
      : 'Tambahkan video dan pilih akun tujuan.'

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[480px]"
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            submit()
          }
        }}
      >
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="text-base font-medium">Buat post</SheetTitle>
          <SheetDescription className="text-[13px]">
            Tempel link TikTok atau upload MP4, pilih akun dan waktunya.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-6 overflow-y-auto p-4">
          <SourceInput onAdded={addMedia} />

          {fields.length > 0 && (
            <section aria-labelledby="videos-title" className="space-y-3">
              <h3 id="videos-title" className="font-medium">
                Video <span className="text-muted-foreground tabular-nums">({fields.length})</span>
              </h3>
              <ul className="space-y-3">
                {fields.map((field, i) => (
                  <VideoRow
                    key={field.id}
                    index={i}
                    media={media.get(field.mediaId)}
                    row={rows[i] ?? field}
                    platforms={platforms}
                    time={mode === 'exact' ? (rows[i]?.time ?? '') : null}
                    onCaption={(v) => {
                      form.setValue(`rows.${i}.caption`, v)
                      form.setValue(`rows.${i}.captionTouched`, true)
                    }}
                    onOverride={(platform, patch) =>
                      form.setValue(`rows.${i}.overrides`, {
                        ...rows[i]?.overrides,
                        [platform]: { ...rows[i]?.overrides?.[platform], ...patch },
                      })
                    }
                    onTime={(v) => form.setValue(`rows.${i}.time`, v)}
                    onRemove={() => remove(i)}
                  />
                ))}
              </ul>
            </section>
          )}

          <AccountPicker
            accounts={accounts}
            selected={accountIds}
            onChange={(ids) => form.setValue('accountIds', ids)}
            warnings={warnings}
          />

          <SchedulePicker
            mode={mode}
            onMode={(m) => form.setValue('mode', m)}
            accounts={accounts}
            accountIds={accountIds}
            count={rows.length}
          />
        </div>

        <SheetFooter className="border-t px-4 py-3">
          {submitMessage && (
            <p role="alert" className="text-destructive text-[13px]">
              {submitMessage}
            </p>
          )}
          <div className="flex items-center justify-between gap-3">
            <p className="text-muted-foreground text-[13px]">{summary}</p>
            <Button size="lg" onClick={submit} disabled={schedule.isPending}>
              {schedule.isPending ? 'Menjadwalkan…' : 'Jadwalkan'}
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
