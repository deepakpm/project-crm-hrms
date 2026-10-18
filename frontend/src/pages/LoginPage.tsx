import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Landmark } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '@/api'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

function PasswordInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <Input
        id="password"
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        minLength={8}
        required
        className="pr-10"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground hover:text-foreground"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  )
}

export function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'signup' | 'login'>('signup')
  const [companyName, setCompanyName] = useState('')
  const [tenantSlug, setTenantSlug] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  usePageTitle(mode === 'signup' ? 'Sign up' : 'Log in')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'signup') {
        await api.signup({ company_name: companyName, tenant_slug: tenantSlug, email, password })
        toast.success('Workspace created')
      } else {
        await api.login({ tenant_slug: tenantSlug, email, password })
        toast.success('Welcome back')
      }
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-dvh md:grid-cols-2">
      <div className="hidden flex-col justify-center gap-4 bg-primary px-12 text-primary-foreground md:flex">
        <div className="flex items-center gap-2 text-2xl font-semibold">
          <Landmark className="size-7" aria-hidden="true" />
          ledgerly
        </div>
        <p className="max-w-sm text-primary-foreground/80">
          GST invoicing and a real double-entry ledger, built for Indian startups.
        </p>
      </div>

      <div className="flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>
              <Tabs value={mode} onValueChange={(v) => setMode(v as 'signup' | 'login')}>
                <TabsList className="w-full">
                  <TabsTrigger value="signup" className="flex-1">
                    Sign up
                  </TabsTrigger>
                  <TabsTrigger value="login" className="flex-1">
                    Log in
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </CardTitle>
            <CardDescription>
              {mode === 'signup'
                ? 'Create your company workspace.'
                : 'Sign in to your workspace.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="flex flex-col gap-4">
              {mode === 'signup' && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="company_name">Company name</Label>
                  <Input
                    id="company_name"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    required
                  />
                </div>
              )}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="tenant_slug">Workspace URL</Label>
                <Input
                  id="tenant_slug"
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  placeholder="your-company"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  Lowercase letters, numbers and hyphens only.
                </p>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password">Password</Label>
                <PasswordInput value={password} onChange={setPassword} />
                <p className="text-xs text-muted-foreground">At least 8 characters.</p>
              </div>
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <Button type="submit" disabled={busy} className="mt-2">
                {busy ? 'Please wait…' : mode === 'signup' ? 'Create workspace' : 'Log in'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
