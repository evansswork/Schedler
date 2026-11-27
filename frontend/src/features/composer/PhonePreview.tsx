import { PlatformDot } from '@/components/PlatformDot'
import type { Platform } from '@/lib/api'

const NAMES: Record<Platform, string> = { ig: 'Reels', youtube: 'YouTube', tiktok: 'TikTok' }

type Props = { platform: Platform; videoUrl: string | null; caption: string; title?: string }

/** Rough phone-frame preview: where the caption sits and how much of it shows. */
export function PhonePreview({ platform, videoUrl, caption, title }: Props) {
  return (
    <figure className="flex items-start gap-3">
      <div className="relative aspect-[9/16] w-36 shrink-0 overflow-hidden rounded-2xl border-4 border-neutral-900 bg-neutral-900">
        {videoUrl && (
          <video src={videoUrl} muted preload="metadata" className="size-full object-contain" />
        )}
        <div className="absolute inset-x-0 bottom-0 space-y-0.5 bg-black/60 px-2 py-1.5 text-[10px] leading-tight text-white">
          {title && <p className="line-clamp-2 font-medium">{title}</p>}
          <p className="line-clamp-2 opacity-90">{caption || 'Tanpa caption'}</p>
        </div>
      </div>
      <figcaption className="text-muted-foreground flex items-center gap-1.5 text-[13px]">
        <PlatformDot platform={platform} /> Preview {NAMES[platform]}
      </figcaption>
    </figure>
  )
}
