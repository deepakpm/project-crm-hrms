import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Plus, Search, MoreHorizontal, Download, Wallet } from 'lucide-react'
import * as api from '@/api'
import { rupees, formatDate } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function InvoicesListPage() {
  usePageTitle('Invoices')
  const navigate = useNavigate()
  const [invoices, setInvoices] = useState<api.Invoice[] | null>(null)
  const [customers, setCustomers] = useState<api.Customer[]>([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.listInvoices().then(setInvoices)
    api.listCustomers().then(setCustomers)
  }, [])

  const customerNames = useMemo(() => new Map(customers.map((c) => [c.id, c.name])), [customers])
  const customerName = (id: string) => customerNames.get(id) ?? '—'

  const filtered = useMemo(() => {
    if (!invoices) return []
    const q = search.trim().toLowerCase()
    if (!q) return invoices
    return invoices.filter((inv) => {
      const number = inv.number ? `${inv.financial_year}/${inv.number}` : 'draft'
      const name = customerNames.get(inv.customer_id) ?? ''
      return number.toLowerCase().includes(q) || name.toLowerCase().includes(q)
    })
  }, [invoices, customerNames, search])

  return (
    <>
      <PageHeader title="Invoices">
        <Button onClick={() => navigate('/invoices/new')}>
          <Plus className="size-4" />
          New invoice
        </Button>
      </PageHeader>

      {invoices === null ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : invoices.length === 0 ? (
        <EmptyState
          icon={FileText}
          message="No invoices yet. Create your first invoice to start billing."
          actionLabel="New invoice"
          onAction={() => navigate('/invoices/new')}
        />
      ) : (
        <div className="rounded-lg border">
          <div className="border-b p-3">
            <div className="relative max-w-xs">
              <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" aria-hidden="true" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search invoices…"
                className="pl-8"
              />
            </div>
          </div>
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-background">
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((inv) => (
                <TableRow
                  key={inv.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/invoices/${inv.id}`)}
                >
                  <TableCell className="font-medium">
                    {inv.number ? `${inv.financial_year}/${inv.number}` : 'Draft'}
                  </TableCell>
                  <TableCell>{customerName(inv.customer_id)}</TableCell>
                  <TableCell>
                    <StatusBadge status={inv.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {inv.issued_at ? formatDate(inv.issued_at) : formatDate(inv.created_at)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {rupees(inv.grand_total_paise)}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {inv.status === 'issued' && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" aria-label="Row actions">
                            <MoreHorizontal className="size-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => api.downloadInvoicePdf(inv)}>
                            <Download className="size-4" />
                            Download PDF
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => navigate(`/invoices/${inv.id}`)}>
                            <Wallet className="size-4" />
                            Record payment
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  )
}
