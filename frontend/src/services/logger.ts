/**
 * Sistema de Logging para Frontend
 * Almacena logs en localStorage con rotación automática (máx 5MB)
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: any;
}

const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5MB
const STORAGE_KEY = '100toloose_logs';
const MAX_ENTRIES = 5000; // Límite de entradas

class Logger {
  private logs: LogEntry[] = [];
  private initialized = false;

  constructor() {
    this.loadFromStorage();
    this.initialized = true;
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        this.logs = JSON.parse(stored);
      }
    } catch (e) {
      console.error('Failed to load logs from storage:', e);
      this.logs = [];
    }
  }

  private saveToStorage(): void {
    try {
      const data = JSON.stringify(this.logs);
      
      // Verificar tamaño
      const sizeBytes = new Blob([data]).size;
      
      if (sizeBytes > MAX_SIZE_BYTES || this.logs.length > MAX_ENTRIES) {
        // Rotar: eliminar la mitad más antigua
        this.logs = this.logs.slice(Math.floor(this.logs.length / 2));
        this.saveToStorage();
        return;
      }
      
      localStorage.setItem(STORAGE_KEY, data);
    } catch (e) {
      console.error('Failed to save logs to storage:', e);
      // Si falla por espacio, limpiar
      if (e instanceof DOMException && e.name === 'QuotaExceededError') {
        this.logs = this.logs.slice(Math.floor(this.logs.length / 2));
        this.saveToStorage();
      }
    }
  }

  private formatTimestamp(): string {
    return new Date().toISOString().replace('T', ' ').substring(0, 19);
  }

  private log(level: LogLevel, message: string, data?: any): void {
    const entry: LogEntry = {
      timestamp: this.formatTimestamp(),
      level,
      message,
      data: data ? this.sanitizeData(data) : undefined
    };

    this.logs.push(entry);
    
    // Console output con colores
    const colors: Record<LogLevel, string> = {
      DEBUG: 'color: #808080',
      INFO: 'color: #00ff88',
      WARN: 'color: #ffaa00',
      ERROR: 'color: #ff3366'
    };

    const prefix = `%c[${entry.timestamp}] [${level}]`;
    
    if (data) {
      console.log(prefix, colors[level], message, data);
    } else {
      console.log(prefix, colors[level], message);
    }

    // Guardar periódicamente (no en cada log para rendimiento)
    if (this.logs.length % 10 === 0) {
      this.saveToStorage();
    }
  }

  private sanitizeData(data: any): any {
    try {
      // Evitar circular references y datos sensibles
      const sanitized = JSON.parse(JSON.stringify(data));
      
      // Ocultar tokens y passwords
      if (typeof sanitized === 'object') {
        this.maskSensitiveFields(sanitized);
      }
      
      return sanitized;
    } catch {
      return String(data);
    }
  }

  private maskSensitiveFields(obj: any): void {
    const sensitiveFields = ['password', 'token', 'secret', 'api_key', 'apiKey'];
    
    for (const key in obj) {
      if (sensitiveFields.some(f => key.toLowerCase().includes(f))) {
        obj[key] = '***MASKED***';
      } else if (typeof obj[key] === 'object' && obj[key] !== null) {
        this.maskSensitiveFields(obj[key]);
      }
    }
  }

  debug(message: string, data?: any): void {
    this.log('DEBUG', message, data);
  }

  info(message: string, data?: any): void {
    this.log('INFO', message, data);
  }

  warn(message: string, data?: any): void {
    this.log('WARN', message, data);
  }

  error(message: string, data?: any): void {
    this.log('ERROR', message, data);
  }

  // Logging específico para trades
  trade(action: 'OPEN' | 'CLOSE' | 'CANCEL', symbol: string, details: any): void {
    this.info(`📊 TRADE ${action}: ${symbol}`, details);
  }

  // Logging de API calls
  api(method: string, url: string, status?: number, duration?: number): void {
    const statusEmoji = status ? (status < 400 ? '✅' : '❌') : '⏳';
    const durationStr = duration ? ` (${duration}ms)` : '';
    this.debug(`${statusEmoji} API ${method} ${url}${status ? ` → ${status}` : ''}${durationStr}`);
  }

  // Obtener logs
  getLogs(level?: LogLevel, limit = 100): LogEntry[] {
    let filtered = level 
      ? this.logs.filter(l => l.level === level)
      : this.logs;
    
    return filtered.slice(-limit);
  }

  // Obtener logs como texto
  getLogsAsText(limit = 500): string {
    return this.logs
      .slice(-limit)
      .map(l => `${l.timestamp} | ${l.level.padEnd(5)} | ${l.message}${l.data ? ' | ' + JSON.stringify(l.data) : ''}`)
      .join('\n');
  }

  // Estadísticas
  getStats(): { total: number; byLevel: Record<LogLevel, number>; sizeKB: number } {
    const byLevel: Record<LogLevel, number> = {
      DEBUG: 0,
      INFO: 0,
      WARN: 0,
      ERROR: 0
    };

    this.logs.forEach(l => byLevel[l.level]++);

    const sizeBytes = new Blob([JSON.stringify(this.logs)]).size;

    return {
      total: this.logs.length,
      byLevel,
      sizeKB: Math.round(sizeBytes / 1024)
    };
  }

  // Limpiar logs
  clear(): void {
    this.logs = [];
    localStorage.removeItem(STORAGE_KEY);
    this.info('Logs cleared');
  }

  // Exportar logs
  export(): string {
    return JSON.stringify(this.logs, null, 2);
  }

  // Guardar forzado
  flush(): void {
    this.saveToStorage();
  }
}

// Singleton
export const logger = new Logger();

// Interceptar errores globales
if (typeof window !== 'undefined') {
  window.addEventListener('error', (event) => {
    logger.error(`Uncaught Error: ${event.message}`, {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno
    });
  });

  window.addEventListener('unhandledrejection', (event) => {
    logger.error(`Unhandled Promise Rejection: ${event.reason}`);
  });

  // Guardar logs antes de cerrar la página
  window.addEventListener('beforeunload', () => {
    logger.flush();
  });
}

export default logger;


