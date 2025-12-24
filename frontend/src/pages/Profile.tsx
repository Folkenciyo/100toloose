import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Settings, 
  Key, 
  Mail, 
  Send, 
  Bot,
  Save,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Info,
  User,
  Phone,
  Hash,
  Target
} from 'lucide-react'
import { profileApi } from '../services/api'
import { useLanguage } from '../i18n'
import { InfoTooltip } from '../components/InfoTooltip'

interface ProfileSettings {
  profile_info: {
    profile_name: string | null
    summary_email: string | null
    phone_number: string | null
    platform_user_id: string | null
    paper_trading?: boolean
  }
  binance_testnet: {
    api_key: string | null
    secret_key: string | null
  }
  binance_real: {
    api_key: string | null
    secret_key: string | null
  }
  deepseek: {
    api_key: string | null
    enabled: boolean
  }
  smtp: {
    host: string | null
    port: number | null
    user: string | null
    password: string | null
    from_email: string | null
    enabled: boolean
  }
  telegram: {
    bot_token: string | null
    chat_id: string | null
    enabled: boolean
  }
}

export default function Profile() {
  const { t } = useLanguage()
  const [settings, setSettings] = useState<ProfileSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string } | null>>({})

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const res = await profileApi.getSettings()
      const data = res.data
      // Asegurar que las estructuras existan incluso si vienen undefined del backend
      setSettings({
        ...data,
        binance_testnet: data.binance_testnet || { api_key: null, secret_key: null },
        binance_real: data.binance_real || { api_key: null, secret_key: null },
        profile_info: {
          ...data.profile_info,
          paper_trading: data.profile_info?.paper_trading !== undefined ? data.profile_info.paper_trading : true
        }
      })
    } catch (error) {
      console.error('Failed to fetch settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!settings) return
    
    setSaving(true)
    try {
      // Limpiar valores placeholder antes de enviar
      // Solo enviar valores si no son "***", no están vacíos, y tienen contenido válido
      const settingsToSave: any = {
        profile_info: settings.profile_info,
        binance_testnet: {
          api_key: settings.binance_testnet?.api_key || undefined,
          secret_key: (settings.binance_testnet?.secret_key && settings.binance_testnet.secret_key !== '***') 
            ? settings.binance_testnet.secret_key 
            : undefined,
        },
        binance_real: {
          api_key: settings.binance_real?.api_key || undefined,
          secret_key: (settings.binance_real?.secret_key && settings.binance_real.secret_key !== '***') 
            ? settings.binance_real.secret_key 
            : undefined,
        },
        deepseek: {
          api_key: settings.deepseek.api_key || undefined,
          enabled: settings.deepseek.enabled !== undefined ? settings.deepseek.enabled : false,
        },
        smtp: {
          host: settings.smtp.host && settings.smtp.host.trim() !== '' ? settings.smtp.host : undefined,
          port: settings.smtp.port ? settings.smtp.port : undefined,
          user: settings.smtp.user && settings.smtp.user.trim() !== '' ? settings.smtp.user : undefined,
          password: (settings.smtp.password && settings.smtp.password !== '***' && settings.smtp.password.trim() !== '') 
            ? settings.smtp.password 
            : undefined,
          from_email: settings.smtp.from_email && settings.smtp.from_email.trim() !== '' ? settings.smtp.from_email : undefined,
          enabled: settings.smtp.enabled,
        },
        telegram: {
          bot_token: (settings.telegram.bot_token && 
                     settings.telegram.bot_token !== '***' && 
                     settings.telegram.bot_token.trim() !== '') 
            ? settings.telegram.bot_token 
            : undefined,
          chat_id: settings.telegram.chat_id || undefined,
          enabled: settings.telegram.enabled,
        },
      }
      
      // Eliminar campos undefined para que no se envíen
      Object.keys(settingsToSave).forEach(key => {
        if (settingsToSave[key] && typeof settingsToSave[key] === 'object') {
          Object.keys(settingsToSave[key]).forEach(subKey => {
            if (settingsToSave[key][subKey] === undefined) {
              delete settingsToSave[key][subKey]
            }
          })
          // Si el objeto está vacío, no enviarlo
          if (Object.keys(settingsToSave[key]).length === 0) {
            delete settingsToSave[key]
          }
        }
      })
      
      await profileApi.updateSettings(settingsToSave)
      setTestResults({})
      alert(t.profile.settingsSaved)
      // Reload settings to get updated data
      await fetchSettings()
    } catch (error: any) {
      alert(error.response?.data?.detail || t.profile.saveError)
    } finally {
      setSaving(false)
    }
  }

  const handleTestEmail = async () => {
    setTestResults(prev => ({ ...prev, email: null }))
    try {
      const res = await profileApi.testEmail()
      setTestResults(prev => ({ ...prev, email: { success: true, message: res.data.message } }))
    } catch (error: any) {
      setTestResults(prev => ({ 
        ...prev, 
        email: { success: false, message: error.response?.data?.detail || t.profile.testError } 
      }))
    }
  }

  const handleTestTelegram = async () => {
    setTestResults(prev => ({ ...prev, telegram: null }))
    
    // Verificar que tenemos chat_id antes de probar
    if (!settings?.telegram.chat_id) {
      setTestResults(prev => ({ 
        ...prev, 
        telegram: { 
          success: false, 
          message: t.profile.telegram.needChatIdFirst 
        } 
      }))
      return
    }
    
    try {
      const res = await profileApi.testTelegram()
      setTestResults(prev => ({ ...prev, telegram: { success: true, message: res.data.message } }))
    } catch (error: any) {
      setTestResults(prev => ({ 
        ...prev, 
        telegram: { success: false, message: error.response?.data?.detail || t.profile.testError } 
      }))
    }
  }

  const handleTestTelegramTrade = async () => {
    setTestResults(prev => ({ ...prev, telegram: null }))
    
    // Verificar que tenemos chat_id antes de probar
    if (!settings?.telegram.chat_id) {
      setTestResults(prev => ({ 
        ...prev, 
        telegram: { 
          success: false, 
          message: t.profile.telegram.needChatIdFirst 
        } 
      }))
      return
    }
    
    try {
      const res = await profileApi.testTelegramTrade()
      setTestResults(prev => ({ ...prev, telegram: { success: true, message: res.data.message } }))
    } catch (error: any) {
      setTestResults(prev => ({ 
        ...prev, 
        telegram: { success: false, message: error.response?.data?.detail || t.profile.testError } 
      }))
    }
  }

  const handleGetChatId = async () => {
    setTestResults(prev => ({ ...prev, chatId: null }))
    try {
      const res = await profileApi.getTelegramChatId()
      if (res.data.success) {
        // Auto-fill the chat ID
        setSettings(prev => prev ? {
          ...prev,
          telegram: { ...prev.telegram, chat_id: res.data.chat_id }
        } : null)
        setTestResults(prev => ({ 
          ...prev, 
          chatId: { 
            success: true, 
            message: `${t.profile.telegram.chatIdFound}: ${res.data.chat_id} (${res.data.chat_type})` 
          } 
        }))
      } else {
        setTestResults(prev => ({ 
          ...prev, 
          chatId: { 
            success: false, 
            message: res.data.message || t.profile.telegram.chatIdNotFound,
            instructions: res.data.instructions || []
          } 
        }))
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || t.profile.telegram.chatIdError
      setTestResults(prev => ({ 
        ...prev, 
        chatId: { success: false, message: errorMessage } 
      }))
    }
  }

  const togglePasswordVisibility = (field: string) => {
    setShowPasswords(prev => ({ ...prev, [field]: !prev[field] }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          className="w-12 h-12 border-4 border-cyber-primary border-t-transparent rounded-full"
        />
      </div>
    )
  }

  if (!settings) {
    return <div className="text-center py-12 text-cyber-muted">{t.profile.loadError}</div>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <motion.h1 
          className="text-3xl font-display font-bold"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          {t.profile.title}
        </motion.h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 btn-primary"
        >
          <Save size={20} />
          {saving ? t.common.loading : t.common.save}
        </button>
      </div>

      {/* Profile Information */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-cyber-surface border border-cyber-border rounded-xl p-6 mb-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-cyber-primary/20 rounded-lg">
            <User className="text-cyber-primary" size={24} />
          </div>
          <div>
            <h2 className="text-xl font-bold">{t.profile.profileInfo.title}</h2>
            <p className="text-sm text-cyber-muted">{t.profile.profileInfo.description}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-cyber-muted mb-2">{t.profile.profileInfo.profileName}</label>
            <input
              type="text"
              value={settings.profile_info.profile_name || ''}
              onChange={(e) => setSettings({
                ...settings,
                profile_info: { ...settings.profile_info, profile_name: e.target.value }
              })}
              className="input-cyber w-full"
              placeholder={t.profile.profileInfo.profileNamePlaceholder}
            />
          </div>

          <div>
            <label className="block text-sm text-cyber-muted mb-2">{t.profile.profileInfo.summaryEmail}</label>
            <input
              type="email"
              value={settings.profile_info.summary_email || ''}
              onChange={(e) => setSettings({
                ...settings,
                profile_info: { ...settings.profile_info, summary_email: e.target.value }
              })}
              className="input-cyber w-full"
              placeholder={t.profile.profileInfo.summaryEmailPlaceholder}
            />
          </div>

          <div>
            <label className="block text-sm text-cyber-muted mb-2">{t.profile.profileInfo.phoneNumber}</label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 text-cyber-muted" size={18} />
              <input
                type="text"
                value={settings.profile_info.phone_number || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  profile_info: { ...settings.profile_info, phone_number: e.target.value }
                })}
                className="input-cyber w-full pl-10"
                placeholder={t.profile.profileInfo.phoneNumberPlaceholder}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-cyber-muted mb-2">{t.profile.profileInfo.platformUserId}</label>
            <div className="relative">
              <Hash className="absolute left-3 top-1/2 -translate-y-1/2 text-cyber-muted" size={18} />
              <input
                type="text"
                value={settings.profile_info.platform_user_id || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  profile_info: { ...settings.profile_info, platform_user_id: e.target.value }
                })}
                className="input-cyber w-full pl-10"
                placeholder={t.profile.profileInfo.platformUserIdPlaceholder}
              />
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Binance Testnet Configuration (Paper Trading) */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-cyber-warning/20 rounded-lg">
              <Key className="text-cyber-warning" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold">{t.profile.binance?.testnetTitle || 'Binance Testnet (Paper Trading)'}</h2>
              <p className="text-sm text-cyber-muted">{t.profile.binance?.testnetDescription || 'API keys for Binance Testnet. Used when Paper Trading is enabled.'}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-cyber-muted mb-2">{t.profile.binance?.apiKey || 'API Key'}</label>
              <input
                type="text"
                value={settings.binance_testnet.api_key || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  binance_testnet: { ...(settings.binance_testnet || {}), api_key: e.target.value }
                })}
                className="input-cyber w-full font-mono text-sm"
                placeholder="testnet-api-key"
              />
            </div>

            <div>
              <label className="block text-sm text-cyber-muted mb-2">{t.profile.binance?.secretKey || 'Secret Key'}</label>
              <div className="relative">
                <input
                  type={showPasswords.binance_testnet_secret ? 'text' : 'password'}
                  value={settings.binance_testnet?.secret_key === '***' ? '' : (settings.binance_testnet?.secret_key || '')}
                  onChange={(e) => setSettings({
                    ...settings,
                    binance_testnet: { ...(settings.binance_testnet || {}), secret_key: e.target.value }
                  })}
                  className="input-cyber w-full font-mono text-sm pr-12"
                  placeholder="testnet-secret-key"
                />
                <button
                  type="button"
                  onClick={() => togglePasswordVisibility('binance_testnet_secret')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-cyber-muted hover:text-cyber-text"
                >
                  {showPasswords.binance_testnet_secret ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Binance Real Configuration (Real Trading) */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="bg-cyber-surface border border-cyber-danger/50 rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-cyber-danger/20 rounded-lg">
              <Key className="text-cyber-danger" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold">{t.profile.binance?.realTitle || 'Binance Real (Real Trading)'}</h2>
              <p className="text-sm text-cyber-muted">{t.profile.binance?.realDescription || '⚠️ API keys for REAL Binance trading. Uses REAL MONEY!'}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-cyber-muted mb-2">{t.profile.binance?.apiKey || 'API Key'}</label>
              <input
                type="text"
                value={settings.binance_real?.api_key || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  binance_real: { ...(settings.binance_real || {}), api_key: e.target.value }
                })}
                className="input-cyber w-full font-mono text-sm"
                placeholder="real-api-key"
              />
            </div>

            <div>
              <label className="block text-sm text-cyber-muted mb-2">{t.profile.binance?.secretKey || 'Secret Key'}</label>
              <div className="relative">
                <input
                  type={showPasswords.binance_real_secret ? 'text' : 'password'}
                  value={settings.binance_real?.secret_key === '***' ? '' : (settings.binance_real?.secret_key || '')}
                  onChange={(e) => setSettings({
                    ...settings,
                    binance_real: { ...(settings.binance_real || {}), secret_key: e.target.value }
                  })}
                  className="input-cyber w-full font-mono text-sm pr-12"
                  placeholder="real-secret-key"
                />
                <button
                  type="button"
                  onClick={() => togglePasswordVisibility('binance_real_secret')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-cyber-muted hover:text-cyber-text"
                >
                  {showPasswords.binance_real_secret ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
          </div>
        </motion.div>

        {/* DeepSeek Configuration */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-cyber-secondary/20 rounded-lg">
              <Bot className="text-cyber-secondary" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold">{t.profile.deepseek.title}</h2>
              <p className="text-sm text-cyber-muted">{t.profile.deepseek.description}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <label className="block text-sm text-cyber-muted">{t.profile.deepseek.apiKey}</label>
                <InfoTooltip
                  title={t.profile.deepseek.apiKey}
                  description={t.profile.deepseek.apiKeyInfo}
                  example={t.profile.deepseek.apiKeyExample}
                />
              </div>
              <input
                type="text"
                value={settings.deepseek.api_key || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  deepseek: { ...settings.deepseek, api_key: e.target.value }
                })}
                className="input-cyber w-full font-mono text-sm"
                placeholder="sk-..."
              />
            </div>

            {/* Enable DeepSeek Toggle */}
            <div className="flex items-center justify-between p-4 bg-cyber-secondary/10 rounded-lg border border-cyber-border">
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t.profile.deepseek.enable || 'Enable DeepSeek AI'}
                </label>
                <p className="text-xs text-cyber-muted">
                  {t.profile.deepseek.enableDescription || 'Activate DeepSeek AI analysis for trading decisions'}
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.deepseek.enabled || false}
                  onChange={(e) => setSettings({
                    ...settings,
                    deepseek: { ...settings.deepseek, enabled: e.target.checked }
                  })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-cyber-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyber-secondary"></div>
              </label>
            </div>
          </div>
        </motion.div>

        {/* Trading Mode Toggle */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-cyber-warning/20 rounded-lg">
              <Target className="text-cyber-warning" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold">{t.profile.tradingMode?.title || 'Trading Mode'}</h2>
              <p className="text-sm text-cyber-muted">{t.profile.tradingMode?.description || 'Choose between Paper Trading (Testnet) and Real Trading'}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-cyber-secondary/10 rounded-lg border border-cyber-border">
              <div>
                <label className="block text-sm font-medium mb-1">
                  {t.profile.tradingMode?.paperTrading || 'Paper Trading (Testnet)'}
                </label>
                <p className="text-xs text-cyber-muted">
                  {t.profile.tradingMode?.paperTradingDesc || 'Trade with fake money on Binance Testnet. Safe for testing.'}
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.profile_info?.paper_trading !== undefined ? settings.profile_info.paper_trading : true}
                  onChange={async (e) => {
                    const newMode = e.target.checked;
                    if (!newMode && (!settings.binance_real?.api_key || !settings.binance_real?.secret_key)) {
                      alert(t.profile.tradingMode?.needApiKeys || 'You need to configure Binance Real API keys first!');
                      e.target.checked = !newMode; // Revert checkbox
                      return;
                    }
                    if (!newMode && !confirm(t.profile.tradingMode?.realTradingWarning || '⚠️ WARNING: Real Trading uses REAL MONEY! Are you sure?')) {
                      e.target.checked = !newMode; // Revert checkbox
                      return;
                    }
                    try {
                      const { usersApi } = await import('../services/api');
                      await usersApi.updateTradingMode(newMode);
                      setSettings({
                        ...settings,
                        profile_info: { ...settings.profile_info, paper_trading: newMode }
                      });
                    } catch (error: any) {
                      console.error('Failed to update trading mode:', error);
                      alert(error.response?.data?.detail || 'Failed to update trading mode');
                      e.target.checked = !newMode; // Revert checkbox on error
                    }
                  }}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-cyber-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyber-warning"></div>
              </label>
            </div>
            
            {settings.profile_info?.paper_trading === false && (
              <div className="p-4 bg-cyber-danger/10 border border-cyber-danger rounded-lg">
                <p className="text-sm text-cyber-danger font-medium">
                  ⚠️ {t.profile.tradingMode?.realTradingActive || 'REAL TRADING MODE ACTIVE - Using REAL MONEY!'}
                </p>
              </div>
            )}
          </div>
        </motion.div>

        {/* SMTP Configuration */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-cyber-warning/20 rounded-lg">
              <Mail className="text-cyber-warning" size={24} />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold">{t.profile.smtp.title}</h2>
              <p className="text-sm text-cyber-muted">{t.profile.smtp.description}</p>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.smtp.enabled}
                onChange={(e) => setSettings({
                  ...settings,
                  smtp: { ...settings.smtp, enabled: e.target.checked }
                })}
                className="w-4 h-4 accent-cyber-primary"
              />
              <span className="text-sm">{t.profile.enabled}</span>
            </label>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-cyber-muted mb-2">{t.profile.smtp.host}</label>
                <input
                  type="text"
                  value={settings.smtp.host || ''}
                  onChange={(e) => setSettings({
                    ...settings,
                    smtp: { ...settings.smtp, host: e.target.value }
                  })}
                  className="input-cyber w-full"
                  placeholder={t.profile.smtp.hostPlaceholder}
                />
              </div>
              <div>
                <label className="block text-sm text-cyber-muted mb-2">{t.profile.smtp.port}</label>
                <input
                  type="number"
                  value={settings.smtp.port || ''}
                  onChange={(e) => setSettings({
                    ...settings,
                    smtp: { ...settings.smtp, port: parseInt(e.target.value) || null }
                  })}
                  className="input-cyber w-full"
                  placeholder={t.profile.smtp.portPlaceholder}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-cyber-muted mb-2">{t.profile.smtp.user}</label>
              <input
                type="email"
                value={settings.smtp.user || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  smtp: { ...settings.smtp, user: e.target.value }
                })}
                className="input-cyber w-full"
                placeholder={t.profile.smtp.userPlaceholder}
              />
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <label className="block text-sm text-cyber-muted">{t.profile.smtp.password}</label>
                <InfoTooltip
                  title={t.profile.smtp.password}
                  description={t.profile.smtp.passwordInfo}
                  example={t.profile.smtp.gmailInstructions}
                />
              </div>
              <div className="relative">
                <input
                  type={showPasswords.smtp_password ? 'text' : 'password'}
                  value={settings.smtp.password === '***' ? '' : (settings.smtp.password || '')}
                  onChange={(e) => setSettings({
                    ...settings,
                    smtp: { ...settings.smtp, password: e.target.value }
                  })}
                  className="input-cyber w-full pr-12"
                  placeholder="Contraseña de aplicación (16 caracteres)"
                />
                <button
                  type="button"
                  onClick={() => togglePasswordVisibility('smtp_password')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-cyber-muted hover:text-cyber-text"
                >
                  {showPasswords.smtp_password ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm text-cyber-muted mb-2">{t.profile.smtp.fromEmail}</label>
              <input
                type="email"
                value={settings.smtp.from_email || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  smtp: { ...settings.smtp, from_email: e.target.value }
                })}
                className="input-cyber w-full"
                placeholder={t.profile.smtp.fromEmailPlaceholder}
              />
            </div>

            <button
              onClick={handleTestEmail}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-cyber-warning/20 text-cyber-warning border border-cyber-warning/50 rounded-lg hover:bg-cyber-warning/30 transition-all"
            >
              <Send size={18} />
              {t.profile.testEmail}
            </button>

            {testResults.email && (
              <div className={`flex items-center gap-2 p-3 rounded-lg ${
                testResults.email.success 
                  ? 'bg-cyber-primary/20 text-cyber-primary' 
                  : 'bg-cyber-danger/20 text-cyber-danger'
              }`}>
                {testResults.email.success ? <CheckCircle size={18} /> : <XCircle size={18} />}
                <span className="text-sm">{testResults.email.message}</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* Telegram Configuration */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-cyber-accent/20 rounded-lg">
              <Send className="text-cyber-accent" size={24} />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold">{t.profile.telegram.title}</h2>
              <p className="text-sm text-cyber-muted">{t.profile.telegram.description}</p>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.telegram.enabled}
                onChange={(e) => setSettings({
                  ...settings,
                  telegram: { ...settings.telegram, enabled: e.target.checked }
                })}
                className="w-4 h-4 accent-cyber-primary"
              />
              <span className="text-sm">{t.profile.enabled}</span>
            </label>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-cyber-muted mb-2">{t.profile.telegram.botToken}</label>
              <div className="relative">
                <input
                  type={showPasswords.telegram_token ? 'text' : 'password'}
                  value={settings.telegram.bot_token === '***' ? '' : (settings.telegram.bot_token || '')}
                  onChange={(e) => setSettings({
                    ...settings,
                    telegram: { ...settings.telegram, bot_token: e.target.value }
                  })}
                  className="input-cyber w-full font-mono text-sm pr-12"
                  placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                />
                <button
                  type="button"
                  onClick={() => togglePasswordVisibility('telegram_token')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-cyber-muted hover:text-cyber-text"
                >
                  {showPasswords.telegram_token ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <label className="block text-sm text-cyber-muted">{t.profile.telegram.chatId}</label>
                <InfoTooltip
                  title={t.profile.telegram.chatId}
                  description={t.profile.telegram.chatIdInfo}
                  example={t.profile.telegram.chatIdExample}
                />
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={settings.telegram.chat_id || ''}
                  onChange={(e) => setSettings({
                    ...settings,
                    telegram: { ...settings.telegram, chat_id: e.target.value }
                  })}
                  className="input-cyber flex-1"
                  placeholder="123456789"
                />
                <button
                  type="button"
                  onClick={handleGetChatId}
                  disabled={!settings.telegram.bot_token || settings.telegram.bot_token === '***'}
                  className="px-4 py-2 bg-cyber-secondary/20 text-cyber-secondary border border-cyber-secondary/50 rounded-lg hover:bg-cyber-secondary/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm whitespace-nowrap"
                  title={!settings.telegram.bot_token || settings.telegram.bot_token === '***' ? t.profile.telegram.needBotTokenFirst : ''}
                >
                  {t.profile.telegram.getChatId}
                </button>
              </div>
              {testResults.chatId && (
                <div className={`mt-2 p-3 rounded-lg text-sm ${
                  testResults.chatId.success 
                    ? 'bg-cyber-primary/20 text-cyber-primary' 
                    : 'bg-cyber-warning/20 text-cyber-warning'
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    {testResults.chatId.success ? <CheckCircle size={16} /> : <XCircle size={16} />}
                    <span className="font-semibold">{testResults.chatId.message}</span>
                  </div>
                  {testResults.chatId.instructions && (
                    <div className="mt-2 text-xs space-y-1 pl-6">
                      {testResults.chatId.instructions.map((instruction: string, idx: number) => (
                        <div key={idx} className={instruction.startsWith('Option') || instruction.startsWith('Note:') ? 'font-semibold mt-2' : ''}>
                          {instruction}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleTestTelegram}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-cyber-accent/20 text-cyber-accent border border-cyber-accent/50 rounded-lg hover:bg-cyber-accent/30 transition-all"
              >
                <Send size={18} />
                {t.profile.testTelegram}
              </button>
              <button
                onClick={handleTestTelegramTrade}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-cyber-primary/20 text-cyber-primary border border-cyber-primary/50 rounded-lg hover:bg-cyber-primary/30 transition-all"
                title={t.profile.testTelegramTradeTooltip}
              >
                <Send size={18} />
                {t.profile.testTelegramTrade}
              </button>
            </div>

            {testResults.telegram && (
              <div className={`flex items-center gap-2 p-3 rounded-lg ${
                testResults.telegram.success 
                  ? 'bg-cyber-primary/20 text-cyber-primary' 
                  : 'bg-cyber-danger/20 text-cyber-danger'
              }`}>
                {testResults.telegram.success ? <CheckCircle size={18} /> : <XCircle size={18} />}
                <span className="text-sm">{testResults.telegram.message}</span>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

