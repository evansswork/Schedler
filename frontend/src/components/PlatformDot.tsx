import type { Platform } from '@/lib/api'
import { cn } from '@/lib/utils'

const dot: Record<Platform, string> = {
  ig: 'bg-platform-ig',
  youtube: 'bg-platform-yt',
  tiktok: 'bg-platform-tt',
}

/** Decorative colour dot; always render the platform or account name next to it. */
export function PlatformDot({ platform, className }: { platform: Platform; className?: string }) {
  return (
    <span aria-hidden className={cn('relative inline-flex size-2 shrink-0', className)}>
      <span className={cn('size-2 rounded-full', dot[platform])} />
      {platform === 'tiktok' && (
        <span className="bg-platform-tt-2 absolute top-0 left-1 size-2 rounded-full mix-blend-multiply dark:mix-blend-screen" />
      )}
    </span>
  )
}
