import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  DollarSign,
  Target,
  Zap,
  Clock,
  BarChart3,
  CheckCircle,
  Settings,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  PlayCircle,
  PauseCircle
} from 'lucide-react'
import { dashboardApi, tradesApi, deepseekApi } from '../services/api'
import { useLanguage, interpolate } from '../i18n'

interface DashboardData {
  user: {
    username: string
    paper_trading: boolean
    trading_mode?: string  // "Paper Trading (Testnet)" o "Real Trading"
    binance_mode?: string  // "Testnet" o "Real"
    initial_balance: number
    current_balance: number
    balance_synced?: boolean  // Indica si el balance viene de Binance
    profit_loss: number
    profit_loss_percent: number
  }
  trades: {
    total: number
    open: number
    closed: number
    winning: number
    losing: number
    win_rate: number
  }
  performance: {
    total_profit_loss: number
    best_trade: number
    worst_trade: number
  }
  strategies?: Array<{
    id: number
    name: string
    type: string
    symbols: string[]
    is_active: boolean
    stats: {
      total_trades: number
      open_trades: number
      closed_trades: number
      winning_trades: number
      losing_trades: number
      win_rate: number
      total_profit_loss: number
      avg_profit_loss: number
    }
    config: {
      max_trade_amount: number
      stop_loss_percent: number
      take_profit_percent: number
      max_open_trades: number
    }
    last_trade_at: string | null
    created_at: string | null
  }>
}

