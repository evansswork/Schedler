import { RectangleHorizontal, RectangleVertical, Square } from 'lucide-react'

import type { Orientation } from '@/lib/api'

const meta: Record<Orientation, { label: string; Icon: typeof Square }> = {
  vertical: { label: 'Vertikal', Icon: RectangleVertical },
  horizontal: { label: 'Horizontal', Icon: RectangleHorizontal },
  square: { label: 'Kotak', Icon: Square },
}

export function OrientationBadge({ orientation }: { orientation: Orientation }) {
  const { label, Icon } = meta[orientation]
  return (
    <span className="text-muted-foreground inline-flex h-6 items-center gap-1 rounded-full border px-2 text-[13px]">
      <Icon aria-hidden className="size-3.5" />
      {label}
    </span>
  )
}
