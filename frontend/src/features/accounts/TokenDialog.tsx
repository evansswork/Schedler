import { useMutation, useQueryClient } from '@tanstack/react-query'
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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { api, type Account } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

type Props = { account: Account; reconnect: boolean }

export function TokenDialog({ account, reconnect }: Props) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [token, setToken] = useState('')
  const connect = useMutation({
    mutationFn: () =>
      api<Account>(`/accounts/${account.id}/ig-token`, { method: 'PUT', json: { token } }),
    onSuccess: (saved) => {
      toast.success(`${saved.label} tersambung sebagai @${saved.handle}.`)
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts })
      setToken('')
      setOpen(false)
    },
  })
  const fieldId = `token-${account.id}`

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) connect.reset()
      }}
    >
      <Button variant="outline" size="lg" onClick={() => setOpen(true)}>
        {reconnect ? 'Sambungkan ulang' : 'Tempel token'}
      </Button>
      <DialogContent className="sm:max-w-lg">
        <form
          className="contents"
          onSubmit={(e) => {
            e.preventDefault()
            if (token.trim()) connect.mutate()
          }}
        >
          <DialogHeader>
            <DialogTitle>Sambungkan {account.label}</DialogTitle>
            <DialogDescription>
              Buka Meta App Dashboard → Instagram → API setup with Instagram business login, klik
              Generate token di akun ini, lalu tempel di sini. Langkah lengkapnya ada di README
              bagian Setup Instagram.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor={fieldId}>Access token</Label>
            <Textarea
              id={fieldId}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              rows={4}
              autoComplete="off"
              spellCheck={false}
              className="font-mono text-[13px] break-all"
              aria-invalid={connect.isError || undefined}
              aria-describedby={connect.isError ? `${fieldId}-error` : undefined}
            />
            {connect.isError && (
              <p id={`${fieldId}-error`} role="alert" className="text-destructive text-[13px]">
                {connect.error.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" size="lg">
                Batal
              </Button>
            </DialogClose>
            <Button type="submit" size="lg" disabled={!token.trim() || connect.isPending}>
              {connect.isPending ? 'Mengecek token…' : 'Sambungkan'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