interface Trade {
  id: number
  symbol: string
  trade_type: string
  status: string
  entry_price: number
  exit_price: number | null
  quantity: number
  profit_loss: number
  profit_loss_percent: number
  strategy_name: string
  created_at: string
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [recentTrades, setRecentTrades] = useState<Trade[]>([])
  const [deepseekDecisions, setDeepseekDecisions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const { t } = useLanguage()

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [dashboardRes, tradesRes, deepseekRes] = await Promise.all([
          dashboardApi.get(),
          tradesApi.getAll(),
          deepseekApi.getDecisions(5, 0, true).catch(() => ({ data: { decisions: [] } }))
        ])
        console.log('Dashboard data:', dashboardRes.data)
        console.log('Strategies:', dashboardRes.data.strategies)
        console.log('Strategies length:', dashboardRes.data.strategies?.length || 0)
        setData(dashboardRes.data)
        setRecentTrades(tradesRes.data.slice(0, 5))
        setDeepseekDecisions(deepseekRes.data.decisions || [])
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

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

  const stats = [
    {
      label: t.dashboard.totalBalance,
      value: `$${data?.user.current_balance.toLocaleString() || '0'}`,
      change: data?.user.profit_loss_percent || 0,
      icon: DollarSign,
      color: 'cyber-primary'
    },
    {
      label: t.dashboard.totalPnL,
      value: `$${data?.performance.total_profit_loss.toLocaleString() || '0'}`,
      change: data?.user.profit_loss_percent || 0,
      icon: data?.performance.total_profit_loss >= 0 ? TrendingUp : TrendingDown,
      color: data?.performance.total_profit_loss >= 0 ? 'cyber-primary' : 'cyber-danger'
    },
    {
      label: t.dashboard.winRate,
      value: `${data?.trades.win_rate || 0}%`,
      icon: Target,
      color: 'cyber-secondary'
    },
    {
      label: t.dashboard.openTrades,
      value: data?.trades.open || 0,
      icon: Activity,
      color: 'cyber-warning'
    },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <motion.h1 
            className="text-3xl font-display font-bold"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            {t.dashboard.title}
          </motion.h1>
          <p className="text-cyber-muted mt-1">
            {interpolate(t.dashboard.welcomeUser, { username: data?.user.username || '' })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-2 bg-cyber-card rounded-lg border border-cyber-border">
            <span className={`w-2 h-2 rounded-full pulse-live ${data?.user.paper_trading ? 'bg-cyber-warning' : 'bg-cyber-danger'}`} />
            <span className="text-sm font-medium">
              {data?.user.trading_mode || (data?.user.paper_trading ? t.nav.paperTrading : t.nav.liveTrading)}
            </span>
          </div>
          {data?.user.balance_synced && (
            <div className="flex items-center gap-2 px-3 py-2 bg-cyber-success/20 rounded-lg border border-cyber-success/50">
              <CheckCircle size={16} className="text-cyber-success" />
              <span className="text-xs text-cyber-success">
                {data?.user.binance_mode === 'Testnet' ? 'Synced with Testnet' : 'Synced with Binance'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-6 card-hover"
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-cyber-muted text-sm">{stat.label}</span>
              <stat.icon className={`text-${stat.color}`} size={20} />
            </div>
            <p className={`text-2xl font-bold text-${stat.color}`}>
              {stat.value}
            </p>
            {stat.change !== undefined && (
              <p className={`text-sm mt-2 ${stat.change >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'}`}>
                {stat.change >= 0 ? '+' : ''}{stat.change.toFixed(2)}%
              </p>
            )}
          </motion.div>
        ))}
      </div>

      {/* Performance Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trade Summary */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
            <BarChart3 className="text-cyber-secondary" size={20} />
            {t.dashboard.tradeSummary}
          </h2>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-cyber-muted">{t.dashboard.totalTrades}</span>
              <span className="font-bold">{data?.trades.total || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-cyber-muted">{t.dashboard.winningTrades}</span>
              <span className="font-bold text-cyber-primary">{data?.trades.winning || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-cyber-muted">{t.dashboard.losingTrades}</span>
              <span className="font-bold text-cyber-danger">{data?.trades.losing || 0}</span>
            </div>
            <div className="h-px bg-cyber-border my-4" />
            <div className="flex justify-between items-center">
              <span className="text-cyber-muted">{t.dashboard.bestTrade}</span>
              <span className="font-bold text-cyber-primary">
                +${data?.performance.best_trade.toFixed(2) || '0.00'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-cyber-muted">{t.dashboard.worstTrade}</span>
              <span className="font-bold text-cyber-danger">
                ${data?.performance.worst_trade.toFixed(2) || '0.00'}
              </span>
            </div>
          </div>
        </motion.div>

        {/* Recent Trades */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
            <Clock className="text-cyber-secondary" size={20} />
            {t.dashboard.recentTrades}
          </h2>
          {recentTrades.length === 0 ? (
            <div className="text-center py-8 text-cyber-muted">
              <Zap size={40} className="mx-auto mb-4 opacity-50" />
              <p>{t.dashboard.noTradesYet}</p>
              <p className="text-sm mt-1">{t.dashboard.startTradingToSee}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentTrades.map((trade) => (
                <div
                  key={trade.id}
                  className="flex items-center justify-between p-3 bg-cyber-card rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${
                      trade.trade_type === 'buy' 
                        ? 'bg-cyber-primary/20 text-cyber-primary' 
                        : 'bg-cyber-danger/20 text-cyber-danger'
                    }`}>
                      {trade.trade_type === 'buy' ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                    </div>
                    <div>
                      <p className="font-medium">{trade.symbol}</p>
                      <p className="text-xs text-cyber-muted">
                        {trade.strategy_name || t.trades.manual}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`font-medium ${
                      trade.profit_loss >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                    }`}>
                      {trade.profit_loss >= 0 ? '+' : ''}${trade.profit_loss.toFixed(2)}
                    </p>
                    <p className="text-xs text-cyber-muted">
                      {trade.status}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* DeepSeek Decisions */}
        {deepseekDecisions.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
          >
            <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
              <Zap className="text-cyber-primary" size={20} />
              {t.dashboard.deepseekDecisions || 'DeepSeek AI Decisions'}
            </h2>
            <div className="space-y-3">
              {deepseekDecisions.map((decision) => (
                <div
                  key={decision.id}
                  className="p-4 bg-cyber-card rounded-lg border border-cyber-border"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium">{decision.symbol}</p>
                      <p className="text-xs text-cyber-muted">
                        {new Date(decision.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                      decision.recommendation === 'STRONG_BUY' || decision.recommendation === 'BUY'
                        ? 'bg-cyber-primary/20 text-cyber-primary'
                        : decision.recommendation === 'STRONG_SELL' || decision.recommendation === 'SELL'
                        ? 'bg-cyber-danger/20 text-cyber-danger'
                        : 'bg-cyber-muted/20 text-cyber-muted'
                    }`}>
                      {decision.recommendation}
                    </div>
                  </div>
                  <div className="mt-3 space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-cyber-muted">Confidence:</span>
                      <span className="font-medium">{(decision.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-cyber-muted">Risk:</span>
                      <span className={`font-medium ${
                        decision.risk_assessment === 'LOW' ? 'text-cyber-primary' :
                        decision.risk_assessment === 'MEDIUM' ? 'text-cyber-warning' :
                        'text-cyber-danger'
                      }`}>
                        {decision.risk_assessment}
                      </span>
                    </div>
                    <div className="mt-2 pt-2 border-t border-cyber-border">
                      <p className="text-xs text-cyber-muted line-clamp-2">
                        {decision.reasoning}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>

      {/* Active Strategies Summary */}
      {data && data.strategies && data.strategies.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6 mt-6"
        >
          <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
            <Settings className="text-cyber-secondary" size={24} />
            {t.dashboard.activeStrategies || 'Active Strategies'}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.strategies.map((strategy, index) => (
              <motion.div
                key={strategy.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 + (index * 0.1) }}
                className="bg-cyber-card border border-cyber-border rounded-xl p-5 hover:border-cyber-primary/50 transition-colors"
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-bold text-lg">{strategy.name}</h3>
                      {strategy.is_active ? (
                        <PlayCircle className="text-cyber-primary" size={18} />
                      ) : (
                        <PauseCircle className="text-cyber-muted" size={18} />
                      )}
                    </div>
                    <p className="text-xs text-cyber-muted uppercase">{strategy.type}</p>
                  </div>
                </div>

                {/* Symbols */}
                <div className="mb-4">
                  <p className="text-xs text-cyber-muted mb-2">Symbols:</p>
                  <div className="flex flex-wrap gap-2">
                    {strategy.symbols.slice(0, 3).map((symbol, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-cyber-primary/20 text-cyber-primary rounded text-xs font-medium"
                      >
                        {symbol}
                      </span>
                    ))}
                    {strategy.symbols.length > 3 && (
                      <span className="px-2 py-1 bg-cyber-muted/20 text-cyber-muted rounded text-xs">
                        +{strategy.symbols.length - 3}
                      </span>
                    )}
                  </div>
                </div>

                {/* Stats */}
                <div className="space-y-3 mb-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-cyber-muted">Total Trades</span>
                    <span className="font-bold">{strategy.stats.total_trades}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-cyber-muted">Open Trades</span>
                    <span className="font-bold text-cyber-warning">{strategy.stats.open_trades}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-cyber-muted">Win Rate</span>
                    <span className={`font-bold ${
                      strategy.stats.win_rate >= 50 ? 'text-cyber-primary' : 'text-cyber-danger'
                    }`}>
                      {strategy.stats.win_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-cyber-muted">Total P&L</span>
                    <span className={`font-bold flex items-center gap-1 ${
                      strategy.stats.total_profit_loss >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                    }`}>
                      {strategy.stats.total_profit_loss >= 0 ? (
                        <TrendingUpIcon size={16} />
                      ) : (
                        <TrendingDownIcon size={16} />
                      )}
                      ${strategy.stats.total_profit_loss.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Divider */}
                <div className="h-px bg-cyber-border my-4" />

                {/* Performance Summary */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-cyber-muted mb-1">Wins</p>
                    <p className="font-bold text-cyber-primary">{strategy.stats.winning_trades}</p>
                  </div>
                  <div>
                    <p className="text-cyber-muted mb-1">Losses</p>
                    <p className="font-bold text-cyber-danger">{strategy.stats.losing_trades}</p>
                  </div>
                  <div>
                    <p className="text-cyber-muted mb-1">Avg P&L</p>
                    <p className={`font-bold ${
                      strategy.stats.avg_profit_loss >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                    }`}>
                      ${strategy.stats.avg_profit_loss.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-cyber-muted mb-1">Max Trade</p>
                    <p className="font-bold">${strategy.config.max_trade_amount.toFixed(0)}</p>
                  </div>
                </div>

                {/* Last Trade */}
                {strategy.last_trade_at && (
                  <div className="mt-4 pt-4 border-t border-cyber-border">
                    <p className="text-xs text-cyber-muted">
                      Last trade: {new Date(strategy.last_trade_at).toLocaleString()}
                    </p>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {/* No Active Strategies Message */}
      {data && (!data.strategies || data.strategies.length === 0) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-8 text-center"
        >
          <Settings size={48} className="mx-auto mb-4 text-cyber-muted opacity-50" />
          <h3 className="text-lg font-semibold mb-2">{t.dashboard.noActiveStrategies || 'No Active Strategies'}</h3>
          <p className="text-cyber-muted">
            {t.dashboard.createStrategyToStart || 'Create and activate a strategy to start trading'}
          </p>
        </motion.div>
      )}
    </div>
  )
}

