import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  LayoutDashboard, 
  TrendingUp, 
  Brain, 
  LogOut, 
  Wallet,
  Activity,
  FileText,
  Settings
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useLanguage } from '../i18n'
import { LanguageSelector } from './LanguageSelector'

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const { t } = useLanguage()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { path: '/', icon: LayoutDashboard, label: t.nav.dashboard },
    { path: '/trading', icon: TrendingUp, label: t.nav.trading },
    { path: '/strategies', icon: Brain, label: t.nav.strategies },
    { path: '/logs', icon: FileText, label: t.nav.logs },
    { path: '/profile', icon: Settings, label: t.nav.profile },
  ]

  return (
    <div className="min-h-screen bg-cyber-bg bg-grid">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-64 bg-cyber-surface border-r border-cyber-border z-50">
        {/* Logo */}
        <div className="p-6 border-b border-cyber-border">
          <motion.h1 
            className="font-display text-2xl font-bold gradient-text"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            100toLoose
          </motion.h1>
          <p className="text-cyber-muted text-xs mt-1">Autonomous Trading Bot</p>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-300 ${
                  isActive
                    ? 'bg-cyber-primary/10 text-cyber-primary border border-cyber-primary/30'
                    : 'text-cyber-muted hover:text-cyber-text hover:bg-cyber-card'
                }`
              }
            >
              <item.icon size={20} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* User Info */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-cyber-border">
          {/* Language Selector */}
          <div className="mb-4 flex justify-center">
            <LanguageSelector />
          </div>

          <div className="bg-cyber-card rounded-lg p-4 mb-4">
            <div className="flex items-center gap-2 mb-2">
              <Wallet size={16} className="text-cyber-primary" />
              <span className="text-sm text-cyber-muted">{t.nav.balance}</span>
            </div>
            <p className="text-xl font-bold text-cyber-primary">
              ${user?.current_balance?.toLocaleString() || '0.00'}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <Activity size={12} className="text-cyber-secondary" />
              <span className="text-xs text-cyber-muted">
                {user?.paper_trading ? t.nav.paperTrading : t.nav.liveTrading}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{user?.username}</p>
              <p className="text-xs text-cyber-muted">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 rounded-lg hover:bg-cyber-danger/20 text-cyber-danger transition-all"
              title={t.auth.logout}
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-64 min-h-screen p-8">
        <Outlet />
      </main>
    </div>
  )
}

