import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { DollarSign, RefreshCw, TrendingUp } from 'lucide-react'
import { dashboardApi } from '../services/api'
import { useLanguage } from '../i18n'

interface BalanceBreakdown {
  asset: string
  amount: number
  value_usdt: number
  free: number
  locked: number
}

interface DashboardData {
  user: {
    current_balance: number
    balance_breakdown?: BalanceBreakdown[]
    balance_synced?: boolean
    trading_mode?: string
    binance_mode?: string
  }
}

export default function BalanceDistribution() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const { t } = useLanguage()

  const fetchData = async () => {
    try {
      setRefreshing(true)
      const response = await dashboardApi.get()
      setData(response.data)
    } catch (error) {
      console.error('Failed to fetch balance distribution:', error)
      alert('Error al cargar la distribución de balance. Por favor, recarga la página.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
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

  const balanceBreakdown = data?.user.balance_breakdown || []
  const totalBalance = data?.user.current_balance || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <motion.h1 
            className="text-3xl font-display font-bold"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            {t.balanceDistribution.title}
          </motion.h1>
          <p className="text-cyber-muted mt-1">
            {t.balanceDistribution.subtitle}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data?.user.balance_synced && (
            <div className="flex items-center gap-2 px-3 py-2 bg-cyber-success/20 rounded-lg border border-cyber-success/50">
              <span className="text-xs text-cyber-success">
                {data.user.binance_mode === 'Testnet' ? 'Sincronizado con Testnet' : 'Sincronizado con Binance'}
              </span>
            </div>
          )}
          <button
            onClick={fetchData}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-cyber-card border border-cyber-border rounded-lg hover:border-cyber-primary transition-all disabled:opacity-50"
          >
            <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
            {t.balanceDistribution.refresh}
          </button>
        </div>
      </div>

      {/* Total Balance Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-cyber-muted mb-2">{t.balanceDistribution.totalBalance}</p>
            <p className="text-4xl font-bold text-cyber-primary">
              ${totalBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: true })}
            </p>
          </div>
          <div className="w-16 h-16 rounded-full bg-cyber-primary/20 flex items-center justify-center">
            <DollarSign className="text-cyber-primary" size={32} />
          </div>
        </div>
      </motion.div>

      {/* Balance Breakdown */}
      {balanceBreakdown.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-12 text-center"
        >
          <DollarSign size={60} className="mx-auto mb-4 text-cyber-muted opacity-50" />
          <h2 className="text-xl font-semibold mb-2">{t.balanceDistribution.noData}</h2>
          <p className="text-cyber-muted">
            {t.balanceDistribution.noDataDescription}
          </p>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
        >
          <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
            <TrendingUp className="text-cyber-primary" size={20} />
            {t.balanceDistribution.breakdown}
          </h2>
          <div className="space-y-3">
            {balanceBreakdown.map((asset, index) => {
              const percentage = totalBalance > 0 ? (asset.value_usdt / totalBalance) * 100 : 0
              return (
                <motion.div
                  key={asset.asset}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="p-4 bg-cyber-card rounded-lg border border-cyber-border hover:border-cyber-primary/50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-cyber-primary/20 flex items-center justify-center font-bold text-cyber-primary text-lg">
                        {asset.asset.substring(0, 2)}
                      </div>
                      <div>
                        <p className="font-semibold text-lg">{asset.asset}</p>
                        <p className="text-xs text-cyber-muted">
                          {asset.amount.toFixed(8)} {asset.asset}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-cyber-primary text-lg">
                        ${asset.value_usdt.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: true })}
                      </p>
                      <p className="text-xs text-cyber-muted">
                        {percentage.toFixed(2)}%
                      </p>
                    </div>
                  </div>
                  {/* Progress bar */}
                  <div className="w-full bg-cyber-border rounded-full h-2 mt-3">
                    <motion.div
                      className="bg-cyber-primary h-2 rounded-full transition-all"
                      initial={{ width: 0 }}
                      animate={{ width: `${percentage}%` }}
                      transition={{ duration: 0.5, delay: index * 0.05 }}
                    />
                  </div>
                  {asset.locked > 0 && (
                    <div className="mt-3 pt-3 border-t border-cyber-border flex justify-between text-xs text-cyber-muted">
                      <span>{t.balanceDistribution.free}: {asset.free.toFixed(8)}</span>
                      <span>{t.balanceDistribution.locked}: {asset.locked.toFixed(8)}</span>
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      )}
    </div>
  )
}

