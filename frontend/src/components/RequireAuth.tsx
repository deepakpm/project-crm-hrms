import { Navigate, Outlet } from 'react-router-dom'
import * as api from '@/api'

export function RequireAuth() {
  return api.isLoggedIn() ? <Outlet /> : <Navigate to="/login" replace />
}
