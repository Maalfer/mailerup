import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth.jsx'
import Login from './pages/Login.jsx'
import Layout from './pages/Layout.jsx'
import Subscribers from './pages/Subscribers.jsx'
import Campaigns from './pages/Campaigns.jsx'
import CampaignEditor from './pages/CampaignEditor.jsx'
import Analytics from './pages/Analytics.jsx'
import Deliverability from './pages/Deliverability.jsx'
import Settings from './pages/Settings.jsx'
import Users from './pages/Users.jsx'
import Forms from './pages/Forms.jsx'
import Automations from './pages/Automations.jsx'
import AutomationStepEditor from './pages/AutomationStepEditor.jsx'
import Storage from './pages/Storage.jsx'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div role="status" aria-live="polite" className="p-8 text-gray-500">Cargando…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RequireAdmin({ children }) {
  const { user } = useAuth()
  if (!user?.is_admin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/" element={<Navigate to="/subscribers" replace />} />
            <Route path="/subscribers" element={<Subscribers />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaigns/new" element={<CampaignEditor />} />
            <Route path="/campaigns/:id/edit" element={<CampaignEditor />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/deliverability" element={<Deliverability />} />
            <Route path="/users" element={<RequireAdmin><Users /></RequireAdmin>} />
            <Route path="/forms" element={<Forms />} />
            <Route path="/automations" element={<Automations />} />
            <Route path="/automations/:automationId/steps/new" element={<AutomationStepEditor />} />
            <Route path="/automations/:automationId/steps/:stepId/edit" element={<AutomationStepEditor />} />
            <Route path="/storage" element={<Storage />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
