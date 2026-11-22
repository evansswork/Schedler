import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, setCsrfToken, type Me } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

const schema = z.object({ password: z.string().min(1, 'Isi password dulu.') })
type Values = z.infer<typeof schema>

export function LoginPage() {
  const queryClient = useQueryClient()
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { password: '' } })
  const login = useMutation({
    mutationFn: (values: Values) => api<Me>('/auth/login', { method: 'POST', json: values }),
    onSuccess: (me) => {
      setCsrfToken(me.csrf_token)
      queryClient.setQueryData(queryKeys.me, me)
    },
  })
  const error = form.formState.errors.password?.message ?? login.error?.message

  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <form
        onSubmit={form.handleSubmit((v) => login.mutate(v))}
        className="bg-card w-full max-w-sm space-y-4 rounded-xl border p-6"
      >
        <div className="space-y-1">
          <h1 className="text-xl font-medium">Schedler</h1>
          <p className="text-muted-foreground text-[13px]">Masuk untuk mengatur jadwal video.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            autoFocus
            aria-invalid={Boolean(error)}
            aria-describedby={error ? 'password-error' : undefined}
            {...form.register('password')}
          />
          {error && (
            <p id="password-error" role="alert" className="text-destructive text-[13px]">
              {error}
            </p>
          )}
        </div>
        <Button type="submit" className="h-9 w-full" disabled={login.isPending}>
          {login.isPending ? 'Masuk…' : 'Masuk'}
        </Button>
      </form>
    </main>
  )
}
