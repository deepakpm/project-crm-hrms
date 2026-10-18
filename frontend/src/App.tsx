import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { RequireAuth } from '@/components/RequireAuth'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { CustomersPage } from '@/pages/CustomersPage'
import { ItemsPage } from '@/pages/ItemsPage'
import { InvoicesListPage } from '@/pages/InvoicesListPage'
import { InvoiceEditorPage } from '@/pages/InvoiceEditorPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PeopleEmployeesPage } from '@/pages/PeopleEmployeesPage'
import { PeopleLeavePage } from '@/pages/PeopleLeavePage'
import { PeopleAttendancePage } from '@/pages/PeopleAttendancePage'
import { PeopleExpensesPage } from '@/pages/PeopleExpensesPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/items" element={<ItemsPage />} />
            <Route path="/invoices" element={<InvoicesListPage />} />
            <Route path="/invoices/new" element={<InvoiceEditorPage />} />
            <Route path="/invoices/:invoiceId" element={<InvoiceEditorPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/people/employees" element={<PeopleEmployeesPage />} />
            <Route path="/people/leave" element={<PeopleLeavePage />} />
            <Route path="/people/attendance" element={<PeopleAttendancePage />} />
            <Route path="/people/expenses" element={<PeopleExpensesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
