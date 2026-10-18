import { useEffect, useMemo, useState } from 'react'
import { Users, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '@/api'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { StateSelect } from '@/components/StateSelect'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
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

function CustomerForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [gstin, setGstin] = useState('')
  const [stateCode, setStateCode] = useState('')
  const [billingAddress, setBillingAddress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function reset() {
    setName('')
    setGstin('')
    setStateCode('')
    setBillingAddress('')
    setError(null)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.createCustomer({
        name,
        gstin: gstin || null,
        state_code: stateCode,
        billing_address: billingAddress,
      })
      toast.success('Customer added')
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
        New customer
      </Button>
      <DrawerContent>
        <form onSubmit={submit} className="flex h-full flex-col">
          <DrawerHeader>
            <DrawerTitle>New customer</DrawerTitle>
            <DrawerDescription>Used as the bill-to party on quotes and invoices.</DrawerDescription>
          </DrawerHeader>
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c_name">Name</Label>
              <Input id="c_name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c_gstin">GSTIN</Label>
              <Input
                id="c_gstin"
                value={gstin}
                onChange={(e) => setGstin(e.target.value.toUpperCase())}
                placeholder="Leave blank for a B2C customer"
              />
              <p className="text-xs text-muted-foreground">
                No GSTIN means this is a consumer, not a GST-registered business.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c_state">State</Label>
              <StateSelect id="c_state" value={stateCode} onChange={setStateCode} />
              <p className="text-xs text-muted-foreground">
                Compared to your company&apos;s state to decide CGST+SGST vs IGST.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c_address">Billing address</Label>
              <Input
                id="c_address"
                value={billingAddress}
                onChange={(e) => setBillingAddress(e.target.value)}
                required
              />
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
            <Button type="submit" disabled={busy || !stateCode}>
              {busy ? 'Saving…' : 'Add customer'}
            </Button>
          </DrawerFooter>
        </form>
      </DrawerContent>
    </Drawer>
  )
}

export function CustomersPage() {
  usePageTitle('Customers')
  const [customers, setCustomers] = useState<api.Customer[] | null>(null)
  const [search, setSearch] = useState('')

  const reload = () => {
    api.listCustomers().then(setCustomers)
  }
  useEffect(reload, [])

  const filtered = useMemo(() => {
    if (!customers) return []
    const q = search.trim().toLowerCase()
    if (!q) return customers
    return customers.filter((c) => c.name.toLowerCase().includes(q))
  }, [customers, search])

  return (
    <>
      <PageHeader title="Customers">
        <CustomerForm onCreated={reload} />
      </PageHeader>

      {customers === null ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : customers.length === 0 ? (
        <EmptyState icon={Users} message="No customers yet. Add your first customer to start billing them." />
      ) : (
        <div className="rounded-lg border">
          <div className="border-b p-3">
            <div className="relative max-w-xs">
              <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" aria-hidden="true" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search customers…"
                className="pl-8"
              />
            </div>
          </div>
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-background">
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>GSTIN</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Billing address</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell>
                    {c.gstin ?? <Badge variant="outline">B2C</Badge>}
                  </TableCell>
                  <TableCell>{c.state_code}</TableCell>
                  <TableCell className="text-muted-foreground">{c.billing_address}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  )
}
