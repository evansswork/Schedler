import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useHealth } from '@/features/health/useHealth'
import { api } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { setTheme, useTheme, type Theme } from '@/lib/theme'

const SHORTCUTS: [string, string][] = [
  ['N', 'Buat post'],
  ['⌘/Ctrl + Enter', 'Jadwalkan (di composer)'],
  ['/', 'Cari di Antrian'],
  ['G lalu C', 'Kalender'],
  ['G lalu A', 'Antrian'],
  ['G lalu P', 'Perlu perhatian'],
  ['G lalu K', 'Akun & slot'],
  ['G lalu S', 'Pengaturan'],
]

function megabytes(bytes: number) {
  return `${(bytes / 1_000_000).toLocaleString('id-ID', { maximumFractionDigits: 1 })} MB`
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="bg-card space-y-3 rounded-xl border p-4">
      <h2 className="font-medium">{title}</h2>
      {children}
    </section>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[13px]">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular-nums">{children}</span>
    </div>
  )
}

export function SettingsPage({ onLogout }: { onLogout: () => void }) {
  const queryClient = useQueryClient()
  const health = useHealth()
  const theme = useTheme()
  const telegramTest = useMutation({
    mutationFn: () => api<undefined>('/settings/telegram/test', { method: 'POST' }),
    onSuccess: () => toast.success('Pesan tes terkirim. Cek Telegram kamu.'),
    onError: (err) => toast.error(err.message),
  })
  const updateYtdlp = useMutation({
    mutationFn: () => api<{ message: string }>('/settings/ytdlp/update', { method: 'POST' }),
    onSuccess: (res) => {
      toast.success(res.message)
      void queryClient.invalidateQueries({ queryKey: queryKeys.health })
    },
    onError: (err) => toast.error(err.message),
  })

  if (health.isPending)
    return (
      <div aria-busy className="grid gap-4 xl:grid-cols-2">
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
      </div>
    )
  if (health.isError)
    return (
      <div className="bg-card flex items-center justify-between gap-3 rounded-xl border px-4 py-6">
        <p className="text-destructive">{health.error.message}</p>
        <Button variant="outline" size="lg" onClick={() => void health.refetch()}>
          Coba lagi
        </Button>
      </div>
    )
  const h = health.data
  const budget = h.buffer_budget

  return (
    <div className="grid items-start gap-4 xl:grid-cols-2">
      <Section title="Telegram">
        <Row label="Status">
          {h.telegram ? 'Aktif' : 'Belum diatur (isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID)'}
        </Row>
        <Row label="Pesan menunggu dikirim">{h.outbox_waiting}</Row>
        <Button
          variant="outline"
          size="lg"
          disabled={!h.telegram || telegramTest.isPending}
          title={h.telegram ? undefined : 'Isi token dan chat id Telegram di .env dulu'}
          onClick={() => telegramTest.mutate()}
        >
          Kirim tes
        </Button>
      </Section>

      <Section title="Sistem">
        <Row label="Mode uji">
          {h.dry_run ? (
            <span className="text-status-waiting">Aktif: nggak ada yang beneran diposting</span>
          ) : (
            'Mati: posting beneran'
          )}
        </Row>
        <p className="text-muted-foreground text-[13px]">
          Ubah lewat DRY_RUN di .env, lalu restart backend.
        </p>
        <Row label="Pengunduh (yt-dlp)">
          {h.ytdlp.running}
          {h.ytdlp.installed !== h.ytdlp.running && ` → ${h.ytdlp.installed} setelah restart`}
        </Row>
        {h.ytdlp.last_update && (
          <p className="text-muted-foreground text-[13px]">{h.ytdlp.last_update}</p>
        )}
        <Button
          variant="outline"
          size="lg"
          disabled={updateYtdlp.isPending}
          onClick={() => updateYtdlp.mutate()}
        >
          {updateYtdlp.isPending ? 'Mengupdate…' : 'Update sekarang'}
        </Button>
      </Section>

      <Section title="Storage & Buffer">
        <Row label="Penyimpanan video">
          {h.storage_backend === 'r2' ? 'Cloudflare R2' : 'Lokal (VPS)'} ·{' '}
          {megabytes(h.storage_bytes)}
        </Row>
        <Row label="Sisa API Buffer hari ini">
          {budget?.day_quota != null ? `${budget.day_left}/${budget.day_quota}` : 'Belum ada data'}
        </Row>
        <Row label="Sisa API Buffer 30 hari">
          {budget?.month_quota != null
            ? `${budget.month_left}/${budget.month_quota}`
            : 'Belum ada data'}
        </Row>
      </Section>

      <Section title="Tampilan">
        <ToggleGroup
          type="single"
          variant="outline"
          value={theme}
          onValueChange={(v) => v && setTheme(v as Theme)}
          aria-label="Tema"
        >
          <ToggleGroupItem value="system" className="h-9 px-3">
            Ikuti sistem
          </ToggleGroupItem>
          <ToggleGroupItem value="light" className="h-9 px-3">
            Terang
          </ToggleGroupItem>
          <ToggleGroupItem value="dark" className="h-9 px-3">
            Gelap
          </ToggleGroupItem>
        </ToggleGroup>
        <h3 className="text-muted-foreground pt-2 text-[11px] tracking-wide uppercase">
          Shortcut keyboard
        </h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
          {SHORTCUTS.map(([keys, what]) => (
            <div key={keys} className="contents">
              <dt>
                <kbd className="bg-muted rounded px-1.5 py-0.5 text-[12px]">{keys}</kbd>
              </dt>
              <dd className="text-muted-foreground">{what}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Akun dashboard">
        <p className="text-muted-foreground text-[13px]">
          Ganti password: jalankan <code>python -m app.cli hash-password</code> lalu ganti
          ADMIN_PASSWORD_HASH di .env.
        </p>
        <Button variant="outline" size="lg" onClick={onLogout}>
          <LogOut aria-hidden /> Keluar
        </Button>
      </Section>
    </div>
  )
}
