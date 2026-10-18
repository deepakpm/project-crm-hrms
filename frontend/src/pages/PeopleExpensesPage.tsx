import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, Receipt } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '@/api'
import * as peopleApi from '@/peopleApi'
import { rupees } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

const STATUS_VARIANT: Record<string, 'secondary' | 'success' | 'destructive' | 'warning'> = {
  draft: 'secondary',
  submitted: 'warning',
  approved: 'success',
  rejected: 'destructive',
}

type DraftLine = { description: string; amount: string; category: string }

function NewClaimDialog({ employeeId, onCreated }: { employeeId: string; onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [lines, setLines] = useState<DraftLine[]>([{ description: '', amount: '', category: 'other' }])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function updateLine(i: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const claim = await peopleApi.createExpenseClaim({
        employee_id: employeeId,
        lines: lines
          .filter((l) => l.description && Number(l.amount) > 0)
          .map((l) => ({
            description: l.description,
            amount_paise: Math.round(Number(l.amount) * 100),
            category: l.category,
          })),
      })
      await peopleApi.submitExpenseClaim(claim.id)
      toast.success('Expense claim submitted')
      setOpen(false)
      setLines([{ description: '', amount: '', category: 'other' }])
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button onClick={() => setOpen(true)}>
        <Plus className="size-4" />
        New expense claim
      </Button>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>New expense claim</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-4">
            {lines.map((line, i) => (
              <div key={i} className="flex items-end gap-2">
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label>Description</Label>
                  <Input
                    value={line.description}
                    onChange={(e) => updateLine(i, { description: e.target.value })}
                  />
                </div>
                <div className="flex w-28 flex-col gap-1.5">
                  <Label>Amount (₹)</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.amount}
                    onChange={(e) => updateLine(i, { amount: e.target.value })}
                  />
                </div>
                <div className="flex w-28 flex-col gap-1.5">
                  <Label>Category</Label>
                  <Input value={line.category} onChange={(e) => updateLine(i, { category: e.target.value })} />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => setLines((prev) => prev.filter((_, idx) => idx !== i))}
                  disabled={lines.length === 1}
                  aria-label="Remove line"
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setLines((prev) => [...prev, { description: '', amount: '', category: 'other' }])}
            >
              <Plus className="size-4" />
              Add line
            </Button>
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
              {busy ? 'Submitting…' : 'Submit claim'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ReimburseDialog({ claim, onDone }: { claim: peopleApi.ExpenseClaim; onDone: () => void }) {
  const [open, setOpen] = useState(false)
  const [amount, setAmount] = useState(String(claim.total_paise / 100))
  const [method, setMethod] = useState('bank_transfer')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await peopleApi.reimburseExpenseClaim(claim.id, Math.round(Number(amount) * 100), method)
      toast.success('Reimbursement recorded')
      setOpen(false)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        Reimburse
      </Button>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Record reimbursement</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="amt">Amount (₹)</Label>
              <Input
                id="amt"
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="method">Method</Label>
              <Input id="method" value={method} onChange={(e) => setMethod(e.target.value)} required />
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
              {busy ? 'Recording…' : 'Record'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function PeopleExpensesPage() {
  usePageTitle('Expenses')
  const [employees, setEmployees] = useState<peopleApi.EmployeeListItem[]>([])
  const [claims, setClaims] = useState<peopleApi.ExpenseClaim[]>([])
  const canReimburse = ['owner', 'hr', 'accountant'].includes(api.currentUserRole() ?? '')
  // Narrower than canReimburse: the backend's approval check is owner/hr/manager-of,
  // never accountant -- showing Approve to an accountant would just 403 on click.
  const canApproveOwn = ['owner', 'hr'].includes(api.currentUserRole() ?? '')

  const reload = () => {
    peopleApi.listEmployees().then(setEmployees)
    peopleApi.listExpenseClaims().then(setClaims)
  }
  useEffect(reload, [])

  const myEmployee = useMemo(
    () => employees.find((e) => e.user_id === api.currentUserId()),
    [employees],
  )
  const employeeName = (id: string) => employees.find((e) => e.id === id)?.name ?? '—'

  const myClaims = claims.filter((c) => c.employee_id === myEmployee?.id)
  // owner/hr can approve their own claim too (solo founder = only employee case).
  const pendingApprovals = claims.filter(
    (c) => c.status === 'submitted' && (canApproveOwn || c.employee_id !== myEmployee?.id),
  )
  const approvedForReimbursement = claims.filter(
    (c) => c.status === 'approved' && c.outstanding_paise > 0,
  )

  async function act(action: (id: string) => Promise<unknown>, id: string, message: string) {
    try {
      await action(id)
      toast.success(message)
      reload()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  function ClaimRow({ claim, showEmployee, children }: { claim: peopleApi.ExpenseClaim; showEmployee?: boolean; children?: React.ReactNode }) {
    return (
      <TableRow>
        {showEmployee && <TableCell>{employeeName(claim.employee_id)}</TableCell>}
        <TableCell>{claim.lines.map((l) => l.description).join(', ')}</TableCell>
        <TableCell className="text-right tabular-nums">{rupees(claim.total_paise)}</TableCell>
        <TableCell>
          {claim.status === 'approved' && claim.outstanding_paise === 0 ? (
            <Badge variant="secondary">reimbursed</Badge>
          ) : (
            <Badge variant={STATUS_VARIANT[claim.status]}>{claim.status}</Badge>
          )}
        </TableCell>
        <TableCell className="flex gap-2">{children}</TableCell>
      </TableRow>
    )
  }

  return (
    <>
      <PageHeader title="Expenses">{myEmployee && <NewClaimDialog employeeId={myEmployee.id} onCreated={reload} />}</PageHeader>

      <Tabs defaultValue="mine">
        <TabsList>
          <TabsTrigger value="mine">My claims</TabsTrigger>
          <TabsTrigger value="approvals">
            Approvals{pendingApprovals.length > 0 ? ` (${pendingApprovals.length})` : ''}
          </TabsTrigger>
          {canReimburse && <TabsTrigger value="reimburse">To reimburse</TabsTrigger>}
        </TabsList>

        <TabsContent value="mine">
          {myClaims.length === 0 ? (
            <EmptyState icon={Receipt} message="No expense claims yet." />
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Lines</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {myClaims.map((c) => (
                    <ClaimRow key={c.id} claim={c} />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="approvals">
          {pendingApprovals.length === 0 ? (
            <EmptyState icon={Receipt} message="Nothing waiting for your approval." />
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Employee</TableHead>
                    <TableHead>Lines</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingApprovals.map((c) => (
                    <ClaimRow key={c.id} claim={c} showEmployee>
                      <Button size="sm" onClick={() => act(peopleApi.approveExpenseClaim, c.id, 'Approved')}>
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => act(peopleApi.rejectExpenseClaim, c.id, 'Rejected')}
                      >
                        Reject
                      </Button>
                    </ClaimRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {canReimburse && (
          <TabsContent value="reimburse">
            {approvedForReimbursement.length === 0 ? (
              <EmptyState icon={Receipt} message="Nothing approved and waiting for reimbursement." />
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Employee</TableHead>
                      <TableHead>Lines</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {approvedForReimbursement.map((c) => (
                      <ClaimRow key={c.id} claim={c} showEmployee>
                        <ReimburseDialog claim={c} onDone={reload} />
                      </ClaimRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
        )}
      </Tabs>
    </>
  )
}
