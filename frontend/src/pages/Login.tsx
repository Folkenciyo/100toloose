import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Eye, EyeOff, TrendingUp, Zap, Shield } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useLanguage } from '../i18n'
import { LanguageSelector } from '../components/LanguageSelector'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const { login, isLoading, error } = useAuthStore()
  const navigate = useNavigate()
  const { t } = useLanguage()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      // Error handled in store
    }
  }

  return (
    <div className="min-h-screen bg-cyber-bg bg-grid flex relative">
      {/* Language Selector - Top Right */}
      <div className="absolute top-4 right-4 z-50">
        <LanguageSelector />
      </div>

      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center p-12 relative overflow-hidden">
        {/* Animated background elements */}
        <div className="absolute inset-0 overflow-hidden">
          <motion.div
            className="absolute w-96 h-96 bg-cyber-primary/10 rounded-full blur-3xl"
            animate={{
              x: [0, 100, 0],
              y: [0, -50, 0],
            }}
            transition={{ duration: 20, repeat: Infinity }}
            style={{ top: '10%', left: '10%' }}
          />
          <motion.div
            className="absolute w-64 h-64 bg-cyber-secondary/10 rounded-full blur-3xl"
            animate={{
              x: [0, -50, 0],
              y: [0, 100, 0],
            }}
            transition={{ duration: 15, repeat: Infinity }}
            style={{ bottom: '20%', right: '20%' }}
          />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="relative z-10 text-center"
        >
          <h1 className="font-display text-6xl font-black gradient-text mb-4">
            100toLoose
          </h1>
          <p className="text-xl text-cyber-muted mb-12">
            Autonomous Crypto Trading Bot
          </p>

          <div className="space-y-6">
            <motion.div
              className="flex items-center gap-4 text-left"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
            >
              <div className="p-3 bg-cyber-primary/20 rounded-lg">
                <TrendingUp className="text-cyber-primary" size={24} />
              </div>
              <div>
                <h3 className="font-semibold">{t.features.aiPoweredTrading}</h3>
                <p className="text-sm text-cyber-muted">
                  {t.features.aiPoweredTradingDesc}
                </p>
              </div>
            </motion.div>

            <motion.div
              className="flex items-center gap-4 text-left"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 }}
            >
              <div className="p-3 bg-cyber-secondary/20 rounded-lg">
                <Zap className="text-cyber-secondary" size={24} />
              </div>
              <div>
                <h3 className="font-semibold">{t.features.realtimeExecution}</h3>
                <p className="text-sm text-cyber-muted">
                  {t.features.realtimeExecutionDesc}
                </p>
              </div>
            </motion.div>

            <motion.div
              className="flex items-center gap-4 text-left"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 }}
            >
              <div className="p-3 bg-cyber-accent/20 rounded-lg">
                <Shield className="text-cyber-accent" size={24} />
              </div>
              <div>
                <h3 className="font-semibold">{t.features.riskManagement}</h3>
                <p className="text-sm text-cyber-muted">
                  {t.features.riskManagementDesc}
                </p>
              </div>
            </motion.div>
          </div>
        </motion.div>
      </div>

      {/* Right side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          <div className="bg-cyber-surface border border-cyber-border rounded-2xl p-8 shadow-xl">
            <div className="text-center mb-8">
              <h2 className="font-display text-3xl font-bold mb-2">{t.auth.welcomeBack}</h2>
              <p className="text-cyber-muted">{t.auth.signInToAccount}</p>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-cyber-danger/20 border border-cyber-danger/50 rounded-lg p-4 mb-6"
              >
                <p className="text-cyber-danger text-sm">{error}</p>
              </motion.div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">{t.auth.username}</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input-cyber w-full"
                  placeholder={t.auth.username}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t.auth.password}</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-cyber w-full pr-12"
                    placeholder={t.auth.password}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-cyber-muted hover:text-cyber-text"
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full py-4 text-lg"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <motion.span
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                      className="w-5 h-5 border-2 border-cyber-bg border-t-transparent rounded-full"
                    />
                    {t.auth.signingIn}
                  </span>
                ) : (
                  t.auth.login
                )}
              </button>
            </form>

            {/* Registro deshabilitado temporalmente
            <div className="mt-8 text-center">
              <p className="text-cyber-muted">
                Don't have an account?{' '}
                <Link to="/register" className="text-cyber-primary hover:underline">
                  Create one
                </Link>
              </p>
            </div>
            */}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

