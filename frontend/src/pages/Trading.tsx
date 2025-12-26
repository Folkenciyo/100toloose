import { useEffect, useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { 
  TrendingUp, 
  TrendingDown, 
  Search,
  ArrowUpCircle,
  ArrowDownCircle,
  X,
  Loader2
} from 'lucide-react'
import { createChart, ColorType, IChartApi } from 'lightweight-charts'
import { marketApi, tradesApi } from '../services/api'
import { logger } from '../services/logger'
import { useLanguage } from '../i18n'

interface SymbolData {
  symbol: string
  price: number
  change24h?: number
}

interface Analysis {
  current_price: number
  rsi: { value: number; signal: string; overbought: boolean; oversold: boolean }
  macd: { macd: number; signal: number; histogram: number; trend: string }
  bollinger_bands: { upper: number; middle: number; lower: number; position: string }
  ema: { ema_9: number; ema_21: number; signal: string }
  recommendation: string
}

export default function Trading() {
  const [symbols, setSymbols] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT')
  const [symbolData, setSymbolData] = useState<SymbolData | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [klines, setKlines] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [showTradeModal, setShowTradeModal] = useState(false)
  const [tradeType, setTradeType] = useState<'buy' | 'sell'>('buy')
  const [quantity, setQuantity] = useState('')
  const [tradingLoading, setTradingLoading] = useState(false)
  const { t } = useLanguage()
  
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const isChartMounted = useRef(false)

  // Fetch symbols on mount
  useEffect(() => {
    const fetchSymbols = async () => {
      try {
        const res = await marketApi.getSymbols()
        setSymbols(res.data.symbols)
        logger.info('Loaded trading symbols', { count: res.data.symbols.length })
      } catch (error) {
        logger.error('Failed to fetch symbols', error)
      }
    }
    fetchSymbols()
  }, [])

  // Fetch data for selected symbol
  useEffect(() => {
    let isCancelled = false
    
    const fetchData = async () => {
      setLoading(true)
      try {
        const [priceRes, analysisRes, klinesRes] = await Promise.all([
          marketApi.getPrice(selectedSymbol),
          marketApi.getAnalysis(selectedSymbol),
          marketApi.getKlines(selectedSymbol, '1h', 100)
        ])
        
        if (!isCancelled) {
          setSymbolData({ symbol: selectedSymbol, price: priceRes.data.price })
          setAnalysis(analysisRes.data.analysis)
          setKlines(klinesRes.data.klines)
        }
      } catch (error) {
        if (!isCancelled) {
          logger.error('Failed to fetch market data', { symbol: selectedSymbol, error })
        }
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }
    
    fetchData()

    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000)
    
    return () => {
      isCancelled = true
      clearInterval(interval)
    }
  }, [selectedSymbol])

  // Initialize chart - with proper cleanup
  useEffect(() => {
    if (!chartContainerRef.current || klines.length === 0) return
    
    // Mark as mounted
    isChartMounted.current = true

    // Cleanup previous chart safely
    if (chartRef.current) {
      try {
        chartRef.current.remove()
      } catch (e) {
        // Chart already disposed, ignore
      }
      chartRef.current = null
    }

    // Create new chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#12121a' },
        textColor: '#808090',
      },
      grid: {
        vertLines: { color: '#2a2a3a' },
        horzLines: { color: '#2a2a3a' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#2a2a3a',
      },
      timeScale: {
        borderColor: '#2a2a3a',
        timeVisible: true,
      },
    })

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#00ff88',
      downColor: '#ff3366',
      borderUpColor: '#00ff88',
      borderDownColor: '#ff3366',
      wickUpColor: '#00ff88',
      wickDownColor: '#ff3366',
    })

    const chartData = klines.map(k => ({
      time: Math.floor(k.open_time / 1000) as any,
      open: k.open,
      high: k.high,
      low: k.low,
      close: k.close,
    }))

    candlestickSeries.setData(chartData)
    chart.timeScale().fitContent()

    chartRef.current = chart

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current && isChartMounted.current) {
        try {
          chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth })
        } catch (e) {
          // Ignore resize errors on disposed chart
        }
      }
    }

    window.addEventListener('resize', handleResize)
    
    // Cleanup function
    return () => {
      isChartMounted.current = false
      window.removeEventListener('resize', handleResize)
      
      if (chartRef.current) {
        try {
          chartRef.current.remove()
        } catch (e) {
          // Chart already disposed, ignore
        }
        chartRef.current = null
      }
    }
  }, [klines])

  const handleTrade = async () => {
    if (!quantity || parseFloat(quantity) <= 0) return

    setTradingLoading(true)
    try {
      await tradesApi.create({
        symbol: selectedSymbol,
        trade_type: tradeType,
        quantity: parseFloat(quantity),
      })
      logger.trade(tradeType === 'buy' ? 'OPEN' : 'CLOSE', selectedSymbol, { 
        type: tradeType, 
        quantity: parseFloat(quantity),
        price: symbolData?.price 
      })
      setShowTradeModal(false)
      setQuantity('')
    } catch (error: any) {
      logger.error('Trade failed', { symbol: selectedSymbol, error: error.message })
      alert(error.response?.data?.detail || 'Trade failed')
    } finally {
      setTradingLoading(false)
    }
  }

  const filteredSymbols = symbols.filter(s => 
    s.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const getRecommendationColor = (rec: string) => {
    if (rec.includes('BUY')) return 'text-cyber-primary'
    if (rec.includes('SELL')) return 'text-cyber-danger'
    return 'text-cyber-warning'
  }

  const getRecommendationText = (rec: string) => {
    if (rec.includes('STRONG_BUY')) return t.trading.strongBuy
    if (rec.includes('BUY')) return t.trading.buy
    if (rec.includes('STRONG_SELL')) return t.trading.strongSell
    if (rec.includes('SELL')) return t.trading.sell
    return t.trading.hold
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
          {t.trading.title}
        </motion.h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Symbol List */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="bg-cyber-surface border border-cyber-border rounded-xl p-4"
        >
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-cyber-muted" size={18} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t.trading.searchSymbols}
              className="input-cyber w-full pl-10"
            />
          </div>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {filteredSymbols.map((symbol) => (
              <button
                key={symbol}
                onClick={() => setSelectedSymbol(symbol)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-all ${
                  selectedSymbol === symbol
                    ? 'bg-cyber-primary/20 border border-cyber-primary/50'
                    : 'hover:bg-cyber-card'
                }`}
              >
                <span className="font-medium">{symbol}</span>
              </button>
            ))}
          </div>
        </motion.div>

        {/* Chart and Analysis */}
        <div className="lg:col-span-3 space-y-6">
          {/* Price Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold">{selectedSymbol}</h2>
                {loading ? (
                  <div className="flex items-center gap-2 mt-2">
                    <Loader2 size={20} className="animate-spin text-cyber-primary" />
                    <span className="text-cyber-muted">{t.common.loading}</span>
                  </div>
                ) : symbolData && (
                  <p className="text-3xl font-display font-bold text-cyber-primary mt-2">
                    ${symbolData.price.toLocaleString(undefined, { maximumFractionDigits: 8 })}
                  </p>
                )}
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => { setTradeType('buy'); setShowTradeModal(true) }}
                  disabled={loading}
                  className="flex items-center gap-2 px-6 py-3 bg-cyber-primary/20 text-cyber-primary border border-cyber-primary/50 rounded-lg hover:bg-cyber-primary/30 transition-all disabled:opacity-50"
                >
                  <ArrowUpCircle size={20} />
                  {t.trading.buy}
                </button>
                <button
                  onClick={() => { setTradeType('sell'); setShowTradeModal(true) }}
                  disabled={loading}
                  className="flex items-center gap-2 px-6 py-3 bg-cyber-danger/20 text-cyber-danger border border-cyber-danger/50 rounded-lg hover:bg-cyber-danger/30 transition-all disabled:opacity-50"
                >
                  <ArrowDownCircle size={20} />
                  {t.trading.sell}
                </button>
              </div>
            </div>
          </motion.div>

          {/* Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-4"
          >
            {loading ? (
              <div className="h-[400px] flex items-center justify-center">
                <Loader2 size={40} className="animate-spin text-cyber-primary" />
              </div>
            ) : (
              <div ref={chartContainerRef} />
            )}
          </motion.div>

          {/* Technical Analysis */}
          {!loading && analysis && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="grid grid-cols-1 md:grid-cols-4 gap-4"
            >
              {/* RSI */}
              <div className="bg-cyber-surface border border-cyber-border rounded-xl p-4">
                <h3 className="text-sm text-cyber-muted mb-2">{t.trading.rsi} (14)</h3>
                <p className={`text-2xl font-bold ${
                  analysis.rsi.oversold ? 'text-cyber-primary' : 
                  analysis.rsi.overbought ? 'text-cyber-danger' : 'text-cyber-text'
                }`}>
                  {analysis.rsi.value}
                </p>
                <p className="text-xs text-cyber-muted mt-1">
                  {analysis.rsi.overbought ? t.trading.overbought : analysis.rsi.oversold ? t.trading.oversold : t.trading.neutral}
                </p>
              </div>

              {/* MACD */}
              <div className="bg-cyber-surface border border-cyber-border rounded-xl p-4">
                <h3 className="text-sm text-cyber-muted mb-2">{t.trading.macd}</h3>
                <p className={`text-2xl font-bold ${
                  analysis.macd.histogram > 0 ? 'text-cyber-primary' : 'text-cyber-danger'
                }`}>
                  {analysis.macd.histogram > 0 ? '+' : ''}{analysis.macd.histogram.toFixed(4)}
                </p>
                <p className="text-xs text-cyber-muted mt-1">
                  {analysis.macd.histogram > 0 ? t.trading.bullish : t.trading.bearish}
                </p>
              </div>

              {/* Bollinger */}
              <div className="bg-cyber-surface border border-cyber-border rounded-xl p-4">
                <h3 className="text-sm text-cyber-muted mb-2">{t.trading.bollinger}</h3>
                <p className="text-lg font-bold">{analysis.bollinger_bands.position.replace('_', ' ')}</p>
                <p className="text-xs text-cyber-muted mt-1">
                  U: {analysis.bollinger_bands.upper.toFixed(2)} / L: {analysis.bollinger_bands.lower.toFixed(2)}
                </p>
              </div>

              {/* Recommendation */}
              <div className="bg-cyber-surface border border-cyber-border rounded-xl p-4">
                <h3 className="text-sm text-cyber-muted mb-2">{t.trading.signal}</h3>
                <p className={`text-2xl font-bold ${getRecommendationColor(analysis.recommendation)}`}>
                  {getRecommendationText(analysis.recommendation)}
                </p>
                <p className="text-xs text-cyber-muted mt-1">{t.trading.combinedAnalysis}</p>
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* Trade Modal */}
      {showTradeModal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
          onClick={() => setShowTradeModal(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-cyber-surface border border-cyber-border rounded-xl p-6 w-full max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">
                {tradeType === 'buy' ? t.trading.buy : t.trading.sell} {selectedSymbol}
              </h2>
              <button onClick={() => setShowTradeModal(false)} className="text-cyber-muted hover:text-cyber-text">
                <X size={24} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-cyber-muted mb-2">{t.trading.currentPrice}</label>
                <p className="text-2xl font-bold text-cyber-primary">
                  ${symbolData?.price.toLocaleString()}
                </p>
              </div>

              <div>
                <label className="block text-sm text-cyber-muted mb-2">{t.trading.quantity}</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  placeholder="0.00"
                  className="input-cyber w-full"
                  step="0.0001"
                />
              </div>

              {quantity && symbolData && (
                <div className="bg-cyber-card rounded-lg p-4">
                  <p className="text-sm text-cyber-muted">{t.trading.totalValue}</p>
                  <p className="text-xl font-bold">
                    ${(parseFloat(quantity) * symbolData.price).toLocaleString()}
                  </p>
                </div>
              )}

              <button
                onClick={handleTrade}
                disabled={!quantity || parseFloat(quantity) <= 0 || tradingLoading}
                className={`w-full py-4 rounded-lg font-bold transition-all flex items-center justify-center gap-2 ${
                  tradeType === 'buy'
                    ? 'bg-cyber-primary text-cyber-bg hover:opacity-90'
                    : 'bg-cyber-danger text-white hover:opacity-90'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {tradingLoading ? (
                  <>
                    <Loader2 size={20} className="animate-spin" />
                    {t.trading.processing}
                  </>
                ) : (
                  <>
                    {tradeType === 'buy' ? t.trading.buy : t.trading.sell} {selectedSymbol}
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  )
}
