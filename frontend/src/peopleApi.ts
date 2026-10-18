import { request } from '@/api'

// --- employees ---

export type Department = { id: string; name: string }
export type Designation = { id: string; name: string }

export type EmployeeListItem = {
  id: string
  code: string
  name: string
  department_id: string | null
  designation_id: string | null
  status: string
  user_id: string | null
}

export type EmployeeDetail = EmployeeListItem & {
  work_email: string
  phone: string | null
  manager_id: string | null
  join_date: string
  employment_type: string
  user_id: string | null
}

export type EmployeeIn = {
  code: string
  name: string
  work_email: string
  phone?: string | null
  department_id?: string | null
  designation_id?: string | null
  manager_id?: string | null
  join_date: string
  status?: string
  employment_type?: string
  user_id?: string | null
}

export const listDepartments = () => request<Department[]>('/people/departments')
export const createDepartment = (name: string) =>
  request<Department>('/people/departments', { method: 'POST', body: JSON.stringify({ name }) })

export const listDesignations = () => request<Designation[]>('/people/designations')
export const createDesignation = (name: string) =>
  request<Designation>('/people/designations', { method: 'POST', body: JSON.stringify({ name }) })

export const listEmployees = () => request<EmployeeListItem[]>('/people/employees')
export const getEmployee = (id: string) => request<EmployeeDetail>(`/people/employees/${id}`)
export const createEmployee = (body: EmployeeIn) =>
  request<EmployeeDetail>('/people/employees', { method: 'POST', body: JSON.stringify(body) })
export const updateEmployee = (id: string, body: EmployeeIn) =>
  request<EmployeeDetail>(`/people/employees/${id}`, { method: 'PUT', body: JSON.stringify(body) })

// --- leave ---

// Decimal fields (half-day granularity) serialize over the wire as strings
// to preserve exactness -- parse with Number() for display/math.
export type AccrualFrequency = 'none' | 'monthly' | 'yearly'
export type ReasonCode = 'personal' | 'medical' | 'family' | 'bereavement' | 'travel' | 'other'

export type LeaveType = {
  id: string
  name: string
  exclude_weekends: boolean
  exclude_holidays: boolean
  accrual_frequency: AccrualFrequency
}

export type LeaveBalance = { leave_type_id: string; balance_days: string }

export type LeaveApplication = {
  id: string
  employee_id: string
  leave_type_id: string
  start_date: string
  end_date: string
  days: string
  half_day: boolean
  status: 'draft' | 'submitted' | 'approved' | 'rejected' | 'cancelled'
  reason_code: ReasonCode | null
  comment: string | null
  approver_id: string | null
}

export const listLeaveTypes = () => request<LeaveType[]>('/people/leave/types')
export const createLeaveType = (body: {
  name: string
  exclude_weekends: boolean
  exclude_holidays: boolean
  accrual_frequency: AccrualFrequency
}) => request<LeaveType>('/people/leave/types', { method: 'POST', body: JSON.stringify(body) })

export type LeavePolicy = { id: string; name: string }

export const listLeavePolicies = () => request<LeavePolicy[]>('/people/leave/policies')
export const createLeavePolicy = (body: {
  name: string
  types: { leave_type_id: string; annual_days: number }[]
}) => request<LeavePolicy>('/people/leave/policies', { method: 'POST', body: JSON.stringify(body) })
export const applyLeavePolicy = (policyId: string, employeeId: string, financialYear: string) =>
  request<LeaveAllocation[]>(`/people/leave/policies/${policyId}/apply`, {
    method: 'POST',
    body: JSON.stringify({ employee_id: employeeId, financial_year: financialYear }),
  })

export type LeaveAllocation = {
  id: string
  employee_id: string
  leave_type_id: string
  financial_year: string
  allocated_days: string
  last_accrued_on: string | null
}

export const listLeaveAllocations = (employeeId: string) =>
  request<LeaveAllocation[]>(`/people/leave/allocations/${employeeId}`)

export const accrueLeaveAllocation = (allocationId: string) =>
  request<LeaveAllocation>(`/people/leave/allocations/${allocationId}/accrue`, {
    method: 'POST',
  })

export const getLeaveBalances = (employeeId: string) =>
  request<LeaveBalance[]>(`/people/leave/balances/${employeeId}`)

export const listLeaveApplications = () => request<LeaveApplication[]>('/people/leave/applications')

export const createLeaveApplication = (body: {
  employee_id: string
  leave_type_id: string
  start_date: string
  end_date: string
  half_day?: boolean
  reason_code?: ReasonCode | null
  comment?: string | null
}) =>
  request<LeaveApplication>('/people/leave/applications', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const submitLeaveApplication = (id: string) =>
  request<LeaveApplication>(`/people/leave/applications/${id}/submit`, { method: 'POST' })
export const approveLeaveApplication = (id: string) =>
  request<LeaveApplication>(`/people/leave/applications/${id}/approve`, { method: 'POST' })
export const rejectLeaveApplication = (id: string) =>
  request<LeaveApplication>(`/people/leave/applications/${id}/reject`, { method: 'POST' })
export const cancelLeaveApplication = (id: string) =>
  request<LeaveApplication>(`/people/leave/applications/${id}/cancel`, { method: 'POST' })

// --- attendance ---

export type AttendanceStatus = 'present' | 'absent' | 'half_day' | 'on_leave' | 'holiday'

export type Attendance = {
  id: string
  employee_id: string
  date: string
  status: AttendanceStatus
  leave_application_id: string | null
}

export const markAttendance = (employeeId: string, date: string, status: AttendanceStatus) =>
  request<Attendance>('/people/attendance', {
    method: 'POST',
    body: JSON.stringify({ employee_id: employeeId, date, status }),
  })

export const getMonthlyAttendance = (employeeId: string, year: number, month: number) =>
  request<Attendance[]>(`/people/attendance/${employeeId}?year=${year}&month=${month}`)

// --- expenses ---

export type ExpenseClaimLine = {
  id: string
  description: string
  amount_paise: number
  category: string
  attachment_url: string | null
}

export type ExpenseClaim = {
  id: string
  employee_id: string
  status: 'draft' | 'submitted' | 'approved' | 'rejected'
  total_paise: number
  outstanding_paise: number
  approver_id: string | null
  lines: ExpenseClaimLine[]
}

export const listExpenseClaims = () => request<ExpenseClaim[]>('/people/expenses')

export const createExpenseClaim = (body: {
  employee_id: string
  lines: { description: string; amount_paise: number; category: string }[]
}) => request<ExpenseClaim>('/people/expenses', { method: 'POST', body: JSON.stringify(body) })

export const submitExpenseClaim = (id: string) =>
  request<ExpenseClaim>(`/people/expenses/${id}/submit`, { method: 'POST' })
export const approveExpenseClaim = (id: string) =>
  request<ExpenseClaim>(`/people/expenses/${id}/approve`, { method: 'POST' })
export const rejectExpenseClaim = (id: string) =>
  request<ExpenseClaim>(`/people/expenses/${id}/reject`, { method: 'POST' })
export const reimburseExpenseClaim = (id: string, amountPaise: number, method: string) =>
  request(`/people/expenses/${id}/reimburse`, {
    method: 'POST',
    body: JSON.stringify({ amount_paise: amountPaise, method }),
  })
