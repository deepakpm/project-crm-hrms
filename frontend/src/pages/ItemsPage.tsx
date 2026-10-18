import { useEffect, useMemo, useState } from 'react'
import { Package, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '@/api'
import { rupees } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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

function ItemForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [hsnSac, setHsnSac] = useState('')
  const [unit, setUnit] = useState('unit')
  const [unitPrice, setUnitPrice] = useState('')
  const [gstRate, setGstRate] = useState('18')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function reset() {
    setName('')
    setHsnSac('')
    setUnit('unit')
    setUnitPrice('')
    setGstRate('18')
    setError(null)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.createItem({
        name,
        hsn_sac: hsnSac,
        unit,
        unit_price_paise: Math.round(Number(unitPrice) * 100),
        gst_rate_bps: Math.round(Number(gstRate) * 100),
      })
      toast.success('Item added')
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
        New item
      </Button>
      <DrawerContent>
        <form onSubmit={submit} className="flex h-full flex-col">
          <DrawerHeader>
            <DrawerTitle>New item</DrawerTitle>
            <DrawerDescription>A product or service you bill customers for.</DrawerDescription>
          </DrawerHeader>
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="i_name">Name</Label>
              <Input id="i_name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="i_hsn">HSN/SAC code</Label>
              <Input id="i_hsn" value={hsnSac} onChange={(e) => setHsnSac(e.target.value)} required />
              <p className="text-xs text-muted-foreground">
                HSN for goods, SAC for services -- required on every GST invoice line.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="i_unit">Unit</Label>
              <Input id="i_unit" value={unit} onChange={(e) => setUnit(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="i_price">Unit price (₹)</Label>
              <Input
                id="i_price"
                type="number"
                min="0"
                step="0.01"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="i_gst">GST rate (%)</Label>
              <Input
                id="i_gst"
                type="number"
                min="0"
                max="28"
                step="0.01"
                value={gstRate}
                onChange={(e) => setGstRate(e.target.value)}
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
            <Button type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Add item'}
            </Button>
          </DrawerFooter>
        </form>
      </DrawerContent>
    </Drawer>
  )
}

export function ItemsPage() {
  usePageTitle('Items')
  const [items, setItems] = useState<api.Item[] | null>(null)
  const [search, setSearch] = useState('')

  const reload = () => {
    api.listItems().then(setItems)
  }
  useEffect(reload, [])

  const filtered = useMemo(() => {
    if (!items) return []
    const q = search.trim().toLowerCase()
    if (!q) return items
    return items.filter((i) => i.name.toLowerCase().includes(q))
  }, [items, search])

  return (
    <>
      <PageHeader title="Items">
        <ItemForm onCreated={reload} />
      </PageHeader>

      {items === null ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={Package} message="No items yet. Add what you sell to start building invoices." />
      ) : (
        <div className="rounded-lg border">
          <div className="border-b p-3">
            <div className="relative max-w-xs">
              <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" aria-hidden="true" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search items…"
                className="pl-8"
              />
            </div>
          </div>
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-background">
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>HSN/SAC</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">GST rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((i) => (
                <TableRow key={i.id}>
                  <TableCell className="font-medium">{i.name}</TableCell>
                  <TableCell>{i.hsn_sac}</TableCell>
                  <TableCell>{i.unit}</TableCell>
                  <TableCell className="text-right tabular-nums">{rupees(i.unit_price_paise)}</TableCell>
                  <TableCell className="text-right tabular-nums">{i.gst_rate_bps / 100}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  )
}
