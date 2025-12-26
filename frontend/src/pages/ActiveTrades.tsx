import { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { 
  TrendingUp, 
  TrendingDown, 
  Zap,
  Clock,
  X,
  Loader2,
  Wifi,
  WifiOff
} from 'lucide-react'
import { tradesApi } from '../services/api'
import { useLanguage } from '../i18n'
import { wsService } from '../services/websocket'

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
  stop_loss?: number | null
  take_profit?: number | null
  // Campos adicionales para trades abiertos
  current_price?: number | null
  current_value?: number | null
  current_pnl?: number | null
  current_pnl_percent?: number | null
  invested_value?: number | null
}

export default function ActiveTrades() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [closingTradeId, setClosingTradeId] = useState<number | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const { t } = useLanguage()
  const priceUpdateUnsubscribeRef = useRef<(() => void) | null>(null)

  const fetchTrades = async () => {
    try {
      const res = await tradesApi.getAll()
      // Filtrar trades que no estén cerrados (open, pending, cancelled, failed)
      const nonClosedTrades = res.data.filter((trade: Trade) => trade.status !== 'closed')
      setTrades(nonClosedTrades)
      
      // Suscribir a símbolos de trades abiertos
      const openTrades = nonClosedTrades.filter((t: Trade) => t.status === 'open')
      if (openTrades.length > 0 && wsService.isConnected()) {
        const symbols = openTrades.map((t: Trade) => t.symbol)
        wsService.subscribe(symbols)
      }
    } catch (error) {
      console.error('Failed to fetch trades:', error)
    } finally {
      setLoading(false)
    }
  }

  // Actualizar P&L cuando llega un precio nuevo
  const updateTradePrice = (symbol: string, price: number) => {
    setTrades(prevTrades => {
      return prevTrades.map(trade => {
        if (trade.symbol === symbol && trade.status === 'open') {
          // NUNCA actualizar entry_price - es el precio al que se compró
          // Si entry_price es 0 o null, usar el invested_value original si existe
          // Si no, calcular con el entry_price original (aunque sea 0)
          const entryPrice = trade.entry_price && trade.entry_price > 0 
            ? trade.entry_price 
            : (trade.invested_value && trade.quantity && trade.quantity > 0 
                ? trade.invested_value / trade.quantity 
                : 0)
          
          const quantity = trade.quantity || 0
          
          // Si tenemos un invested_value original, usarlo; si no, calcular con entry_price
          let investedValue = trade.invested_value && trade.invested_value > 0
            ? trade.invested_value
            : (entryPrice > 0 ? entryPrice * quantity : 0)
          
          const currentValue = price * quantity
          
          let currentPnl = 0
          let currentPnlPercent = 0
          
          if (trade.trade_type === 'buy') {
            currentPnl = currentValue - investedValue
            if (investedValue > 0 && entryPrice > 0) {
              currentPnlPercent = ((price - entryPrice) / entryPrice) * 100
            }
          } else { // SELL
            currentPnl = investedValue - currentValue
            if (investedValue > 0 && entryPrice > 0) {
              currentPnlPercent = ((entryPrice - price) / entryPrice) * 100
            }
          }
          
          return {
            ...trade,
            // NUNCA actualizar entry_price - mantener el original
            entry_price: trade.entry_price, // Mantener el valor original
            current_price: price,
            current_value: currentValue,
            current_pnl: currentPnl,
            current_pnl_percent: currentPnlPercent,
            invested_value: investedValue // Puede cambiar si entry_price era 0, pero entry_price no
          }
        }
        return trade
      })
    })
  }

  useEffect(() => {
    // Conectar al WebSocket
    wsService.connect()
    
    // Verificar conexión periódicamente
    const checkConnection = setInterval(() => {
      setWsConnected(wsService.isConnected())
    }, 1000)
    
    // Registrar callback para actualizaciones de precios
    const unsubscribe = wsService.onPriceUpdate((symbol, price) => {
      updateTradePrice(symbol, price)
    })
    priceUpdateUnsubscribeRef.current = unsubscribe
    
    // Cargar trades iniciales
    fetchTrades()
    
    // Actualizar cada 30 segundos como fallback (por si falla el websocket)
    const interval = setInterval(fetchTrades, 30000)
    
    return () => {
      clearInterval(interval)
      clearInterval(checkConnection)
      if (priceUpdateUnsubscribeRef.current) {
        priceUpdateUnsubscribeRef.current()
      }
    }
  }, [])

  const handleCloseTrade = async (tradeId: number) => {
    if (!confirm('¿Estás seguro de que quieres cerrar este trade? Se ejecutará una orden de venta/compra en Binance al precio actual de mercado.')) {
      return
    }

    setClosingTradeId(tradeId)
    try {
      await tradesApi.closeTrade(tradeId)
      // Recargar trades después de cerrar
      await fetchTrades()
      alert('✅ Trade cerrado exitosamente. La orden se ha ejecutado en Binance.')
    } catch (error: any) {
      console.error('Failed to close trade:', error)
      const errorMsg = error.response?.data?.detail || error.message || 'Error desconocido'
      alert(`❌ Error al cerrar el trade: ${errorMsg}`)
    } finally {
      setClosingTradeId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyber-muted">{t.common.loading}</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-3xl font-display font-bold flex items-center gap-3">
            <Clock className="text-cyber-primary" size={32} />
            {t.activeTrades.title}
          </h1>
          <p className="text-cyber-muted mt-2 flex items-center gap-2">
            {t.activeTrades.description}
            {wsConnected ? (
              <span className="flex items-center gap-1 text-cyber-primary text-xs">
                <Wifi size={14} />
                <span>Actualización en tiempo real</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-cyber-muted text-xs">
                <WifiOff size={14} />
                <span>Modo offline (actualización cada 30s)</span>
              </span>
            )}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-cyber-muted">{t.activeTrades.totalOpen}</p>
          <p className="text-2xl font-bold text-cyber-primary">{trades.length}</p>
          <p className="text-xs text-cyber-muted mt-1">
            {trades.filter((t: Trade) => t.status === 'open').length} abiertos
          </p>
        </div>
      </motion.div>

      {/* Trades List */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
      >
        {trades.length === 0 ? (
          <div className="text-center py-12 text-cyber-muted">
            <Zap size={48} className="mx-auto mb-4 opacity-50" />
            <p className="text-lg">{t.activeTrades.noOpenTrades}</p>
            <p className="text-sm mt-2">{t.activeTrades.startTradingToSee}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {trades.map((trade) => {
              const isOpen = trade.status === 'open'
              const pnl = isOpen && trade.current_pnl !== undefined && trade.current_pnl !== null 
                ? trade.current_pnl 
                : (trade.profit_loss !== undefined && trade.profit_loss !== null ? trade.profit_loss : 0)
              const pnlPercent = isOpen && trade.current_pnl_percent !== undefined && trade.current_pnl_percent !== null
                ? trade.current_pnl_percent 
                : (trade.profit_loss_percent !== undefined && trade.profit_loss_percent !== null ? trade.profit_loss_percent : 0)
              const currentPrice = isOpen && trade.current_price ? trade.current_price : null
              // Calcular invested_value: usar el valor del backend si existe, sino calcularlo
              let investedValue = 0
              if (isOpen && trade.invested_value !== undefined && trade.invested_value !== null && trade.invested_value > 0) {
                investedValue = trade.invested_value
              } else if (trade.entry_price && trade.entry_price > 0 && trade.quantity && trade.quantity > 0) {
                investedValue = trade.entry_price * trade.quantity
              }
              // Si no hay entry_price válido, investedValue queda en 0 (no usar precio actual)
              const currentValue = isOpen && trade.current_value ? trade.current_value : null
              
              return (
                <motion.div
                  key={trade.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-5 bg-cyber-card rounded-lg border border-cyber-border hover:border-cyber-primary/50 transition-all"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${
                        trade.trade_type === 'buy' 
                          ? 'bg-cyber-primary/20 text-cyber-primary' 
                          : 'bg-cyber-danger/20 text-cyber-danger'
                      }`}>
                        {trade.trade_type === 'buy' ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                      </div>
                      <div>
                        <p className="font-bold text-xl">{trade.symbol}</p>
                        <p className="text-sm text-cyber-muted">
                          {trade.strategy_name || t.trades.manual}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`font-bold text-2xl ${
                        pnl >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                      }`}>
                        {pnl >= 0 ? '+' : ''}${(pnl || 0).toFixed(2)}
                      </p>
                      <p className={`text-lg font-medium ${
                        pnlPercent >= 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                      }`}>
                        {pnlPercent >= 0 ? '+' : ''}{(pnlPercent || 0).toFixed(2)}%
                      </p>
                      <p className={`text-xs uppercase mb-3 ${
                        trade.status === 'open' ? 'text-cyber-primary' :
                        trade.status === 'pending' ? 'text-cyber-secondary' :
                        trade.status === 'cancelled' ? 'text-cyber-muted' :
                        'text-cyber-danger'
                      }`}>
                        {trade.status === 'open' ? 'Abierto' :
                         trade.status === 'pending' ? 'Pendiente' :
                         trade.status === 'cancelled' ? 'Cancelado' :
                         trade.status === 'failed' ? 'Fallido' :
                         trade.status}
                      </p>
                      {trade.status === 'open' && (
                        <button
                          onClick={() => handleCloseTrade(trade.id)}
                          disabled={closingTradeId === trade.id}
                          className="px-4 py-2 bg-cyber-danger/20 hover:bg-cyber-danger/30 text-cyber-danger rounded-lg transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {closingTradeId === trade.id ? (
                            <>
                              <Loader2 size={16} className="animate-spin" />
                              Cerrando...
                            </>
                          ) : (
                            <>
                              <X size={16} />
                              Cerrar Trade
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {(isOpen || trade.status === 'pending') && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-cyber-border">
                      <div>
                        <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.quantity}</p>
                        <p className="font-medium text-lg">{(trade.quantity || 0).toFixed(6)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.invested}</p>
                        <p className="font-medium text-lg">${(investedValue || 0).toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.entryPrice}</p>
                        <p className="font-medium text-lg">
                          {trade.entry_price && trade.entry_price > 0 
                            ? `$${trade.entry_price.toFixed(2)}` 
                            : 'N/A'}
                        </p>
                        {(!trade.entry_price || trade.entry_price <= 0) && (
                          <p className="text-xs text-cyber-danger mt-1">
                            ⚠️ Precio de entrada no disponible
                          </p>
                        )}
                      </div>
                      {currentPrice !== null && currentPrice !== undefined ? (
                        <div>
                          <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.currentPrice}</p>
                          <p className={`font-medium text-lg ${
                            currentPrice > (trade.entry_price || 0) ? 'text-cyber-primary' : 'text-cyber-danger'
                          }`}>
                            ${currentPrice.toFixed(2)}
                          </p>
                        </div>
                      ) : (
                        <div>
                          <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.currentPrice}</p>
                          <p className="font-medium text-lg text-cyber-muted">{t.common.loading}</p>
                        </div>
                      )}
                      {currentValue !== null && currentValue !== undefined ? (
                        <div>
                          <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.currentValue}</p>
                          <p className="font-medium text-lg">${currentValue.toFixed(2)}</p>
                        </div>
                      ) : null}
                      {trade.stop_loss !== null && trade.stop_loss !== undefined ? (
                        <div>
                          <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.stopLoss}</p>
                          <p className="font-medium text-lg text-cyber-danger">${trade.stop_loss.toFixed(2)}</p>
                        </div>
                      ) : null}
                      {trade.take_profit !== null && trade.take_profit !== undefined ? (
                        <div>
                          <p className="text-xs text-cyber-muted mb-1">{t.activeTrades.takeProfit}</p>
                          <p className="font-medium text-lg text-cyber-primary">${trade.take_profit.toFixed(2)}</p>
                        </div>
                      ) : null}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        )}
      </motion.div>
    </div>
  )
}

