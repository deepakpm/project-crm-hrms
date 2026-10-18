import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '@/api'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { StateSelect } from '@/components/StateSelect'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

const ROLES: api.User['role'][] = ['owner', 'hr', 'manager', 'accountant', 'member']

function AddTeammateDialog({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<api.User['role']>('member')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.createTeammate({ email, password, role })
      toast.success('Teammate added')
      setOpen(false)
      setEmail('')
      setPassword('')
      onAdded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus className="size-4" />
        Add teammate
      </Button>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Add a teammate</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t_email">Email</Label>
              <Input id="t_email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t_password">Temporary password</Label>
              <Input
                id="t_password"
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Role</Label>
              <Select value={role} onValueChange={(v) => setRole(v as api.User['role'])}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
              {busy ? 'Adding…' : 'Add teammate'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function TeamCard() {
  const [users, setUsers] = useState<api.User[] | null>(null)
  const reload = () => {
    api.listUsers().then(setUsers)
  }
  useEffect(reload, [])

  return (
    <Card className="max-w-2xl">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Team</CardTitle>
          <CardDescription>Who can sign in to this workspace, and with what role.</CardDescription>
        </div>
        <AddTeammateDialog onAdded={reload} />
      </CardHeader>
      <CardContent>
        {users === null ? (
          <Skeleton className="h-9 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{u.role}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

export function SettingsPage() {
  usePageTitle('Settings')
  const [legalName, setLegalName] = useState('')
  const [gstin, setGstin] = useState('')
  const [stateCode, setStateCode] = useState('')
  const [address, setAddress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    api
      .getCompany()
      .then((c) => {
        setLegalName(c.legal_name)
        setGstin(c.gstin)
        setStateCode(c.state_code)
        setAddress(c.address)
      })
      .catch(() => {}) // no company profile set yet -- form just stays empty
      .finally(() => setLoaded(true))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.upsertCompany({ legal_name: legalName, gstin, state_code: stateCode, address })
      toast.success('Company profile saved')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader title="Settings" />
      <div className="space-y-6">
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Company profile</CardTitle>
          <CardDescription>
            Required before you can issue invoices -- your GSTIN and state decide whether an
            invoice charges CGST+SGST or IGST.
          </CardDescription>
        </CardHeader>
        {!loaded ? (
          <CardContent className="space-y-3">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </CardContent>
        ) : (
          <form onSubmit={submit}>
            <CardContent className="space-y-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="legal_name">Legal name</Label>
                <Input id="legal_name" value={legalName} onChange={(e) => setLegalName(e.target.value)} required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="gstin">GSTIN</Label>
                <Input
                  id="gstin"
                  value={gstin}
                  onChange={(e) => setGstin(e.target.value.toUpperCase())}
                  placeholder="27AAAAA0000A1Z5"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  15 characters: state code, PAN, entity code and a checksum.
                </p>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="state">State</Label>
                <StateSelect id="state" value={stateCode} onChange={setStateCode} />
                <p className="text-xs text-muted-foreground">
                  Compared to each customer&apos;s state to decide place of supply.
                </p>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="address">Address</Label>
                <Input id="address" value={address} onChange={(e) => setAddress(e.target.value)} required />
              </div>
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={saving || !stateCode}>
                {saving ? 'Saving…' : 'Save'}
              </Button>
            </CardFooter>
          </form>
        )}
      </Card>
      <TeamCard />
      </div>
    </>
  )
}
