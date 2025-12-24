import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  FileText, 
  RefreshCw, 
  Download, 
  Trash2,
  Server,
  Monitor,
  AlertTriangle,
  Activity,
  ChevronDown
} from 'lucide-react'
import { logsApi } from '../services/api'
import { logger } from '../services/logger'
import { useLanguage } from '../i18n'

type LogType = 'app' | 'error' | 'trades' | 'api' | 'deepseek' | 'email' | 'telegram'
type ViewMode = 'backend' | 'frontend'

interface BackendLogStats {
  files: Record<string, {
    size_kb: number
    lines: number
    errors: number
    warnings: number
  }>
}

export default function Logs() {
  const [viewMode, setViewMode] = useState<ViewMode>('backend')
  const [selectedLog, setSelectedLog] = useState<LogType>('app')
  const [logContent, setLogContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [lines, setLines] = useState(100)
  const [backendStats, setBackendStats] = useState<BackendLogStats | null>(null)
  const [frontendStats, setFrontendStats] = useState<any>(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const { t } = useLanguage()

  const logTypes: { key: LogType; label: string; icon: any; color: string }[] = [
    { key: 'app', label: t.logs.application, icon: Activity, color: 'cyber-primary' },
    { key: 'trades', label: t.logs.tradesLog, icon: FileText, color: 'cyber-secondary' },
    { key: 'error', label: t.logs.errors, icon: AlertTriangle, color: 'cyber-danger' },
    { key: 'api', label: t.logs.apiRequests, icon: Server, color: 'cyber-warning' },
    { key: 'deepseek', label: t.logs.deepseek || 'DeepSeek AI', icon: Activity, color: 'cyber-primary' },
    { key: 'email', label: t.logs.email || 'Email', icon: Monitor, color: 'cyber-secondary' },
    { key: 'telegram', label: t.logs.telegram || 'Telegram', icon: Server, color: 'cyber-warning' },
  ]

  useEffect(() => {
    if (viewMode === 'backend') {
      fetchBackendStats()
      fetchBackendLogs()
    } else {
      loadFrontendLogs()
    }
  }, [viewMode, selectedLog, lines])

  useEffect(() => {
    if (!autoRefresh) return
    
    const interval = setInterval(() => {
      if (viewMode === 'backend') {
        fetchBackendLogs()
      } else {
        loadFrontendLogs()
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [autoRefresh, viewMode, selectedLog])

  const fetchBackendStats = async () => {
    try {
      const res = await logsApi.stats()
      setBackendStats(res.data)
    } catch (error) {
      console.error('Failed to fetch backend stats:', error)
    }
  }

  const fetchBackendLogs = async () => {
    setLoading(true)
    try {
      const res = await logsApi.view(selectedLog, lines)
      setLogContent(res.data.content || 'No logs available')
    } catch (error) {
      setLogContent('Failed to fetch logs')
    } finally {
      setLoading(false)
    }
  }

  const loadFrontendLogs = () => {
    setFrontendStats(logger.getStats())
    setLogContent(logger.getLogsAsText(lines))
  }

  const handleRefresh = () => {
    if (viewMode === 'backend') {
      fetchBackendStats()
      fetchBackendLogs()
    } else {
      loadFrontendLogs()
    }
  }

  const handleDownload = () => {
    const blob = new Blob([logContent], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${viewMode}_${selectedLog}_logs_${new Date().toISOString().split('T')[0]}.log`
    a.click()
    URL.revokeObjectURL(url)
    logger.info(`Downloaded ${viewMode} ${selectedLog} logs`)
  }

  const handleClearFrontendLogs = () => {
    if (confirm(t.logs.clearConfirm)) {
      logger.clear()
      loadFrontendLogs()
    }
  }

  const getLogLineClass = (line: string) => {
    if (line.includes('| ERROR') || line.includes('[ERROR]')) return 'text-cyber-danger'
    if (line.includes('| WARNING') || line.includes('[WARN]')) return 'text-cyber-warning'
    if (line.includes('| INFO') || line.includes('[INFO]')) return 'text-cyber-primary'
    if (line.includes('✅') || line.includes('WIN')) return 'text-cyber-success'
    if (line.includes('❌') || line.includes('LOSS')) return 'text-cyber-danger'
    return 'text-cyber-muted'
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
          {t.logs.title}
        </motion.h1>
        
        <div className="flex items-center gap-4">
          {/* Auto Refresh Toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 accent-cyber-primary"
            />
            <span className="text-sm text-cyber-muted">{t.logs.autoRefresh}</span>
          </label>
          
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-cyber-card border border-cyber-border rounded-lg hover:border-cyber-primary transition-all"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            {t.common.refresh}
          </button>
          
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-2 bg-cyber-card border border-cyber-border rounded-lg hover:border-cyber-secondary transition-all"
          >
            <Download size={18} />
            {t.common.download}
          </button>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-4">
        <button
          onClick={() => setViewMode('backend')}
          className={`flex items-center gap-2 px-6 py-3 rounded-lg border transition-all ${
            viewMode === 'backend'
              ? 'bg-cyber-primary/20 border-cyber-primary text-cyber-primary'
              : 'border-cyber-border hover:border-cyber-muted'
          }`}
        >
          <Server size={20} />
          {t.logs.backendLogs}
        </button>
        <button
          onClick={() => setViewMode('frontend')}
          className={`flex items-center gap-2 px-6 py-3 rounded-lg border transition-all ${
            viewMode === 'frontend'
              ? 'bg-cyber-secondary/20 border-cyber-secondary text-cyber-secondary'
              : 'border-cyber-border hover:border-cyber-muted'
          }`}
        >
          <Monitor size={20} />
          {t.logs.frontendLogs}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar - Log Types */}
        <div className="space-y-4">
          {/* Stats Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-4"
          >
            <h3 className="text-sm font-medium mb-4 text-cyber-muted">
              {viewMode === 'backend' ? t.logs.backendLogs : t.logs.frontendLogs}
            </h3>
            
            {viewMode === 'backend' && backendStats?.files[selectedLog] && (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-cyber-muted">{t.logs.size}</span>
                  <span>{backendStats.files[selectedLog].size_kb} KB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-cyber-muted">{t.logs.lines}</span>
                  <span>{backendStats.files[selectedLog].lines}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-cyber-muted">{t.logs.errors}</span>
                  <span className="text-cyber-danger">{backendStats.files[selectedLog].errors}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-cyber-muted">{t.logs.warnings}</span>
                  <span className="text-cyber-warning">{backendStats.files[selectedLog].warnings}</span>
                </div>
              </div>
            )}
            
            {viewMode === 'frontend' && frontendStats && (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-cyber-muted">{t.logs.size}</span>
                  <span>{frontendStats.sizeKB} KB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-cyber-muted">Total</span>
                  <span>{frontendStats.total}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-cyber-muted">{t.logs.errors}</span>
                  <span className="text-cyber-danger">{frontendStats.byLevel.ERROR}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-cyber-muted">{t.logs.warnings}</span>
                  <span className="text-cyber-warning">{frontendStats.byLevel.WARN}</span>
                </div>
              </div>
            )}
          </motion.div>

          {/* Log Type Selector (Backend only) */}
          {viewMode === 'backend' && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-cyber-surface border border-cyber-border rounded-xl p-4"
            >
              <h3 className="text-sm font-medium mb-4 text-cyber-muted">{t.logs.logType}</h3>
              <div className="space-y-2">
                {logTypes.map((type) => (
                  <button
                    key={type.key}
                    onClick={() => setSelectedLog(type.key)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                      selectedLog === type.key
                        ? `bg-${type.color}/20 border border-${type.color}/50`
                        : 'hover:bg-cyber-card'
                    }`}
                  >
                    <type.icon size={18} className={`text-${type.color}`} />
                    <span>{type.label}</span>
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Lines Selector */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-4"
          >
            <h3 className="text-sm font-medium mb-4 text-cyber-muted">{t.logs.linesToShow}</h3>
            <select
              value={lines}
              onChange={(e) => setLines(Number(e.target.value))}
              className="w-full input-cyber"
            >
              <option value={50}>Last 50</option>
              <option value={100}>Last 100</option>
              <option value={250}>Last 250</option>
              <option value={500}>Last 500</option>
              <option value={1000}>Last 1000</option>
            </select>
          </motion.div>

          {/* Clear Frontend Logs */}
          {viewMode === 'frontend' && (
            <button
              onClick={handleClearFrontendLogs}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-cyber-danger/20 text-cyber-danger border border-cyber-danger/50 rounded-lg hover:bg-cyber-danger/30 transition-all"
            >
              <Trash2 size={18} />
              {t.logs.clearFrontendLogs}
            </button>
          )}
        </div>

        {/* Log Content */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="lg:col-span-3 bg-cyber-surface border border-cyber-border rounded-xl overflow-hidden"
        >
          <div className="p-4 border-b border-cyber-border flex items-center justify-between">
            <h3 className="font-medium">
              {viewMode === 'backend' ? `${selectedLog}.log` : 'Browser Console Logs'}
            </h3>
            {autoRefresh && (
              <span className="flex items-center gap-2 text-xs text-cyber-primary">
                <span className="w-2 h-2 bg-cyber-primary rounded-full pulse-live" />
                {t.logs.live}
              </span>
            )}
          </div>
          
          <div className="p-4 h-[600px] overflow-auto font-mono text-sm bg-cyber-bg">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <RefreshCw size={24} className="animate-spin text-cyber-primary" />
              </div>
            ) : logContent ? (
              <pre className="whitespace-pre-wrap">
                {logContent.split('\n').map((line, i) => (
                  <div key={i} className={`py-0.5 ${getLogLineClass(line)}`}>
                    {line}
                  </div>
                ))}
              </pre>
            ) : (
              <div className="flex items-center justify-center h-full text-cyber-muted">
                {t.logs.noLogsAvailable}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

