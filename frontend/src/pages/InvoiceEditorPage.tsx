import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2, Download, Wallet } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '@/api'
import { rupees, formatDate } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

type DraftLine = { item_id: string; quantity: string }

function SummaryCard({
  totals,
  footer,
}: {
  totals: {
    place_of_supply_state_code?: string
    subtotal_paise: number
    cgst_paise: number
    sgst_paise: number
    igst_paise: number
    grand_total_paise: number
  } | null
  footer: React.ReactNode
}) {
  return (
    <Card className="sticky top-6 h-fit">
      <CardHeader>
        <CardTitle>Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {!totals ? (
          <p className="text-muted-foreground">Add a customer and at least one line to see totals.</p>
        ) : (
          <>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="tabular-nums">{rupees(totals.subtotal_paise)}</span>
            </div>
            {totals.cgst_paise > 0 && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">CGST</span>
                <span className="tabular-nums">{rupees(totals.cgst_paise)}</span>
              </div>
            )}
            {totals.sgst_paise > 0 && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">SGST</span>
                <span className="tabular-nums">{rupees(totals.sgst_paise)}</span>
              </div>
            )}
            {totals.igst_paise > 0 && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">IGST</span>
                <span className="tabular-nums">{rupees(totals.igst_paise)}</span>
              </div>
            )}
            <div className="flex justify-between border-t pt-2 text-base font-semibold">
              <span>Total</span>
              <span className="tabular-nums">{rupees(totals.grand_total_paise)}</span>
            </div>
          </>
        )}
      </CardContent>
      <CardFooter className="flex flex-col gap-2">{footer}</CardFooter>
    </Card>
  )
}

