import { useEffect, useMemo, useState } from 'react'
import { Users, Plus, Search } from 'lucide-react'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
  DrawerClose,
} from '@/components/ui/drawer'

function EmployeeForm({
  employees,
  users,
  onCreated,
}: {
  employees: peopleApi.EmployeeListItem[]
  users: api.User[]
  onCreated: () => void
}) {
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [workEmail, setWorkEmail] = useState('')
  const [joinDate, setJoinDate] = useState('')
  const [managerId, setManagerId] = useState('')
  const [userId, setUserId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const linkedUserIds = new Set(employees.map((e) => e.user_id).filter(Boolean))
  const availableUsers = users.filter((u) => !linkedUserIds.has(u.id))

  function reset() {
    setCode('')
    setName('')
    setWorkEmail('')
    setJoinDate('')
    setManagerId('')
    setUserId('')
    setError(null)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await peopleApi.createEmployee({
        code,
        name,
        work_email: workEmail,
        join_date: joinDate,
        manager_id: managerId || null,
        user_id: userId || null,
      })
      toast.success('Employee added')
      reset()
      setOpen(false)
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Drawer
      direction="right"
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (!v) reset()
      }}
    >
      <Button onClick={() => setOpen(true)}>
        <Plus className="size-4" />
        New employee
      </Button>
      <DrawerContent>
        <form onSubmit={submit} className="flex h-full flex-col">
          <DrawerHeader>
            <DrawerTitle>New employee</DrawerTitle>
            <DrawerDescription>Core HR record -- leave, attendance and expenses attach to this.</DrawerDescription>
          </DrawerHeader>
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_code">Employee code</Label>
              <Input id="e_code" value={code} onChange={(e) => setCode(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_name">Name</Label>
              <Input id="e_name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_email">Work email</Label>
              <Input
                id="e_email"
                type="email"
                value={workEmail}
                onChange={(e) => setWorkEmail(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_join">Join date</Label>
              <Input
                id="e_join"
                type="date"
                value={joinDate}
                onChange={(e) => setJoinDate(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Manager</Label>
              <Select value={managerId} onValueChange={setManagerId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="No manager" />
                </SelectTrigger>
                <SelectContent>
                  {employees.map((emp) => (
                    <SelectItem key={emp.id} value={emp.id}>
                      {emp.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Link to login</Label>
              <Select value={userId} onValueChange={setUserId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="No self-service login" />
                </SelectTrigger>
                <SelectContent>
                  {availableUsers.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.email} ({u.role})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Required for this person to use self-service leave/attendance/expense pages.
              </p>
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
          </div>
          <DrawerFooter className="flex-row justify-end">
            <DrawerClose asChild>
              <Button type="button" variant="secondary">
                Cancel
              </Button>
            </DrawerClose>
            <Button type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Add employee'}
            </Button>
          </DrawerFooter>
        </form>
      </DrawerContent>
    </Drawer>
  )
}

export function PeopleEmployeesPage() {
  usePageTitle('Employees')
  const [employees, setEmployees] = useState<peopleApi.EmployeeListItem[] | null>(null)
  const [users, setUsers] = useState<api.User[]>([])
  const [search, setSearch] = useState('')
  const canManage = ['owner', 'hr'].includes(api.currentUserRole() ?? '')

  const reload = () => {
    peopleApi.listEmployees().then(setEmployees)
  }
  useEffect(reload, [])
  useEffect(() => {
    if (canManage) api.listUsers().then(setUsers)
  }, [canManage])

  const filtered = useMemo(() => {
    if (!employees) return []
    const q = search.trim().toLowerCase()
    if (!q) return employees
    return employees.filter((e) => e.name.toLowerCase().includes(q) || e.code.toLowerCase().includes(q))
  }, [employees, search])

  const myUserId = api.currentUserId()

  return (
    <>
      <PageHeader title="Employees">
        {canManage && <EmployeeForm employees={employees ?? []} users={users} onCreated={reload} />}
      </PageHeader>

      {employees === null ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : employees.length === 0 ? (
        <EmptyState icon={Users} message="No employees yet. Add your first employee to get started." />
      ) : (
        <div className="rounded-lg border">
          <div className="border-b p-3">
            <div className="relative max-w-xs">
              <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" aria-hidden="true" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search employees…"
                className="pl-8"
              />
            </div>
          </div>
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-background">
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((emp) => (
                <TableRow key={emp.id}>
                  <TableCell className="font-medium">{emp.code}</TableCell>
                  <TableCell>{emp.name}</TableCell>
                  <TableCell>
                    <Badge variant={emp.status === 'active' ? 'success' : 'secondary'}>{emp.status}</Badge>
                  </TableCell>
                  <TableCell>{emp.user_id === myUserId && <Badge variant="outline">You</Badge>}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  )
}
