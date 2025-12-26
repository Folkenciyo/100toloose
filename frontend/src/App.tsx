import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Login from './pages/Login'
// import Register from './pages/Register'  // Registro deshabilitado temporalmente
import Dashboard from './pages/Dashboard'
import Trading from './pages/Trading'
import Strategies from './pages/Strategies'
import ActiveTrades from './pages/ActiveTrades'
import Logs from './pages/Logs'
import Profile from './pages/Profile'
import BalanceDistribution from './pages/BalanceDistribution'
import Layout from './components/Layout'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* <Route path="/register" element={<Register />} /> Registro deshabilitado */}
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="balance-distribution" element={<BalanceDistribution />} />
        <Route path="trading" element={<Trading />} />
        <Route path="strategies" element={<Strategies />} />
        <Route path="active-trades" element={<ActiveTrades />} />
        <Route path="logs" element={<Logs />} />
        <Route path="profile" element={<Profile />} />
      </Route>
    </Routes>
  )
}

export default App

