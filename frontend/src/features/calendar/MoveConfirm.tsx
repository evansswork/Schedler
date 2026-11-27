import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { formatWIB } from '@/lib/format'

type Props = { pending: { at: string } | null; onCancel: () => void; onConfirm: () => void }

/** Asked before moving a post that Buffer already holds. */
export function MoveConfirm({ pending, onCancel, onConfirm }: Props) {
  return (
    <Dialog open={pending !== null} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Pindahkan jadwal di Buffer juga?</DialogTitle>
          <DialogDescription>
            {pending &&
              `Post ini sudah dikirim ke Buffer. Jadwal di Buffer ikut diubah ke ${formatWIB(pending.at)}.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" size="lg" onClick={onCancel}>
            Batal
          </Button>
          <Button size="lg" onClick={onConfirm}>
            Pindahkan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
