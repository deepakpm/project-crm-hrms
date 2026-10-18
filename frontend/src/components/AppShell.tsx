import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Users,
  Package,
  BarChart3,
  Settings,
  Menu,
  Moon,
  Sun,
  LogOut,
  ChevronsUpDown,
  Contact,
  CalendarDays,
  Clock,
  Receipt,
} from 'lucide-react'
import * as api from '@/api'
import { useTheme } from '@/lib/theme'
import { Button } from '@/components/ui/button'
import { Drawer, DrawerContent, DrawerTrigger } from '@/components/ui/drawer'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard; end?: boolean }
type NavGroup = { label: string | null; items: NavItem[] }

const NAV_GROUPS: NavGroup[] = [
  {
    label: null,
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/invoices', label: 'Invoices', icon: FileText },
      { to: '/customers', label: 'Customers', icon: Users },
      { to: '/items', label: 'Items', icon: Package },
      { to: '/reports', label: 'Reports', icon: BarChart3 },
    ],
  },
  {
    label: 'People',
    items: [
      { to: '/people/employees', label: 'Employees', icon: Contact },
      { to: '/people/leave', label: 'Leave', icon: CalendarDays },
      { to: '/people/attendance', label: 'Attendance', icon: Clock },
      { to: '/people/expenses', label: 'Expenses', icon: Receipt },
    ],
  },
  {
    label: null,
    items: [{ to: '/settings', label: 'Settings', icon: Settings }],
  },
]

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1 p-3">
      {NAV_GROUPS.map((group, i) => (
        <div key={i} className={i > 0 ? 'mt-3' : undefined}>
          {group.label && (
            <p className="px-3 pb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              {group.label}
            </p>
          )}
          {group.items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )
}

function AccountMenu({ companyName }: { companyName: string | null }) {
  const navigate = useNavigate()
  const { theme, toggle } = useTheme()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm hover:bg-muted">
          <span className="flex-1 truncate font-medium">{companyName ?? 'Your workspace'}</span>
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuItem onClick={() => navigate('/settings')}>
          <Settings className="size-4" aria-hidden="true" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuItem onClick={toggle}>
          {theme === 'dark' ? (
            <Sun className="size-4" aria-hidden="true" />
          ) : (
            <Moon className="size-4" aria-hidden="true" />
          )}
          {theme === 'dark' ? 'Light theme' : 'Dark theme'}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          onClick={() => {
            api.logout()
            navigate('/login')
          }}
        >
          <LogOut className="size-4" aria-hidden="true" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function AppShell() {
  const [companyName, setCompanyName] = useState<string | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  useEffect(() => {
    api.getCompany().then(
      (c) => setCompanyName(c.legal_name),
      () => setCompanyName(null), // no company profile set yet -- fine, Settings page handles that
    )
  }, [])

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r md:flex">
        <div className="flex h-14 items-center border-b px-4 font-semibold">ledgerly</div>
        <div className="flex-1 overflow-y-auto">
          <SidebarNav />
        </div>
        <div className="border-t p-3">
          <AccountMenu companyName={companyName} />
        </div>
      </aside>

      <div className="md:pl-60">
        <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b bg-background px-4 md:hidden">
          <Drawer direction="left" open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <DrawerTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Open navigation">
                <Menu className="size-5" />
              </Button>
            </DrawerTrigger>
            <DrawerContent className="h-dvh w-60 rounded-none">
              <div className="flex h-14 items-center border-b px-4 font-semibold">ledgerly</div>
              <SidebarNav onNavigate={() => setMobileNavOpen(false)} />
              <div className="mt-auto border-t p-3">
                <AccountMenu companyName={companyName} />
              </div>
            </DrawerContent>
          </Drawer>
          <span className="font-semibold">ledgerly</span>
        </header>

        <main className="mx-auto max-w-[1200px] px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
