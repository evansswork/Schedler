import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Download } from 'lucide-react'
import { toast } from 'sonner'

import { PlatformDot } from '@/components/PlatformDot'
import { Button } from '@/components/ui/button'
import { api, type Target } from '@/lib/api'
import { formatWIB } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'

/** A post the platform route could not publish: the owner uploads it by hand. */
export function ManualItem({ target }: { target: Target }) {
  const queryClient = useQueryClient()
  const done = useMutation({
    mutationFn: () => api<Target>(`/targets/${target.id}/mark-published`, { method: 'POST' }),
    onSuccess: () => {
      toast.success(`Post di ${target.account.label} ditandai tayang.`)
      void queryClient.invalidateQueries({ queryKey: queryKeys.allTargets })
    },
    onError: (err) => toast.error(err.message),
  })

  async function copyCaption() {
    try {
      await navigator.clipboard.writeText(target.caption)
      toast.success('Caption disalin.')
    } catch {
      toast.error('Browser menolak menyalin. Salin caption-nya secara manual.')
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1 basis-full space-y-1 md:basis-auto">
        <p className="text-status-manual">{target.last_error_human ?? 'Perlu diupload manual.'}</p>
        <p className="text-muted-foreground flex flex-wrap items-center gap-x-3 text-[13px]">
          <span className="inline-flex items-center gap-1.5">
            <PlatformDot platform={target.account.platform} />
            {target.account.label}
          </span>
          <span className="tabular-nums">{formatWIB(target.scheduled_at)}</span>
        </p>
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-1">
        {target.media.public_url && (
          <Button asChild variant="outline" size="lg">
            <a href={target.media.public_url} target="_blank" rel="noreferrer" download>
              <Download aria-hidden /> Unduh file
            </a>
          </Button>
        )}
        <Button variant="outline" size="lg" onClick={() => void copyCaption()}>
          <Copy aria-hidden /> Salin caption
        </Button>
        <Button variant="outline" size="lg" disabled={done.isPending} onClick={() => done.mutate()}>
          <Check aria-hidden /> Sudah diposting
        </Button>
      </div>
    </li>
  )
}
