import { Eye } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import type { Platform } from '@/lib/api'
import { cn } from '@/lib/utils'

import {
  captionFor,
  defaultTitle,
  hashtagCount,
  IG_MAX_HASHTAGS,
  YT_TITLE_MAX,
  type Override,
  type Row,
} from './logic'
import { PhonePreview } from './PhonePreview'

const LABELS: Record<Platform, string> = { ig: 'Instagram', youtube: 'YouTube', tiktok: 'TikTok' }
const SAME = 'Kosongkan untuk pakai caption Semua'

type Props = {
  n: number
  row: Row
  platforms: Platform[] // platforms of the selected accounts
  videoUrl: string | null
  placeholder: string
  onCaption: (value: string) => void
  onOverride: (platform: Platform, patch: Override) => void
}

export function CaptionTabs({ n, row, platforms, videoUrl, placeholder, ...on }: Props) {
  const [tab, setTab] = useState<'all' | Platform>('all')
  const [preview, setPreview] = useState(false)
  const own = (p: Platform) => row.overrides?.[p] ?? {}
  const hasOverride = (p: Platform) => Boolean(own(p).caption?.trim() || own(p).title?.trim())
  const tags = hashtagCount(captionFor(row, 'ig'))
  const previewPlatform: Platform = tab === 'all' ? (platforms[0] ?? 'ig') : tab

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as 'all' | Platform)} className="gap-2">
      <div className="flex items-center gap-2">
        <TabsList className="h-8 max-w-full justify-start overflow-x-auto">
          <TabsTrigger value="all" className="px-2 text-[13px]">
            Semua
          </TabsTrigger>
          {platforms.map((p) => (
            <TabsTrigger key={p} value={p} className="px-2 text-[13px]">
              {LABELS[p]}
              {hasOverride(p) && (
                <span aria-label="diubah" className="bg-primary size-1.5 rounded-full" />
              )}
            </TabsTrigger>
          ))}
        </TabsList>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="ml-auto"
          aria-pressed={preview}
          aria-label={`Preview video ${n}`}
          title="Preview"
          onClick={() => setPreview(!preview)}
        >
          <Eye aria-hidden />
        </Button>
      </div>

      <TabsContent value="all">
        <Textarea
          value={row.caption}
          onChange={(e) => on.onCaption(e.target.value)}
          rows={2}
          placeholder={placeholder}
          aria-label={`Caption video ${n}`}
        />
      </TabsContent>
      {platforms.includes('ig') && (
        <TabsContent value="ig" className="space-y-1">
          <Textarea
            value={own('ig').caption ?? ''}
            onChange={(e) => on.onOverride('ig', { caption: e.target.value })}
            rows={2}
            placeholder={SAME}
            aria-label={`Caption Instagram video ${n}`}
          />
          <p
            className={cn(
              'text-muted-foreground text-right text-[12px] tabular-nums',
              tags > IG_MAX_HASHTAGS && 'text-destructive',
            )}
          >
            {tags}/{IG_MAX_HASHTAGS} hashtag
          </p>
        </TabsContent>
      )}
      {platforms.includes('youtube') && (
        <TabsContent value="youtube" className="space-y-2">
          <div className="space-y-1">
            <Input
              value={own('youtube').title ?? ''}
              onChange={(e) => on.onOverride('youtube', { title: e.target.value })}
              maxLength={YT_TITLE_MAX}
              placeholder={defaultTitle(row)}
              aria-label={`Judul YouTube video ${n}`}
              className="h-9"
            />
            <p className="text-muted-foreground text-right text-[12px] tabular-nums">
              {(own('youtube').title || defaultTitle(row)).length}/{YT_TITLE_MAX}
            </p>
          </div>
          <Textarea
            value={own('youtube').caption ?? ''}
            onChange={(e) => on.onOverride('youtube', { caption: e.target.value })}
            rows={2}
            placeholder={`Deskripsi. ${SAME}`}
            aria-label={`Deskripsi YouTube video ${n}`}
          />
        </TabsContent>
      )}
      {platforms.includes('tiktok') && (
        <TabsContent value="tiktok">
          <Textarea
            value={own('tiktok').caption ?? ''}
            onChange={(e) => on.onOverride('tiktok', { caption: e.target.value })}
            rows={2}
            placeholder={SAME}
            aria-label={`Caption TikTok video ${n}`}
          />
        </TabsContent>
      )}

      {preview && (
        <PhonePreview
          platform={previewPlatform}
          videoUrl={videoUrl}
          caption={captionFor(row, previewPlatform)}
          title={
            previewPlatform === 'youtube' ? own('youtube').title || defaultTitle(row) : undefined
          }
        />
      )}
    </Tabs>
  )
}
