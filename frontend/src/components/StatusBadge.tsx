import { Badge } from '@/components/ui/badge'
import type { Invoice } from '@/api'

const VARIANT: Record<Invoice['status'], 'secondary' | 'success' | 'destructive'> = {
  draft: 'secondary',
  issued: 'success',
  cancelled: 'destructive',
}

const LABEL: Record<Invoice['status'], string> = {
  draft: 'Draft',
  issued: 'Issued',
  cancelled: 'Cancelled',
}

export function StatusBadge({ status }: { status: Invoice['status'] }) {
  return <Badge variant={VARIANT[status]}>{LABEL[status]}</Badge>
}
