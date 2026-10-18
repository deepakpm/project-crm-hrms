import { useEffect, useMemo, useState } from 'react'
import { Plus, CalendarOff } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '@/api'
import * as peopleApi from '@/peopleApi'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
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
  cancelled: 'secondary',
}

const REASON_CODES: { value: peopleApi.ReasonCode; label: string }[] = [
  { value: 'personal', label: 'Personal' },
  { value: 'medical', label: 'Medical' },
  { value: 'family', label: 'Family' },
  { value: 'bereavement', label: 'Bereavement' },
  { value: 'travel', label: 'Travel' },
  { value: 'other', label: 'Other' },
]

const ACCRUAL_FREQUENCIES: { value: peopleApi.AccrualFrequency; label: string }[] = [
  { value: 'none', label: 'Upfront (full amount on allocation)' },
  { value: 'monthly', label: 'Accrues monthly' },
  { value: 'yearly', label: 'Accrues yearly' },
]

function LeaveSetup({ leaveTypes, onChanged }: { leaveTypes: peopleApi.LeaveType[]; onChanged: () => void }) {
  const [open, setOpen] = useState(false)
  const [typeName, setTypeName] = useState('')
  const [accrualFrequency, setAccrualFrequency] = useState<peopleApi.AccrualFrequency>('none')
  const [policyName, setPolicyName] = useState('Standard')
  const [annualDays, setAnnualDays] = useState('12')

  async function createType(e: React.FormEvent) {
    e.preventDefault()
    try {
      await peopleApi.createLeaveType({
        name: typeName,
        exclude_weekends: true,
        exclude_holidays: true,
        accrual_frequency: accrualFrequency,
      })
      toast.success('Leave type created')
      setTypeName('')
      setAccrualFrequency('none')
      onChanged()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  async function createPolicy(e: React.FormEvent) {
    e.preventDefault()
    const leaveType = leaveTypes[0]
    if (!leaveType) {
      toast.error('Create a leave type first')
      return
    }
    try {
      await peopleApi.createLeavePolicy({
        name: policyName,
        types: [{ leave_type_id: leaveType.id, annual_days: Number(annualDays) }],
      })
      toast.success('Policy created')
      setOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Setup</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-end gap-6">
        <form onSubmit={createType} className="flex items-end gap-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lt_name">New leave type</Label>
            <Input
              id="lt_name"
              value={typeName}
              onChange={(e) => setTypeName(e.target.value)}
              placeholder="e.g. Casual Leave, Bereavement Leave"
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Crediting</Label>
            <Select
              value={accrualFrequency}
              onValueChange={(v) => setAccrualFrequency(v as peopleApi.AccrualFrequency)}
            >
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ACCRUAL_FREQUENCIES.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" variant="secondary">
            Add type
          </Button>
        </form>

        <Dialog open={open} onOpenChange={setOpen}>
          <Button variant="secondary" onClick={() => setOpen(true)}>
            New policy
          </Button>
          <DialogContent>
            <form onSubmit={createPolicy}>
              <DialogHeader>
                <DialogTitle>New leave policy</DialogTitle>
              </DialogHeader>
              <div className="flex flex-col gap-4 py-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="p_name">Policy name</Label>
                  <Input id="p_name" value={policyName} onChange={(e) => setPolicyName(e.target.value)} required />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="p_days">Annual days ({leaveTypes[0]?.name ?? 'no leave type yet'})</Label>
                  <Input
                    id="p_days"
                    type="number"
                    min="0.5"
                    step="0.5"
                    value={annualDays}
                    onChange={(e) => setAnnualDays(e.target.value)}
                    required
                  />
                </div>
              </div>
              <DialogFooter>
                <DialogClose asChild>
                  <Button type="button" variant="secondary">
                    Cancel
                  </Button>
                </DialogClose>
                <Button type="submit" disabled={leaveTypes.length === 0}>
                  Create policy
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}

function ApplyPolicyDialog({
  employees,
  onApplied,
}: {
  employees: peopleApi.EmployeeListItem[]
  onApplied: () => void
}) {
  const [open, setOpen] = useState(false)
  const [policyId, setPolicyId] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [financialYear, setFinancialYear] = useState('2026-27')
  const [policies, setPolicies] = useState<peopleApi.LeavePolicy[]>([])

  useEffect(() => {
    if (open) peopleApi.listLeavePolicies().then(setPolicies)
  }, [open])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await peopleApi.applyLeavePolicy(policyId, employeeId, financialYear)
      toast.success('Policy applied')
      setOpen(false)
      onApplied()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Allocate leave
      </Button>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Allocate leave from a policy</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-1.5">
              <Label>Employee</Label>
              <Select value={employeeId} onValueChange={setEmployeeId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select employee" />
                </SelectTrigger>
                <SelectContent>
                  {employees.map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Policy</Label>
              <Select value={policyId} onValueChange={setPolicyId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select policy" />
                </SelectTrigger>
                <SelectContent>
                  {policies.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fy">Financial year</Label>
              <Input id="fy" value={financialYear} onChange={(e) => setFinancialYear(e.target.value)} required />
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="secondary">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!employeeId || !policyId}>
              Allocate
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function NewApplicationForm({
  employeeId,
  leaveTypes,
  onCreated,
}: {
  employeeId: string
  leaveTypes: peopleApi.LeaveType[]
  onCreated: () => void
}) {
  const [open, setOpen] = useState(false)
  const [leaveTypeId, setLeaveTypeId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [halfDay, setHalfDay] = useState(false)
  const [reasonCode, setReasonCode] = useState<peopleApi.ReasonCode | ''>('')
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function toggleHalfDay(checked: boolean) {
    setHalfDay(checked)
    if (checked && startDate) setEndDate(startDate) // half day only ever covers a single date
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const application = await peopleApi.createLeaveApplication({
        employee_id: employeeId,
        leave_type_id: leaveTypeId,
        start_date: startDate,
        end_date: halfDay ? startDate : endDate,
        half_day: halfDay,
        reason_code: reasonCode || null,
        comment: comment || null,
      })
      await peopleApi.submitLeaveApplication(application.id)
      toast.success('Leave application submitted')
      setOpen(false)
      setStartDate('')
      setEndDate('')
      setHalfDay(false)
      setReasonCode('')
      setComment('')
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
        Apply for leave
      </Button>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Apply for leave</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-1.5">
              <Label>Leave type</Label>
              <Select value={leaveTypeId} onValueChange={setLeaveTypeId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select leave type" />
                </SelectTrigger>
                <SelectContent>
                  {leaveTypes.map((lt) => (
                    <SelectItem key={lt.id} value={lt.id}>
                      {lt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-4">
              <div className="flex flex-1 flex-col gap-1.5">
                <Label htmlFor="start">Start date</Label>
                <Input
                  id="start"
                  type="date"
                  value={startDate}
                  onChange={(e) => {
                    setStartDate(e.target.value)
                    if (halfDay) setEndDate(e.target.value)
                  }}
                  required
                />
              </div>
              <div className="flex flex-1 flex-col gap-1.5">
                <Label htmlFor="end">End date</Label>
                <Input
                  id="end"
                  type="date"
                  value={halfDay ? startDate : endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  disabled={halfDay}
                  required
                />
              </div>
            </div>
            <label htmlFor="half_day" className="flex items-center gap-2 text-sm">
              <input
                id="half_day"
                type="checkbox"
                className="size-4 rounded border-input accent-primary"
                checked={halfDay}
                onChange={(e) => toggleHalfDay(e.target.checked)}
              />
              Half day
            </label>
            <div className="flex flex-col gap-1.5">
              <Label>Reason (optional)</Label>
              <Select value={reasonCode} onValueChange={(v) => setReasonCode(v as peopleApi.ReasonCode)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a reason" />
                </SelectTrigger>
                <SelectContent>
                  {REASON_CODES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="comment">Comment (optional)</Label>
              <Textarea id="comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={2} />
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
            <Button type="submit" disabled={busy || !leaveTypeId}>
              {busy ? 'Submitting…' : 'Submit'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AccrualsCard({
  employees,
  leaveTypes,
  onAccrued,
}: {
  employees: peopleApi.EmployeeListItem[]
  leaveTypes: peopleApi.LeaveType[]
  onAccrued: () => void
}) {
  const [employeeId, setEmployeeId] = useState('')
  const [allocations, setAllocations] = useState<peopleApi.LeaveAllocation[]>([])
  const accruingTypeIds = new Set(
    leaveTypes.filter((lt) => lt.accrual_frequency !== 'none').map((lt) => lt.id),
  )

  const reload = () => {
    if (employeeId) peopleApi.listLeaveAllocations(employeeId).then(setAllocations)
  }
  useEffect(reload, [employeeId])

  const accruing = allocations.filter((a) => accruingTypeIds.has(a.leave_type_id))

  async function runAccrual(allocationId: string) {
    try {
      await peopleApi.accrueLeaveAllocation(allocationId)
      toast.success('Accrual credited')
      reload()
      onAccrued()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  if (accruingTypeIds.size === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Accruals</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Select value={employeeId} onValueChange={setEmployeeId}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Select employee" />
          </SelectTrigger>
          <SelectContent>
            {employees.map((e) => (
              <SelectItem key={e.id} value={e.id}>
                {e.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {employeeId && accruing.length === 0 && (
          <p className="text-sm text-muted-foreground">No accruing allocations for this employee.</p>
        )}
        {accruing.map((a) => (
          <div key={a.id} className="flex items-center justify-between gap-4 text-sm">
            <span>
              {leaveTypes.find((lt) => lt.id === a.leave_type_id)?.name} -- cap{' '}
              {Number(a.allocated_days)}d, last accrued {a.last_accrued_on ?? 'never'}
            </span>
            <Button size="sm" variant="secondary" onClick={() => runAccrual(a.id)}>
              Run accrual
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function PeopleLeavePage() {
  usePageTitle('Leave')
  const [employees, setEmployees] = useState<peopleApi.EmployeeListItem[]>([])
  const [leaveTypes, setLeaveTypes] = useState<peopleApi.LeaveType[]>([])
  const [applications, setApplications] = useState<peopleApi.LeaveApplication[]>([])
  const [balances, setBalances] = useState<peopleApi.LeaveBalance[]>([])
  const canManage = ['owner', 'hr'].includes(api.currentUserRole() ?? '')

  const reload = () => {
    peopleApi.listEmployees().then(setEmployees)
    peopleApi.listLeaveTypes().then(setLeaveTypes)
    peopleApi.listLeaveApplications().then(setApplications)
  }
  useEffect(reload, [])

  const myEmployee = useMemo(
    () => employees.find((e) => e.user_id === api.currentUserId()),
    [employees],
  )

  const reloadBalances = () => {
    if (myEmployee) peopleApi.getLeaveBalances(myEmployee.id).then(setBalances)
  }
  useEffect(reloadBalances, [myEmployee])

  const employeeName = (id: string) => employees.find((e) => e.id === id)?.name ?? '—'
  const leaveTypeName = (id: string) => leaveTypes.find((lt) => lt.id === id)?.name ?? '—'

  const myApplications = applications.filter((a) => a.employee_id === myEmployee?.id)
  // owner/hr can approve their own request too (common for a solo founder who
  // is also the only employee) -- only exclude "my own" for everyone else.
  const pendingApprovals = applications.filter(
    (a) => a.status === 'submitted' && (canManage || a.employee_id !== myEmployee?.id),
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

  return (
    <>
      <PageHeader title="Leave" />
      <div className="space-y-6">
        {canManage && (
          <>
            <LeaveSetup leaveTypes={leaveTypes} onChanged={reload} />
            <AccrualsCard employees={employees} leaveTypes={leaveTypes} onAccrued={reloadBalances} />
            <div className="flex justify-end">
              <ApplyPolicyDialog employees={employees} onApplied={reload} />
            </div>
          </>
        )}

        <Tabs defaultValue="mine">
          <TabsList>
            <TabsTrigger value="mine">My leave</TabsTrigger>
            <TabsTrigger value="approvals">
              Approvals{pendingApprovals.length > 0 ? ` (${pendingApprovals.length})` : ''}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="mine" className="space-y-4">
            {!myEmployee ? (
              <EmptyState
                icon={CalendarOff}
                message="Your login isn't linked to an employee record yet -- ask HR to link it."
              />
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2">
                    {balances.map((b) => (
                      <Badge key={b.leave_type_id} variant="outline">
                        {leaveTypeName(b.leave_type_id)}: {Number(b.balance_days)}d
                      </Badge>
                    ))}
                  </div>
                  <NewApplicationForm employeeId={myEmployee.id} leaveTypes={leaveTypes} onCreated={reload} />
                </div>
                {myApplications.length === 0 ? (
                  <EmptyState icon={CalendarOff} message="No leave applications yet." />
                ) : (
                  <div className="rounded-lg border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Type</TableHead>
                          <TableHead>Dates</TableHead>
                          <TableHead className="text-right">Days</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {myApplications.map((a) => (
                          <TableRow key={a.id}>
                            <TableCell>{leaveTypeName(a.leave_type_id)}</TableCell>
                            <TableCell>
                              {a.start_date} – {a.end_date}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">{Number(a.days)}</TableCell>
                            <TableCell>
                              <Badge variant={STATUS_VARIANT[a.status]}>{a.status}</Badge>
                            </TableCell>
                            <TableCell>
                              {a.status === 'approved' && (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() =>
                                    act(peopleApi.cancelLeaveApplication, a.id, 'Leave cancelled')
                                  }
                                >
                                  Cancel
                                </Button>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </>
            )}
          </TabsContent>

          <TabsContent value="approvals">
            {pendingApprovals.length === 0 ? (
              <EmptyState icon={CalendarOff} message="Nothing waiting for your approval." />
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Employee</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Dates</TableHead>
                      <TableHead className="text-right">Days</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingApprovals.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell>{employeeName(a.employee_id)}</TableCell>
                        <TableCell>{leaveTypeName(a.leave_type_id)}</TableCell>
                        <TableCell>
                          {a.start_date} – {a.end_date}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{Number(a.days)}</TableCell>
                        <TableCell className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => act(peopleApi.approveLeaveApplication, a.id, 'Approved')}
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => act(peopleApi.rejectLeaveApplication, a.id, 'Rejected')}
                          >
                            Reject
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
