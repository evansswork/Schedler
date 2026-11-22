import { useMutation } from '@tanstack/react-query'
import { Upload } from 'lucide-react'
import { useId, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { api, type Media } from '@/lib/api'
import { cn } from '@/lib/utils'

import { parseLinks } from './logic'

type Mode = 'link' | 'upload'

export function SourceInput({ onAdded }: { onAdded: (media: Media[]) => void }) {
  const [mode, setMode] = useState<Mode>('link')
  const [text, setText] = useState('')
  const [invalid, setInvalid] = useState<string[]>([])
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const hintId = useId()

  const addLinks = useMutation({
    mutationFn: (urls: string[]) =>
      api<Media[]>('/media/links', { method: 'POST', json: { urls } }),
    onSuccess: (media) => {
      setText('')
      onAdded(media)
    },
  })
  const upload = useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      files.forEach((f) => form.append('files', f))
      return api<Media[]>('/media/upload', { method: 'POST', form })
    },
    onSuccess: onAdded,
  })

  function submitLinks() {
    const { valid, invalid } = parseLinks(text)
    setInvalid(invalid)
    if (invalid.length === 0 && valid.length > 0) addLinks.mutate(valid)
  }

  function uploadFiles(list: FileList | null) {
    const files = [...(list ?? [])]
    if (files.length) upload.mutate(files)
  }

  const error = addLinks.error?.message ?? upload.error?.message

  return (
    <section aria-labelledby="source-title" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id="source-title" className="font-medium">
          Sumber
        </h3>
        <ToggleGroup
          type="single"
          variant="outline"
          value={mode}
          onValueChange={(v) => v && setMode(v as Mode)}
          aria-label="Sumber video"
        >
          <ToggleGroupItem value="link" className="h-8 px-3">
            Link TikTok
          </ToggleGroupItem>
          <ToggleGroupItem value="upload" className="h-8 px-3">
            Upload MP4
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      {mode === 'link' ? (
        <div className="space-y-2">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
                e.preventDefault()
                submitLinks()
              }
            }}
            rows={3}
            placeholder="Tempel satu atau banyak link (satu per baris)"
            aria-label="Link TikTok"
            aria-describedby={hintId}
            aria-invalid={invalid.length > 0}
          />
          <div className="flex items-start justify-between gap-3">
            <p id={hintId} className="text-muted-foreground text-[13px]">
              {invalid.length > 0 ? (
                <span className="text-destructive">
                  Bukan link video TikTok: {invalid.join(', ')}
                </span>
              ) : (
                'Enter untuk menambahkan, Shift+Enter untuk baris baru.'
              )}
            </p>
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={submitLinks}
              disabled={!text.trim() || addLinks.isPending}
            >
              {addLinks.isPending ? 'Menambahkan…' : 'Tambahkan'}
            </Button>
          </div>
        </div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            uploadFiles(e.dataTransfer.files)
          }}
          className={cn(
            'flex flex-col items-start gap-3 rounded-xl border border-dashed p-4',
            dragging && 'border-primary bg-accent',
          )}
        >
          <p className="text-muted-foreground text-[13px]">
            {upload.isPending ? 'Mengupload…' : 'Tarik file MP4 ke sini, atau pilih dari komputer.'}
          </p>
          <input
            ref={fileInput}
            type="file"
            accept="video/mp4"
            multiple
            className="sr-only"
            onChange={(e) => {
              uploadFiles(e.target.files)
              e.target.value = ''
            }}
          />
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => fileInput.current?.click()}
            disabled={upload.isPending}
          >
            <Upload aria-hidden /> Pilih file
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-destructive text-[13px]">
          {error}
        </p>
      )}
    </section>
  )
}
