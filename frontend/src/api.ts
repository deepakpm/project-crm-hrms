const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8001'

export type Tokens = { access_token: string; refresh_token: string }

let tokens: Tokens | null = JSON.parse(localStorage.getItem('ledgerly_tokens') ?? 'null')

function setTokens(t: Tokens | null) {
  tokens = t
  if (t) localStorage.setItem('ledgerly_tokens', JSON.stringify(t))
  else localStorage.removeItem('ledgerly_tokens')
}

export function isLoggedIn() {
  return tokens !== null
}

export function logout() {
  setTokens(null)
}

function decodedAccessToken(): { sub?: string; role?: string } | null {
  if (!tokens) return null
  try {
    return JSON.parse(atob(tokens.access_token.split('.')[1]))
  } catch {
    return null
  }
}

export const currentUserId = () => decodedAccessToken()?.sub ?? null
export const currentUserRole = () => decodedAccessToken()?.role ?? null

export class ApiError extends Error {}

export async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers)
  if (tokens) headers.set('Authorization', `Bearer ${tokens.access_token}`)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (resp.status === 401 && tokens && retry) {
    const refreshed = await tryRefresh()
    if (refreshed) return request<T>(path, options, false)
  }

  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail ?? resp.statusText)
    throw new ApiError(detail)
  }

  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

async function tryRefresh(): Promise<boolean> {
  if (!tokens) return false
  const resp = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  })
  if (!resp.ok) {
    setTokens(null)
    return false
  }
  setTokens(await resp.json())
  return true
}

// --- auth ---

export async function signup(body: {
  company_name: string
  tenant_slug: string
  email: string
  password: string
}) {
  const t = await request<Tokens>('/auth/signup', { method: 'POST', body: JSON.stringify(body) })
  setTokens(t)
}

export async function login(body: { tenant_slug: string; email: string; password: string }) {
  const t = await request<Tokens>('/auth/login', { method: 'POST', body: JSON.stringify(body) })
  setTokens(t)
}

// --- users (teammates) ---

export type User = {
  id: string
  tenant_id: string
  email: string
  role: 'owner' | 'accountant' | 'member' | 'hr' | 'manager'
}

export const listUsers = () => request<User[]>('/users')
export const createTeammate = (body: { email: string; password: string; role: User['role'] }) =>
  request<User>('/users', { method: 'POST', body: JSON.stringify(body) })

// --- company ---

export type Company = {
  id: string
  legal_name: string
  gstin: string
  state_code: string
  address: string
}

export const getCompany = () => request<Company>('/company')
export const upsertCompany = (body: Omit<Company, 'id'>) =>
  request<Company>('/company', { method: 'PUT', body: JSON.stringify(body) })

// --- customers ---

export type Customer = {
  id: string
  name: string
  gstin: string | null
  state_code: string
  billing_address: string
}

export const listCustomers = () => request<Customer[]>('/customers')
export const createCustomer = (body: Omit<Customer, 'id'>) =>
  request<Customer>('/customers', { method: 'POST', body: JSON.stringify(body) })

// --- items ---

export type Item = {
  id: string
  name: string
  hsn_sac: string
  unit: string
  unit_price_paise: number
  gst_rate_bps: number
}

export const listItems = () => request<Item[]>('/items')
export const createItem = (body: Omit<Item, 'id'>) =>
  request<Item>('/items', { method: 'POST', body: JSON.stringify(body) })

// --- invoices ---

export type InvoiceLine = {
  item_id: string
  description: string
  hsn_sac: string
  quantity: number
  unit_price_paise: number
  gst_rate_bps: number
  taxable_paise: number
  cgst_paise: number
  sgst_paise: number
  igst_paise: number
}

export type Invoice = {
  id: string
  customer_id: string
  quote_id: string | null
  status: 'draft' | 'issued' | 'cancelled'
  financial_year: string | null
  number: number | null
  place_of_supply_state_code: string
  subtotal_paise: number
  cgst_paise: number
  sgst_paise: number
  igst_paise: number
  grand_total_paise: number
  created_at: string
  issued_at: string | null
  cancelled_at: string | null
  lines: InvoiceLine[]
}

export type InvoiceDraft = {
  customer_id: string
  quote_id?: string | null
  lines: { item_id: string; quantity: number }[]
}

export type InvoicePreview = {
  place_of_supply_state_code: string
  subtotal_paise: number
  cgst_paise: number
  sgst_paise: number
  igst_paise: number
  grand_total_paise: number
  lines: InvoiceLine[]
}

export const listInvoices = () => request<Invoice[]>('/invoices')
export const getInvoice = (id: string) => request<Invoice>(`/invoices/${id}`)

export const createInvoice = (body: InvoiceDraft) =>
  request<Invoice>('/invoices', { method: 'POST', body: JSON.stringify(body) })

// Same GST calc the backend uses on create -- never duplicated in the browser.
export const previewInvoice = (body: InvoiceDraft) =>
  request<InvoicePreview>('/invoices/preview', { method: 'POST', body: JSON.stringify(body) })

export const issueInvoice = (id: string) =>
  request<Invoice>(`/invoices/${id}/issue`, { method: 'POST' })

export const cancelInvoice = (id: string) =>
  request<Invoice>(`/invoices/${id}/cancel`, { method: 'POST' })

export async function downloadInvoicePdf(invoice: Invoice) {
  const headers = new Headers()
  if (tokens) headers.set('Authorization', `Bearer ${tokens.access_token}`)
  const resp = await fetch(`${API_BASE}/invoices/${invoice.id}/pdf`, { headers })
  if (!resp.ok) throw new ApiError('could not fetch PDF')
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `invoice-${invoice.financial_year}-${invoice.number}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

// --- payments ---

export type Payment = {
  id: string
  invoice_id: string
  amount_paise: number
  method: string
  paid_at: string
}

export const createPayment = (body: { invoice_id: string; amount_paise: number; method: string }) =>
  request<Payment>('/payments', { method: 'POST', body: JSON.stringify(body) })

// --- reports ---

export type TrialBalanceRow = {
  account_code: string
  account_name: string
  account_type: string
  debit_paise: number
  credit_paise: number
}

export type AgeingRow = {
  invoice_id: string
  financial_year: string | null
  number: number | null
  customer_name: string
  outstanding_paise: number
  days_overdue: number
  bucket: string
}

export const getTrialBalance = () => request<TrialBalanceRow[]>('/reports/trial-balance')
export const getReceivablesAgeing = () => request<AgeingRow[]>('/reports/receivables-ageing')
