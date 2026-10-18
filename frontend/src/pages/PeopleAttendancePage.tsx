import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import * as api from '@/api'
import * as peopleApi from '@/peopleApi'
import { usePageTitle } from '@/lib/usePageTitle'
import { PageHeader } from '@/components/PageHeader'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'

const STATUSES: peopleApi.AttendanceStatus[] = ['present', 'absent', 'half_day', 'on_leave', 'holiday']
const STATUS_DOT: Record<peopleApi.AttendanceStatus, string> = {
  present: 'bg-success',
  absent: 'bg-destructive',
  half_day: 'bg-warning',
  on_leave: 'bg-warning',
  holiday: 'bg-muted-foreground',
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month, 0).getDate()
}

export function PeopleAttendancePage() {
  usePageTitle('Attendance')
  const [employees, setEmployees] = useState<peopleApi.EmployeeListItem[]>([])
  const [employeeId, setEmployeeId] = useState('')
  const [now] = useState(() => new Date())
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1) // 1-12
  const [marks, setMarks] = useState<peopleApi.Attendance[]>([])

  useEffect(() => {
    peopleApi.listEmployees().then((all) => {
      setEmployees(all)
      const mine = all.find((e) => e.user_id === api.currentUserId())
      setEmployeeId(mine?.id ?? all[0]?.id ?? '')
    })
  }, [])

  const reload = () => {
    if (employeeId) peopleApi.getMonthlyAttendance(employeeId, year, month).then(setMarks)
  }
  useEffect(reload, [employeeId, year, month])

  const markByDate = new Map(marks.map((m) => [m.date, m]))

  async function setDay(day: number, status: peopleApi.AttendanceStatus) {
    const date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    try {
      await peopleApi.markAttendance(employeeId, date, status)
      reload()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  const total = daysInMonth(year, month)
  const firstWeekday = new Date(year, month - 1, 1).getDay() // 0=Sun

  return (
    <>
      <PageHeader title="Attendance">
        <Select value={employeeId} onValueChange={setEmployeeId}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Employee" />
          </SelectTrigger>
          <SelectContent>
            {employees.map((e) => (
              <SelectItem key={e.id} value={e.id}>
                {e.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <SelectItem key={m} value={String(m)}>
                {new Date(2000, m - 1, 1).toLocaleString('en', { month: 'long' })}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
          <SelectTrigger className="w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </PageHeader>

      <Card>
        <CardContent className="pt-6">
          <div className="mb-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
            {STATUSES.map((s) => (
              <span key={s} className="flex items-center gap-1.5">
                <span className={`size-2 rounded-full ${STATUS_DOT[s]}`} aria-hidden="true" />
                {s.replace('_', ' ')}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
              <div key={d} className="py-1">
                {d}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: firstWeekday }, (_, i) => (
              <div key={`empty-${i}`} />
            ))}
            {Array.from({ length: total }, (_, i) => i + 1).map((day) => {
              const date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
              const mark = markByDate.get(date)
              const fromLeave = mark?.leave_application_id != null
              return (
                <div
                  key={day}
                  className={`flex flex-col items-center gap-1 rounded-md border p-1.5 ${fromLeave ? 'bg-muted/50' : ''}`}
                >
                  <span className="text-xs">{day}</span>
                  <Select
                    value={mark?.status ?? ''}
                    onValueChange={(v) => setDay(day, v as peopleApi.AttendanceStatus)}
                    disabled={fromLeave}
                  >
                    <SelectTrigger
                      className="h-6 w-full px-1 text-xs"
                      size="sm"
                      title={fromLeave ? 'Set by an approved leave application' : undefined}
                    >
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUSES.map((s) => (
                        <SelectItem key={s} value={s}>
                          {s.replace('_', ' ')}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </>
  )
}
