import axios from 'axios'
import { logger } from './logger'

// Empty string = relative URLs → Vite proxy forwards /api/* to backend:8000
const API_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const startTime = Date.now()
  // @ts-ignore
  config.metadata = { startTime }
  
  const storedData = localStorage.getItem('100toloose-auth')
  if (storedData) {
    const { state } = JSON.parse(storedData)
    if (state?.token) {
      config.headers.Authorization = `Bearer ${state.token}`
    }
  }
  
  logger.api(config.method?.toUpperCase() || 'GET', config.url || '')
  
  return config
})

// Handle responses and errors
api.interceptors.response.use(
  (response) => {
    // @ts-ignore
    const duration = Date.now() - (response.config.metadata?.startTime || Date.now())
    logger.api(
      response.config.method?.toUpperCase() || 'GET',
      response.config.url || '',
      response.status,
      duration
    )
    return response
  },
  (error) => {
    // @ts-ignore
    const duration = Date.now() - (error.config?.metadata?.startTime || Date.now())
    const status = error.response?.status || 0
    const url = error.config?.url || 'unknown'
    const method = error.config?.method?.toUpperCase() || 'GET'
    
    logger.api(method, url, status, duration)
    
    if (status === 401) {
      logger.warn('Session expired, redirecting to login')
      localStorage.removeItem('100toloose-auth')
      window.location.href = '/login'
    } else if (status >= 500) {
      logger.error(`Server error on ${method} ${url}`, {
        status,
        message: error.response?.data?.detail || error.message
      })
    }
    
    return Promise.reject(error)
  }
)

export default api

// API functions
export const marketApi = {
  getPrice: (symbol: string) => {
    logger.debug(`Fetching price for ${symbol}`)
    return api.get(`/market/price/${symbol}`)
  },
  getKlines: (symbol: string, interval = '1h', limit = 100) => 
    api.get(`/market/klines/${symbol}?interval=${interval}&limit=${limit}`),
  getTicker24h: (symbol: string) => api.get(`/market/ticker/24h/${symbol}`),
  getSymbols: () => api.get('/market/symbols'),
  getAnalysis: (symbol: string, interval = '1h') => 
    api.get(`/market/analysis/${symbol}?interval=${interval}`),
}

export const tradesApi = {
  getAll: (status?: string) => api.get(`/trades/${status ? `?status_filter=${status}` : ''}`),
  getOpen: () => api.get('/trades/open'),
  create: (data: any) => {
    logger.trade('OPEN', data.symbol, data)
    return api.post('/trades/', data)
  },
  close: (id: number) => {
    logger.info(`Closing trade #${id}`)
    return api.post(`/trades/${id}/close`)
  },
}

export const strategiesApi = {
  getAll: () => api.get('/strategies/'),
  getAllWithStatus: () => api.get('/strategies/with-status'),
  get: (id: number) => api.get(`/strategies/${id}`),
  create: (data: any) => {
    logger.info('Creating new strategy', { name: data.name, type: data.strategy_type })
    return api.post('/strategies/', data)
  },
  update: (id: number, data: any) => api.put(`/strategies/${id}`, data),
  activate: (id: number) => {
    logger.info(`Activating strategy #${id}`)
    return api.post(`/strategies/${id}/activate`)
  },
  deactivate: (id: number) => {
    logger.info(`Deactivating strategy #${id}`)
    return api.post(`/strategies/${id}/deactivate`)
  },
  delete: (id: number) => {
    logger.warn(`Deleting strategy #${id}`)
    return api.delete(`/strategies/${id}`)
  },
}

export const botApi = {
  status: () => api.get('/bot/status'),
  stats: () => api.get('/bot/stats'),
  start: () => api.post('/bot/start'),
  stop: () => api.post('/bot/stop'),
}

export const dashboardApi = {
  get: () => api.get('/users/dashboard'),
}

export const logsApi = {
  list: () => api.get('/logs/'),
  view: (logType: string, lines = 100) => api.get(`/logs/view/${logType}?lines=${lines}`),
  viewRaw: (logType: string, lines = 100) => api.get(`/logs/view/${logType}/raw?lines=${lines}`),
  stats: () => api.get('/logs/stats'),
}

export const profileApi = {
  getSettings: () => api.get('/profile/settings'),
  updateSettings: (data: any) => api.put('/profile/settings', data),
  testEmail: () => api.post('/profile/settings/test-email'),
  testTelegram: () => api.post('/profile/settings/test-telegram'),
  testTelegramTrade: () => api.post('/profile/settings/test-telegram-trade'),
  getTelegramChatId: () => api.get('/profile/settings/get-telegram-chat-id'),
}

export const deepseekApi = {
  getDecisions: (limit = 20, offset = 0, executedOnly = false) => 
    api.get(`/deepseek/decisions?limit=${limit}&offset=${offset}&executed_only=${executedOnly}`),
  getDecision: (id: number) => api.get(`/deepseek/decisions/${id}`),
}
