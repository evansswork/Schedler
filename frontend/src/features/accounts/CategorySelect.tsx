import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api, type Account } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

export function CategorySelect({ account }: { account: Account }) {
  const queryClient = useQueryClient()
  const categories = useQuery({
    queryKey: queryKeys.ytCategories,
    queryFn: () => api<Record<string, string>>('/accounts/youtube-categories'),
    staleTime: Infinity,
  })
  const save = useMutation({
    mutationFn: (id: string) =>
      api<Account>(`/accounts/${account.id}`, { method: 'PATCH', json: { yt_category_id: id } }),
    onSuccess: (saved) => {
      toast.success(`Kategori ${saved.label} disimpan.`)
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts })
    },
    onError: (err) => toast.error(err.message),
  })
  const id = `cat-${account.id}`
  return (
    <div className="flex flex-wrap items-center gap-2 text-[13px]">
      <label htmlFor={id} className="text-muted-foreground">
        Kategori YouTube
      </label>
      <select
        id={id}
        value={account.yt_category_id ?? '22'}
        disabled={!categories.data || save.isPending}
        onChange={(e) => save.mutate(e.target.value)}
        className="border-input bg-background focus-visible:ring-ring/50 dark:bg-input/30 h-9 rounded-lg border px-2 outline-none focus-visible:ring-3"
      >
        {Object.entries(categories.data ?? {}).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </div>
  )
}
