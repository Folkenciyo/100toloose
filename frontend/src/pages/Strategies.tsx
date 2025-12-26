import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Brain, 
  Plus, 
  Play, 
  Pause, 
  Trash2,
  TrendingUp,
  TrendingDown,
  X,
  RefreshCw,
  Clock,
  AlertCircle,
  Zap,
  Activity
} from 'lucide-react'
import { strategiesApi, botApi } from '../services/api'
import { useLanguage } from '../i18n'
import { InfoTooltip } from '../components/InfoTooltip'

interface SymbolStatus {
  symbol: string
  current_price: number
  has_open_trade: boolean
  open_trade_id: number | null
  open_trade_pnl: {
    value: number
    percent: number
    entry_price: number
    stop_loss: number
    take_profit: number
  } | null
  signal: {
    status: string
    message: string
    indicator?: string
    value?: number
    action?: string
  }
}

interface StrategyWithStatus {
  id: number
  name: string
  strategy_type: string
  description: string
  is_active: boolean
  is_paper_trading: boolean
  max_trade_amount: number
  stop_loss_percent: number
  take_profit_percent: number
  max_open_trades: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  total_profit_loss: number
  win_rate: number
  symbols: SymbolStatus[]
  waiting_reason: string
  last_trade_at: string | null
}

interface BotStatus {
  running: boolean
  active_symbols: string[]
  stats: {
    signals_detected: number
    trades_executed: number
    trades_skipped: number
    errors: number
  }
}

const POPULAR_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT']