function NewInvoiceEditor() {
  usePageTitle('New invoice')
  const navigate = useNavigate()
  const [customers, setCustomers] = useState<api.Customer[]>([])
  const [items, setItems] = useState<api.Item[]>([])
  const [customerId, setCustomerId] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([{ item_id: '', quantity: '1' }])
  const [preview, setPreview] = useState<api.InvoicePreview | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listCustomers().then(setCustomers)
    api.listItems().then(setItems)
  }, [])

  const validLines = useMemo(
    () =>
      lines
        .filter((l) => l.item_id && Number(l.quantity) > 0)
        .map((l) => ({ item_id: l.item_id, quantity: Number(l.quantity) })),
    [lines],
  )

  const canPreview = Boolean(customerId) && validLines.length > 0

  // Live totals from the same GST calc the backend uses on save -- never
  // duplicated in the browser. Debounced so every keystroke doesn't fire a call.
  useEffect(() => {
    if (!canPreview) return
    const handle = setTimeout(() => {
      api.previewInvoice({ customer_id: customerId, lines: validLines }).then(setPreview, () => setPreview(null))
    }, 300)
    return () => clearTimeout(handle)
  }, [canPreview, customerId, validLines])

  function updateLine(i: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }

  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i))
  }

  async function saveDraft() {
    setError(null)
    setSaving(true)
    try {
      const invoice = await api.createInvoice({ customer_id: customerId, lines: validLines })
      toast.success('Draft saved')
      navigate(`/invoices/${invoice.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader title="New invoice" />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="customer">Customer</Label>
              <Select value={customerId} onValueChange={setCustomerId}>
                <SelectTrigger id="customer" className="w-full max-w-sm">
                  <SelectValue placeholder="Select a customer" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {customers.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No customers yet -- add one on the Customers page first.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Line items</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {lines.map((line, i) => {
              const item = items.find((it) => it.id === line.item_id)
              const lineTotal =
                item && Number(line.quantity) > 0 ? item.unit_price_paise * Number(line.quantity) : null
              return (
                <div key={i} className="flex flex-wrap items-end gap-3 rounded-md border p-3">
                  <div className="flex min-w-48 flex-1 flex-col gap-1.5">
                    <Label>Item</Label>
                    <Select value={line.item_id} onValueChange={(v) => updateLine(i, { item_id: v })}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select an item" />
                      </SelectTrigger>
                      <SelectContent>
                        {items.map((it) => (
                          <SelectItem key={it.id} value={it.id}>
                            {it.name} ({it.gst_rate_bps / 100}%)
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex w-24 flex-col gap-1.5">
                    <Label>Qty</Label>
                    <Input
                      type="number"
                      min="1"
                      value={line.quantity}
                      onChange={(e) => updateLine(i, { quantity: e.target.value })}
                    />
                  </div>
                  <div className="flex w-28 flex-col gap-1.5">
                    <Label>Line total</Label>
                    <p className="flex h-9 items-center text-sm tabular-nums text-muted-foreground">
                      {lineTotal !== null ? rupees(lineTotal) : '—'}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeLine(i)}
                    disabled={lines.length === 1}
                    aria-label="Remove line"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              )
            })}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setLines((prev) => [...prev, { item_id: '', quantity: '1' }])}
            >
              <Plus className="size-4" />
              Add line
            </Button>
          </CardContent>
        </Card>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>

      <SummaryCard
        totals={canPreview ? preview : null}
        footer={
          <Button
            className="w-full"
            disabled={saving || !customerId || validLines.length === 0}
            onClick={saveDraft}
          >
            {saving ? 'Saving…' : 'Save draft'}
          </Button>
        }
      />
      </div>
    </>
  )
}

function IssueDialog({ invoice, onIssued }: { invoice: api.Invoice; onIssued: () => void }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  async function confirm() {
    setBusy(true)
    try {
      await api.issueInvoice(invoice.id)
      toast.success('Invoice issued')
      setOpen(false)
      onIssued()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not issue invoice')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button onClick={() => setOpen(true)}>Issue invoice</Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Issue this invoice?</DialogTitle>
          <DialogDescription>
            This posts a journal entry to your ledger and assigns a permanent invoice number. Once
            issued, the invoice becomes read-only and can only be reversed by cancelling it.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="secondary">Cancel</Button>
          </DialogClose>
          <Button onClick={confirm} disabled={busy}>
            {busy ? 'Issuing…' : 'Issue invoice'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function CancelDialog({ invoice, onCancelled }: { invoice: api.Invoice; onCancelled: () => void }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  async function confirm() {
    setBusy(true)
    try {
      await api.cancelInvoice(invoice.id)
      toast.success('Invoice cancelled')
      setOpen(false)
      onCancelled()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not cancel invoice')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="destructive" onClick={() => setOpen(true)}>
        Cancel invoice
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancel this invoice?</DialogTitle>
          <DialogDescription>
            This reverses the original ledger entry exactly. The invoice number stays assigned but the
            invoice can no longer be paid. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="secondary">Keep invoice</Button>
          </DialogClose>
          <Button variant="destructive" onClick={confirm} disabled={busy}>
            {busy ? 'Cancelling…' : 'Cancel invoice'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function RecordPaymentDialog({ invoice, onRecorded }: { invoice: api.Invoice; onRecorded: () => void }) {
  const [open, setOpen] = useState(false)
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('bank_transfer')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.createPayment({
        invoice_id: invoice.id,
        amount_paise: Math.round(Number(amount) * 100),
        method,
      })
      toast.success('Payment recorded')
      setOpen(false)
      setAmount('')
      onRecorded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <Wallet className="size-4" />
        Record payment
      </Button>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Record a payment</DialogTitle>
            <DialogDescription>
              Against invoice {invoice.financial_year}/{invoice.number}. Partial payments are fine.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pay_amount">Amount (₹)</Label>
              <Input
                id="pay_amount"
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pay_method">Method</Label>
              <Input id="pay_method" value={method} onChange={(e) => setMethod(e.target.value)} required />
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="secondary">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={busy}>
              {busy ? 'Recording…' : 'Record payment'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ExistingInvoiceEditor({ invoiceId }: { invoiceId: string }) {
  const [invoice, setInvoice] = useState<api.Invoice | null>(null)
  const [customer, setCustomer] = useState<api.Customer | null>(null)

  const reload = () => {
    api.getInvoice(invoiceId).then(setInvoice)
  }
  useEffect(reload, [invoiceId])

  useEffect(() => {
    if (!invoice) return
    api.listCustomers().then((all) => setCustomer(all.find((c) => c.id === invoice.customer_id) ?? null))
  }, [invoice])

  usePageTitle(invoice ? (invoice.number ? `Invoice ${invoice.financial_year}/${invoice.number}` : 'Draft invoice') : 'Invoice')

  if (!invoice) {
    return (
      <>
        <PageHeader title="Invoice" />
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader title={invoice.number ? `Invoice ${invoice.financial_year}/${invoice.number}` : 'Draft invoice'}>
        <StatusBadge status={invoice.status} />
      </PageHeader>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <Card>
          <CardContent className="space-y-1 pt-6 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Customer</span>
              <span>{customer?.name ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Place of supply</span>
              <span>{invoice.place_of_supply_state_code}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Created</span>
              <span>{formatDate(invoice.created_at)}</span>
            </div>
            {invoice.issued_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Issued</span>
                <span>{formatDate(invoice.issued_at)}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Line items</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead>HSN/SAC</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Rate</TableHead>
                  <TableHead className="text-right">Taxable</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoice.lines.map((line, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{line.description}</TableCell>
                    <TableCell>{line.hsn_sac}</TableCell>
                    <TableCell className="text-right tabular-nums">{line.quantity}</TableCell>
                    <TableCell className="text-right tabular-nums">{rupees(line.unit_price_paise)}</TableCell>
                    <TableCell className="text-right tabular-nums">{rupees(line.taxable_paise)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <SummaryCard
        totals={invoice}
        footer={
          <>
            {invoice.status === 'draft' && <IssueDialog invoice={invoice} onIssued={reload} />}
            {invoice.status === 'issued' && (
              <>
                <Button className="w-full" variant="secondary" onClick={() => api.downloadInvoicePdf(invoice)}>
                  <Download className="size-4" />
                  Download PDF
                </Button>
                <RecordPaymentDialog invoice={invoice} onRecorded={reload} />
                <CancelDialog invoice={invoice} onCancelled={reload} />
              </>
            )}
            {invoice.status === 'cancelled' && (
              <p className="text-center text-sm text-muted-foreground">This invoice is cancelled.</p>
            )}
          </>
        }
      />
      </div>
    </>
  )
}

export function InvoiceEditorPage() {
  const { invoiceId } = useParams()
  return invoiceId ? <ExistingInvoiceEditor invoiceId={invoiceId} /> : <NewInvoiceEditor />
}

