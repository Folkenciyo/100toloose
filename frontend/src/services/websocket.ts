/**
 * WebSocket service para actualizaciones en tiempo real de precios
 */
import { logger } from './logger'

// Determinar la URL base del WebSocket
// En desarrollo, conectamos directamente al backend (puerto 8000)
// En producción, usar la misma URL que la API
const getWebSocketUrl = (): string => {
  if (import.meta.env.DEV) {
    // En desarrollo, conectar directamente al backend en puerto 8000
    return 'ws://localhost:8000'
  } else {
    // En producción, usar la misma URL que la API
    const API_URL = import.meta.env.VITE_API_URL || window.location.origin
    return API_URL.replace(/^https?:/, window.location.protocol === 'https:' ? 'wss:' : 'ws:')
  }
}

const WS_BASE_URL = getWebSocketUrl()

export interface PriceUpdate {
  type: 'price_update'
  symbol: string
  price: number
  change: number
  timestamp: string
}

export interface InitialPrices {
  type: 'initial_prices'
  prices: Record<string, number>
}

export interface TradeUpdate {
  type: 'trade_update'
  trade: any
  timestamp: string
}

export type WebSocketMessage = PriceUpdate | InitialPrices | TradeUpdate | { type: 'subscribed' | 'pong' }

type PriceUpdateCallback = (symbol: string, price: number, change: number) => void
type TradeUpdateCallback = (trade: any) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private isConnecting = false
  private priceCallbacks: Set<PriceUpdateCallback> = new Set()
  private tradeCallbacks: Set<TradeUpdateCallback> = new Set()
  private subscribedSymbols: Set<string> = new Set()
  private latestPrices: Map<string, number> = new Map()

  /**
   * Obtiene el token JWT del localStorage
   */
  private getToken(): string | null {
    try {
      const storedData = localStorage.getItem('100toloose-auth')
      if (storedData) {
        const { state } = JSON.parse(storedData)
        return state?.token || null
      }
    } catch (e) {
      logger.error('Failed to get token from localStorage', e)
    }
    return null
  }

  /**
   * Conecta al WebSocket
   */
  async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      return
    }

    const token = this.getToken()
    if (!token) {
      logger.warn('No token available for WebSocket connection')
      return
    }

    this.isConnecting = true

    try {
      // Construir URL del WebSocket
      const wsUrl = `${WS_BASE_URL}/api/v1/ws/prices?token=${encodeURIComponent(token)}`
      
      logger.info(`Connecting to WebSocket: ${wsUrl.replace(token, '***')}`)
      
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        logger.info('✅ WebSocket connected')
        this.isConnecting = false
        this.reconnectAttempts = 0
        
        // Re-suscribir símbolos si ya había algunos
        if (this.subscribedSymbols.size > 0) {
          this.subscribe(Array.from(this.subscribedSymbols))
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (e) {
          logger.error('Failed to parse WebSocket message', e)
        }
      }

      this.ws.onerror = (error) => {
        logger.error('WebSocket error', error)
        this.isConnecting = false
      }

      this.ws.onclose = () => {
        logger.warn('WebSocket closed')
        this.isConnecting = false
        this.ws = null
        
        // Intentar reconectar si no excedimos el límite
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          const delay = this.reconnectDelay * this.reconnectAttempts
          logger.info(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
          setTimeout(() => this.connect(), delay)
        } else {
          logger.error('Max reconnection attempts reached')
        }
      }
    } catch (error) {
      logger.error('Failed to create WebSocket connection', error)
      this.isConnecting = false
    }
  }

  /**
   * Maneja mensajes recibidos del WebSocket
   */
  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'price_update':
        const priceMsg = message as PriceUpdate
        this.latestPrices.set(priceMsg.symbol, priceMsg.price)
        this.priceCallbacks.forEach(callback => {
          try {
            callback(priceMsg.symbol, priceMsg.price, priceMsg.change)
          } catch (e) {
            logger.error('Error in price callback', e)
          }
        })
        break

      case 'initial_prices':
        const initialMsg = message as InitialPrices
        Object.entries(initialMsg.prices).forEach(([symbol, price]) => {
          this.latestPrices.set(symbol, price)
        })
        break

      case 'trade_update':
        const tradeMsg = message as TradeUpdate
        this.tradeCallbacks.forEach(callback => {
          try {
            callback(tradeMsg.trade)
          } catch (e) {
            logger.error('Error in trade callback', e)
          }
        })
        break

      case 'subscribed':
        logger.info('Successfully subscribed to symbols')
        break

      case 'pong':
        // Heartbeat response
        break

      default:
        logger.warn('Unknown WebSocket message type', message)
    }
  }

  /**
   * Suscribe a actualizaciones de precios para símbolos específicos
   */
  subscribe(symbols: string[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // Guardar para suscribir cuando se conecte
      symbols.forEach(s => this.subscribedSymbols.add(s))
      return
    }

    symbols.forEach(s => this.subscribedSymbols.add(s))

    this.ws.send(JSON.stringify({
      action: 'subscribe',
      symbols: Array.from(this.subscribedSymbols)
    }))

    logger.info(`Subscribed to ${symbols.length} symbols`)
  }

  /**
   * Desuscribe de símbolos
   */
  unsubscribe(symbols: string[]): void {
    symbols.forEach(s => this.subscribedSymbols.delete(s))
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: Array.from(this.subscribedSymbols)
      }))
    }
  }

  /**
   * Registra un callback para actualizaciones de precios
   */
  onPriceUpdate(callback: PriceUpdateCallback): () => void {
    this.priceCallbacks.add(callback)
    
    // Retorna función para desregistrar
    return () => {
      this.priceCallbacks.delete(callback)
    }
  }

  /**
   * Registra un callback para actualizaciones de trades
   */
  onTradeUpdate(callback: TradeUpdateCallback): () => void {
    this.tradeCallbacks.add(callback)
    
    // Retorna función para desregistrar
    return () => {
      this.tradeCallbacks.delete(callback)
    }
  }

  /**
   * Obtiene el último precio conocido de un símbolo
   */
  getLatestPrice(symbol: string): number | undefined {
    return this.latestPrices.get(symbol)
  }

  /**
   * Obtiene todos los precios conocidos
   */
  getAllLatestPrices(): Map<string, number> {
    return new Map(this.latestPrices)
  }

  /**
   * Desconecta el WebSocket
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.priceCallbacks.clear()
    this.tradeCallbacks.clear()
    this.subscribedSymbols.clear()
    this.latestPrices.clear()
    this.reconnectAttempts = 0
  }

  /**
   * Verifica si está conectado
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

// Instancia singleton
export const wsService = new WebSocketService()