export default function Strategies() {
  const [strategies, setStrategies] = useState<StrategyWithStatus[]>([])
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    strategy_type: 'rsi',
    description: '',
    symbols: ['BTCUSDT'],
    max_trade_amount: 100,
    stop_loss_percent: 2,
    take_profit_percent: 3,
    max_open_trades: 3,
  })
  const { t } = useLanguage()

  const STRATEGY_TYPES = [
    { 
      value: 'rsi', 
      label: t.strategies.types.rsi, 
      description: t.strategies.types.rsiDesc,
      info: t.strategies.types.rsiInfo,
      example: t.strategies.types.rsiExample
    },
    { 
      value: 'macd', 
      label: t.strategies.types.macd, 
      description: t.strategies.types.macdDesc,
      info: t.strategies.types.macdInfo,
      example: t.strategies.types.macdExample
    },
    { 
      value: 'bollinger', 
      label: t.strategies.types.bollinger, 
      description: t.strategies.types.bollingerDesc,
      info: t.strategies.types.bollingerInfo,
      example: t.strategies.types.bollingerExample
    },
    { 
      value: 'ema_cross', 
      label: t.strategies.types.emaCross, 
      description: t.strategies.types.emaCrossDesc,
      info: t.strategies.types.emaCrossInfo,
      example: t.strategies.types.emaCrossExample
    },
    { 
      value: 'combined', 
      label: t.strategies.types.combined, 
      description: t.strategies.types.combinedDesc,
      info: t.strategies.types.combinedInfo,
      example: t.strategies.types.combinedExample
    },
    { 
      value: 'scalping', 
      label: t.strategies.types.scalping, 
      description: t.strategies.types.scalpingDesc,
      info: t.strategies.types.scalpingInfo,
      example: t.strategies.types.scalpingExample
    },
  ]

  useEffect(() => {
    fetchData()
    // Auto-refresh cada 10 segundos
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [strategiesRes, botRes] = await Promise.all([
        strategiesApi.getAllWithStatus(),
        botApi.status()
      ])
      setStrategies(strategiesRes.data)
      setBotStatus(botRes.data)
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const handleRefresh = () => {
    setRefreshing(true)
    fetchData()
  }

  const handleCreate = async () => {
    try {
      await strategiesApi.create(formData)
      setShowCreateModal(false)
      setFormData({
        name: '',
        strategy_type: 'rsi',
        description: '',
        symbols: ['BTCUSDT'],
        max_trade_amount: 100,
        stop_loss_percent: 2,
        take_profit_percent: 3,
        max_open_trades: 3,
      })
      fetchData()
    } catch (error: any) {
      console.error('Failed to create strategy:', error)
      const errorMessage = error.response?.data?.detail || error.message || 'Error al crear la estrategia'
      alert(errorMessage)
    }
  }

  const handleToggleActive = async (strategy: StrategyWithStatus) => {
    try {
      if (strategy.is_active) {
        await strategiesApi.deactivate(strategy.id)
      } else {
        await strategiesApi.activate(strategy.id)
      }
      fetchData()
    } catch (error) {
      console.error('Failed to toggle strategy:', error)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm(t.strategies.deleteConfirm)) return
    try {
      await strategiesApi.delete(id)
      fetchData()
    } catch (error) {
      console.error('Failed to delete strategy:', error)
    }
  }

  const toggleSymbol = (symbol: string) => {
    setFormData(prev => ({
      ...prev,
      symbols: prev.symbols.includes(symbol)
        ? prev.symbols.filter(s => s !== symbol)
        : [...prev.symbols, symbol]
    }))
  }

  const getSignalColor = (status: string) => {
    switch (status) {
      case 'buy_signal': return 'text-cyber-primary'
      case 'sell_signal': return 'text-cyber-danger'
      case 'waiting': return 'text-cyber-warning'
      default: return 'text-cyber-muted'
    }
  }

  const getSignalIcon = (status: string) => {
    switch (status) {
      case 'buy_signal': return <TrendingUp size={14} className="text-cyber-primary" />
      case 'sell_signal': return <TrendingDown size={14} className="text-cyber-danger" />
      case 'waiting': return <Clock size={14} className="text-cyber-warning" />
      default: return <AlertCircle size={14} className="text-cyber-muted" />
    }
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <motion.h1 
          className="text-3xl font-display font-bold"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          {t.strategies.title}
        </motion.h1>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-cyber-card border border-cyber-border rounded-lg hover:border-cyber-primary transition-all"
          >
            <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 btn-primary"
          >
            <Plus size={20} />
            {t.strategies.createStrategy}
          </button>
        </div>
      </div>

      {/* Bot Status Banner */}
      {botStatus && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`p-4 rounded-xl border ${
            botStatus.running 
              ? 'bg-cyber-primary/10 border-cyber-primary/30' 
              : 'bg-cyber-danger/10 border-cyber-danger/30'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity size={24} className={botStatus.running ? 'text-cyber-primary' : 'text-cyber-danger'} />
              <div>
                <p className="font-semibold">
                  {botStatus.running ? `🤖 ${t.bot.active}` : `⏹️ ${t.bot.stopped}`}
                </p>
                <p className="text-sm text-cyber-muted">
                  {t.bot.symbols}: {botStatus.active_symbols?.length || 0} | 
                  {t.bot.signals}: {botStatus.stats?.signals_detected || 0} | 
                  {t.bot.trades}: {botStatus.stats?.trades_executed || 0}
                </p>
              </div>
            </div>
            {botStatus.running && (
              <span className="flex items-center gap-2 text-sm text-cyber-primary">
                <span className="w-2 h-2 bg-cyber-primary rounded-full pulse-live" />
                {t.bot.realtime}
              </span>
            )}
          </div>
        </motion.div>
      )}

      {/* Strategies Grid */}
      {strategies.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-12 text-center"
        >
          <Brain size={60} className="mx-auto mb-4 text-cyber-muted opacity-50" />
          <h2 className="text-xl font-semibold mb-2">{t.strategies.noStrategies}</h2>
          <p className="text-cyber-muted mb-6">
            {t.strategies.createFirstStrategy}
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary"
          >
            {t.strategies.createStrategy}
          </button>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {strategies.map((strategy, index) => (
            <motion.div
              key={strategy.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`bg-cyber-surface border rounded-xl overflow-hidden ${
                strategy.is_active 
                  ? 'border-cyber-primary glow-green' 
                  : 'border-cyber-border'
              }`}
            >
              {/* Header */}
              <div className="p-4 border-b border-cyber-border">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold">{strategy.name}</h3>
                      {strategy.strategy_type === 'scalping' && (
                        <Zap size={16} className="text-cyber-warning" />
                      )}
                    </div>
                    <p className="text-sm text-cyber-muted capitalize">
                      {strategy.strategy_type.replace('_', ' ')}
                    </p>
                  </div>
                  <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                    strategy.is_active 
                      ? 'bg-cyber-primary/20 text-cyber-primary' 
                      : 'bg-cyber-muted/20 text-cyber-muted'
                  }`}>
                    {strategy.is_active ? t.strategies.active : t.strategies.inactive}
                  </div>
                </div>
              </div>

              {/* Waiting Reason - NUEVO */}
              <div className={`px-4 py-3 text-sm ${
                strategy.waiting_reason.includes('Señal') 
                  ? 'bg-cyber-primary/10 text-cyber-primary'
                  : strategy.waiting_reason.includes('desactivada')
                  ? 'bg-cyber-muted/10 text-cyber-muted'
                  : 'bg-cyber-card text-cyber-text'
              }`}>
                {strategy.waiting_reason}
              </div>

              {/* Symbols Status */}
              <div className="p-4 border-b border-cyber-border">
                <p className="text-xs text-cyber-muted mb-2">{t.strategies.monitoredSymbols}:</p>
                <div className="space-y-2">
                  {strategy.symbols.map((sym) => (
                    <div key={sym.symbol} className="flex items-center justify-between bg-cyber-card rounded-lg p-2">
                      <div className="flex items-center gap-2">
                        {getSignalIcon(sym.signal?.status)}
                        <span className="font-medium">{sym.symbol}</span>
                        {sym.current_price && (
                          <span className="text-xs text-cyber-muted">
                            ${sym.current_price.toLocaleString()}
                          </span>
                        )}
                      </div>
                      <div className="text-right">
                        {sym.has_open_trade && sym.open_trade_pnl ? (
                          <span className={`text-sm font-medium ${
                            sym.open_trade_pnl.value >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                          }`}>
                            {sym.open_trade_pnl.value >= 0 ? '+' : ''}${sym.open_trade_pnl.value.toFixed(2)}
                            <span className="text-xs ml-1">
                              ({sym.open_trade_pnl.percent >= 0 ? '+' : ''}{sym.open_trade_pnl.percent.toFixed(2)}%)
                            </span>
                          </span>
                        ) : (
                          <span className={`text-xs ${getSignalColor(sym.signal?.status)}`}>
                            {sym.signal?.message?.substring(0, 30) || 'Analizando...'}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Stats */}
              <div className="p-4 grid grid-cols-4 gap-2 text-center">
                <div>
                  <p className="text-xs text-cyber-muted">{t.bot.trades}</p>
                  <p className="text-lg font-bold">{strategy.total_trades}</p>
                </div>
                <div>
                  <p className="text-xs text-cyber-muted">{t.dashboard.winRate}</p>
                  <p className="text-lg font-bold text-cyber-primary">
                    {strategy.win_rate.toFixed(0)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-cyber-muted">{t.trades.pnl}</p>
                  <p className={`text-lg font-bold ${
                    strategy.total_profit_loss >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                  }`}>
                    ${strategy.total_profit_loss.toFixed(0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-cyber-muted">Max</p>
                  <p className="text-lg font-bold">${strategy.max_trade_amount}</p>
                </div>
              </div>

              {/* Risk Settings */}
              <div className="px-4 pb-4">
                <div className="bg-cyber-card rounded-lg p-3 flex justify-between text-sm">
                  <span className="text-cyber-muted">SL: <span className="text-cyber-danger">{strategy.stop_loss_percent}%</span></span>
                  <span className="text-cyber-muted">TP: <span className="text-cyber-primary">{strategy.take_profit_percent}%</span></span>
                  <span className="text-cyber-muted">Max: {strategy.max_open_trades} trades</span>
                </div>
              </div>

              {/* Actions */}
              <div className="p-4 border-t border-cyber-border flex gap-2">
                <button
                  onClick={() => handleToggleActive(strategy)}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg transition-all ${
                    strategy.is_active
                      ? 'bg-cyber-warning/20 text-cyber-warning hover:bg-cyber-warning/30'
                      : 'bg-cyber-primary/20 text-cyber-primary hover:bg-cyber-primary/30'
                  }`}
                >
                  {strategy.is_active ? <Pause size={18} /> : <Play size={18} />}
                  {strategy.is_active ? t.strategies.pause : t.strategies.activate}
                </button>
                <button
                  onClick={() => handleDelete(strategy.id)}
                  disabled={strategy.is_active}
                  className="p-2 rounded-lg bg-cyber-danger/20 text-cyber-danger hover:bg-cyber-danger/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => setShowCreateModal(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">{t.strategies.createStrategy}</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-cyber-muted hover:text-cyber-text">
                <X size={24} />
              </button>
            </div>

            <div className="space-y-5">
              {/* Name */}
              <div>
                <label className="block text-sm text-cyber-muted mb-2">{t.strategies.strategyName}</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder={t.strategies.strategyName}
                  className="input-cyber w-full"
                />
              </div>

              {/* Type */}
              <div>
                <label className="block text-sm text-cyber-muted mb-2">{t.strategies.strategyType}</label>
                <div className="space-y-2">
                  {STRATEGY_TYPES.map((type) => (
                    <button
                      key={type.value}
                      onClick={() => setFormData({ ...formData, strategy_type: type.value })}
                      className={`w-full text-left p-3 rounded-lg border transition-all relative ${
                        formData.strategy_type === type.value
                          ? 'border-cyber-primary bg-cyber-primary/10'
                          : 'border-cyber-border hover:border-cyber-muted'
                      } ${type.value === 'scalping' ? 'border-cyber-warning/50' : ''}`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{type.label}</p>
                            <InfoTooltip 
                              title={type.label}
                              description={type.info}
                              example={type.example}
                            />
                          </div>
                          <p className="text-xs text-cyber-muted mt-1">{type.description}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Symbols */}
              <div>
                <label className="block text-sm text-cyber-muted mb-2">{t.strategies.tradingPairs}</label>
                <div className="flex flex-wrap gap-2">
                  {POPULAR_SYMBOLS.map((symbol) => (
                    <button
                      key={symbol}
                      onClick={() => toggleSymbol(symbol)}
                      className={`px-3 py-2 rounded-lg border transition-all ${
                        formData.symbols.includes(symbol)
                          ? 'border-cyber-primary bg-cyber-primary/20 text-cyber-primary'
                          : 'border-cyber-border hover:border-cyber-muted'
                      }`}
                    >
                      {symbol}
                    </button>
                  ))}
                </div>
              </div>

              {/* Trade Amount */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm text-cyber-muted">{t.strategies.maxTradeAmount}</label>
                  <InfoTooltip 
                    title={t.strategies.maxTradeAmount}
                    description={t.strategies.maxTradeAmountInfo}
                    example={t.strategies.maxTradeAmountExample}
                  />
                </div>
                <input
                  type="number"
                  value={formData.max_trade_amount}
                  onChange={(e) => setFormData({ ...formData, max_trade_amount: parseFloat(e.target.value) })}
                  className="input-cyber w-full"
                />
              </div>

              {/* Risk Settings */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <label className="block text-sm text-cyber-muted">{t.strategies.stopLoss}</label>
                    <InfoTooltip 
                      title={t.strategies.stopLoss}
                      description={t.strategies.stopLossInfo}
                      example={t.strategies.stopLossExample}
                    />
                  </div>
                  <input
                    type="number"
                    value={formData.stop_loss_percent}
                    onChange={(e) => {
                      const value = parseFloat(e.target.value) || 0
                      if (value >= 0.1 && value <= 50) {
                        setFormData({ ...formData, stop_loss_percent: value })
                      }
                    }}
                    className="input-cyber w-full"
                    step="0.1"
                    min="0.1"
                    max="50"
                  />
                  {formData.stop_loss_percent < 0.1 && (
                    <p className="text-xs text-cyber-danger mt-1">
                      ⚠️ Mínimo 0.1% (considera volatilidad y comisiones)
                    </p>
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <label className="block text-sm text-cyber-muted">{t.strategies.takeProfit}</label>
                    <InfoTooltip 
                      title={t.strategies.takeProfit}
                      description={t.strategies.takeProfitInfo}
                      example={t.strategies.takeProfitExample}
                    />
                  </div>
                  <input
                    type="number"
                    value={formData.take_profit_percent}
                    onChange={(e) => {
                      const value = parseFloat(e.target.value) || 0
                      if (value >= 0.1 && value <= 100) {
                        setFormData({ ...formData, take_profit_percent: value })
                      }
                    }}
                    className="input-cyber w-full"
                    step="0.1"
                    min="0.1"
                    max="100"
                  />
                  {formData.take_profit_percent < 0.1 && (
                    <p className="text-xs text-cyber-danger mt-1">
                      ⚠️ Mínimo 0.1% (considera volatilidad y comisiones)
                    </p>
                  )}
                </div>
              </div>

              {/* Max Open Trades */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <label className="block text-sm text-cyber-muted">{t.strategies.maxOpenTrades}</label>
                  <InfoTooltip 
                    title={t.strategies.maxOpenTrades}
                    description={t.strategies.maxOpenTradesInfo}
                    example={t.strategies.maxOpenTradesExample}
                  />
                </div>
                <input
                  type="number"
                  value={formData.max_open_trades}
                  onChange={(e) => setFormData({ ...formData, max_open_trades: parseInt(e.target.value) })}
                  className="input-cyber w-full"
                  min="1"
                  max="10"
                />
              </div>

              {formData.strategy_type === 'scalping' && (
                <div className="bg-cyber-warning/20 border border-cyber-warning/50 rounded-lg p-4">
                  <p className="text-sm text-cyber-warning">
                    ⚠️ <strong>Scalping</strong> {t.strategies.scalpingWarning}
                  </p>
                </div>
              )}

              <button
                onClick={handleCreate}
                disabled={!formData.name || formData.symbols.length === 0}
                className="w-full btn-primary py-4"
              >
                {t.strategies.createStrategy}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  )
}
