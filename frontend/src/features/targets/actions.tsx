import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RotateCcw, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { api, type Target } from '@/lib/api'
import { formatWIB } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'

function useRefreshTargets() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.allTargets })
}

export function RetryButton({ target, compact = false }: { target: Target; compact?: boolean }) {
  const refresh = useRefreshTargets()
  const retry = useMutation({
    mutationFn: () => api<Target>(`/targets/${target.id}/retry`, { method: 'POST' }),
    onSuccess: () => {
      toast.success(`Post di ${target.account.label} dicoba lagi.`)
      void refresh()
    },
    onError: (err) => toast.error(err.message),
  })
  if (compact)
    return (
      <Button
        variant="ghost"
        size="icon-lg"
        aria-label={`Coba lagi post di ${target.account.label}`}
        title="Coba lagi"
        disabled={retry.isPending}
        onClick={() => retry.mutate()}
      >
        <RotateCcw aria-hidden />
      </Button>
    )
  return (
    <Button variant="outline" size="lg" disabled={retry.isPending} onClick={() => retry.mutate()}>
      <RotateCcw aria-hidden /> Coba lagi
    </Button>
  )
}

export function CancelButton({ target }: { target: Target }) {
  const queryClient = useQueryClient()
  const refresh = useRefreshTargets()
  const [open, setOpen] = useState(false)
  const cancel = useMutation({
    mutationFn: () => api<Target>(`/targets/${target.id}/cancel`, { method: 'POST' }),
    onMutate: () => {
      // Optimistic: drop the row everywhere; a refetch restores it if the server refuses.
      queryClient.setQueriesData<Target[]>({ queryKey: queryKeys.allTargets }, (old) =>
        old?.filter((t) => t.id !== target.id),
      )
      setOpen(false)
    },
    onSuccess: () => toast.success(`Post di ${target.account.label} dibatalkan.`),
    onError: (err) => toast.error(err.message),
    onSettled: () => void refresh(),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button
        variant="ghost"
        size="icon-lg"
        aria-label={`Batalkan post di ${target.account.label}`}
        title="Batalkan"
        onClick={() => setOpen(true)}
      >
        <X aria-hidden />
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Batalkan post di {target.account.label}?</DialogTitle>
          <DialogDescription>
            Jadwal {formatWIB(target.scheduled_at)} dihapus. Post yang sama di akun lain nggak ikut
            dibatalkan.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" size="lg">
              Kembali
            </Button>
          </DialogClose>
          <Button variant="destructive" size="lg" onClick={() => cancel.mutate()}>
            Batalkan post
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
