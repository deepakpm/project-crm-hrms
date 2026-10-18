import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as api from '@/api'
import { rupees } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { LayoutDashboard } from 'lucide-react'

const BUCKETS = ['0-30', '31-60', '61-90', '90+'] as const
const BUCKET_COLOR: Record<(typeof BUCKETS)[number], string> = {
  '0-30': 'bg-success',
  '31-60': 'bg-warning',
  '61-90': 'bg-warning',
  '90+': 'bg-destructive',
}

export function DashboardPage() {
  usePageTitle('Dashboard')
  const navigate = useNavigate()
  const [ageing, setAgeing] = useState<api.AgeingRow[] | null>(null)
  const [invoices, setInvoices] = useState<api.Invoice[] | null>(null)
  const [now] = useState(() => new Date())

  useEffect(() => {
    api.getReceivablesAgeing().then(setAgeing)
    api.listInvoices().then(setInvoices)
  }, [])

  const outstanding = useMemo(
    () => ageing?.reduce((sum, r) => sum + r.outstanding_paise, 0) ?? 0,
    [ageing],
  )
  const overdue = useMemo(
    () => ageing?.filter((r) => r.bucket !== '0-30').reduce((sum, r) => sum + r.outstanding_paise, 0) ?? 0,
    [ageing],
  )
  const issuedThisMonth = useMemo(() => {
    if (!invoices) return 0
    return invoices.filter((inv) => {
      if (!inv.issued_at) return false
      const d = new Date(inv.issued_at)
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()
    }).length
  }, [invoices, now])

  const bucketTotals = useMemo(() => {
    const totals = Object.fromEntries(BUCKETS.map((b) => [b, 0])) as Record<(typeof BUCKETS)[number], number>
    for (const r of ageing ?? []) totals[r.bucket as (typeof BUCKETS)[number]] += r.outstanding_paise
    return totals
  }, [ageing])

  const mostOverdue = useMemo(
    () => [...(ageing ?? [])].sort((a, b) => b.days_overdue - a.days_overdue).slice(0, 5),
    [ageing],
  )

  const loading = ageing === null || invoices === null

  return (
    <>
      <PageHeader title="Dashboard" />
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : invoices.length === 0 ? (
        <EmptyState
          icon={LayoutDashboard}
          message="Nothing to show yet. Issue your first invoice to see numbers here."
          actionLabel="New invoice"
          onAction={() => navigate('/invoices/new')}
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-normal text-muted-foreground">
                  Receivables outstanding
                </CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold tabular-nums">{rupees(outstanding)}</CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-normal text-muted-foreground">Overdue</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold tabular-nums text-warning">
                {rupees(overdue)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-normal text-muted-foreground">Invoices issued (MTD)</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold tabular-nums">{issuedThisMonth}</CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Receivables ageing</CardTitle>
            </CardHeader>
            <CardContent>
              {outstanding === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing outstanding.</p>
              ) : (
                <>
                  <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
                    {BUCKETS.map((b) =>
                      bucketTotals[b] > 0 ? (
                        <div
                          key={b}
                          className={BUCKET_COLOR[b]}
                          style={{ width: `${(bucketTotals[b] / outstanding) * 100}%` }}
                          title={`${b} days: ${rupees(bucketTotals[b])}`}
                        />
                      ) : null,
                    )}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                    {BUCKETS.map((b) => (
                      <span key={b} className="flex items-center gap-1.5 text-muted-foreground">
                        <span className={`size-2 rounded-full ${BUCKET_COLOR[b]}`} aria-hidden="true" />
                        {b} days: {rupees(bucketTotals[b])}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {mostOverdue.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Most overdue</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {mostOverdue.map((r) => (
                  <button
                    key={r.invoice_id}
                    onClick={() => navigate(`/invoices/${r.invoice_id}`)}
                    className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                  >
                    <span>
                      {r.financial_year}/{r.number} &middot; {r.customer_name}
                    </span>
                    <span className="tabular-nums text-muted-foreground">
                      {r.days_overdue}d &middot; {rupees(r.outstanding_paise)}
                    </span>
                  </button>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </>
  )
}
