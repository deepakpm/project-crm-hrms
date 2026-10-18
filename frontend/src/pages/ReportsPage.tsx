import { useEffect, useState } from 'react'
import * as api from '@/api'
import { rupees } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

function toCsv(headers: string[], rows: (string | number)[][]) {
  const escape = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`
  return [headers, ...rows].map((row) => row.map(escape).join(',')).join('\n')
}

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function TrialBalanceTab() {
  const [rows, setRows] = useState<api.TrialBalanceRow[] | null>(null)

  useEffect(() => {
    api.getTrialBalance().then(setRows)
  }, [])

  if (!rows) return <Skeleton className="h-48 w-full" />

  const totalDebit = rows.reduce((sum, r) => sum + r.debit_paise, 0)
  const totalCredit = rows.reduce((sum, r) => sum + r.credit_paise, 0)

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            downloadCsv(
              'trial-balance.csv',
              toCsv(
                ['Code', 'Account', 'Type', 'Debit', 'Credit'],
                rows.map((r) => [r.account_code, r.account_name, r.account_type, r.debit_paise / 100, r.credit_paise / 100]),
              ),
            )
          }
        >
          Export CSV
        </Button>
      </div>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Account</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Debit</TableHead>
              <TableHead className="text-right">Credit</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.account_code}>
                <TableCell className="font-medium">
                  {r.account_code} {r.account_name}
                </TableCell>
                <TableCell className="text-muted-foreground">{r.account_type}</TableCell>
                <TableCell className="text-right tabular-nums">{rupees(r.debit_paise)}</TableCell>
                <TableCell className="text-right tabular-nums">{rupees(r.credit_paise)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="font-semibold">
              <TableCell colSpan={2}>Total</TableCell>
              <TableCell className="text-right tabular-nums">{rupees(totalDebit)}</TableCell>
              <TableCell className="text-right tabular-nums">{rupees(totalCredit)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function AgeingTab() {
  const [rows, setRows] = useState<api.AgeingRow[] | null>(null)

  useEffect(() => {
    api.getReceivablesAgeing().then(setRows)
  }, [])

  if (!rows) return <Skeleton className="h-48 w-full" />

  const total = rows.reduce((sum, r) => sum + r.outstanding_paise, 0)

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            downloadCsv(
              'receivables-ageing.csv',
              toCsv(
                ['Invoice', 'Customer', 'Outstanding', 'Days overdue', 'Bucket'],
                rows.map((r) => [
                  r.number ? `${r.financial_year}/${r.number}` : '',
                  r.customer_name,
                  r.outstanding_paise / 100,
                  r.days_overdue,
                  r.bucket,
                ]),
              ),
            )
          }
        >
          Export CSV
        </Button>
      </div>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Invoice</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead className="text-right">Outstanding</TableHead>
              <TableHead className="text-right">Days overdue</TableHead>
              <TableHead>Bucket</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.invoice_id}>
                <TableCell className="font-medium">
                  {r.financial_year}/{r.number}
                </TableCell>
                <TableCell>{r.customer_name}</TableCell>
                <TableCell className="text-right tabular-nums">{rupees(r.outstanding_paise)}</TableCell>
                <TableCell className="text-right tabular-nums">{r.days_overdue}</TableCell>
                <TableCell>
                  <Badge variant={r.bucket === '0-30' ? 'secondary' : r.bucket === '90+' ? 'destructive' : 'warning'}>
                    {r.bucket}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground">
                  Nothing outstanding.
                </TableCell>
              </TableRow>
            )}
            {rows.length > 0 && (
              <TableRow className="font-semibold">
                <TableCell colSpan={2}>Total</TableCell>
                <TableCell className="text-right tabular-nums">{rupees(total)}</TableCell>
                <TableCell colSpan={2} />
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

export function ReportsPage() {
  usePageTitle('Reports')
  return (
    <>
      <PageHeader title="Reports" />
      <Tabs defaultValue="trial-balance">
        <TabsList>
          <TabsTrigger value="trial-balance">Trial balance</TabsTrigger>
          <TabsTrigger value="ageing">Receivables ageing</TabsTrigger>
        </TabsList>
        <TabsContent value="trial-balance">
          <TrialBalanceTab />
        </TabsContent>
        <TabsContent value="ageing">
          <AgeingTab />
        </TabsContent>
      </Tabs>
    </>
  )
}
