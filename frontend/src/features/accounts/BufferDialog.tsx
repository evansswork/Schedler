import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { api, type Account, type BufferChannel } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/utils'

export function BufferDialog({ account }: { account: Account }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  // Fetched only while the dialog is open: every listing spends Buffer API budget.
  const channels = useQuery({
    queryKey: queryKeys.bufferChannels,
    queryFn: () => api<BufferChannel[]>('/accounts/buffer-channels'),
    enabled: open,
    staleTime: 5 * 60_000,
    retry: false,
  })
  const link = useMutation({
    mutationFn: (c: BufferChannel) =>
      api<Account>(`/accounts/${account.id}/buffer-channel`, {
        method: 'PUT',
        json: { key_ref: c.key_ref, channel_id: c.id },
      }),
    onSuccess: (saved) => {
      toast.success(`${saved.label} tersambung ke ${saved.handle}.`)
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts })
      setOpen(false)
    },
  })
  const matching = (channels.data ?? []).filter((c) => c.service === account.platform)

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) link.reset()
      }}
    >
      <Button variant="outline" size="lg" onClick={() => setOpen(true)}>
        {account.connected ? 'Ganti channel' : 'Pilih channel'}
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Channel Buffer untuk {account.label}</DialogTitle>
          <DialogDescription>
            Channel diambil dari akun Buffer di BUFFER_API_KEYS. Sambungkan dulu channel{' '}
            {account.platform === 'youtube' ? 'YouTube' : 'TikTok'}-nya di buffer.com kalau belum
            ada.
          </DialogDescription>
        </DialogHeader>
        {channels.isPending ? (
          <div aria-busy className="space-y-2">
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
          </div>
        ) : channels.isError ? (
          <p role="alert" className="text-destructive">
            {channels.error.message}
          </p>
        ) : matching.length === 0 ? (
          <p className="text-muted-foreground">
            Nggak ada channel {account.platform === 'youtube' ? 'YouTube' : 'TikTok'} di Buffer.
          </p>
        ) : (
          <ul className="space-y-2">
            {matching.map((c) => {
              const current = c.id === account.buffer_channel_id
              return (
                <li key={`${c.key_ref}-${c.id}`}>
                  <button
                    type="button"
                    disabled={link.isPending || c.is_disconnected || current}
                    onClick={() => link.mutate(c)}
                    className={cn(
                      'hover:bg-accent flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border px-3 text-left disabled:opacity-60',
                      current && 'border-primary',
                    )}
                  >
                    <span className="min-w-0 truncate">
                      {c.name}
                      <span className="text-muted-foreground text-[13px]"> · {c.organization}</span>
                    </span>
                    <span className="text-muted-foreground shrink-0 text-[13px]">
                      {current ? 'Dipakai' : c.is_disconnected ? 'Terputus di Buffer' : ''}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        {link.isError && (
          <p role="alert" className="text-destructive text-[13px]">
            {link.error.message}
          </p>
        )}
      </DialogContent>
    </Dialog>
  )
}
