"""
Middleware para logging de requests HTTP
"""
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging_config import api_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware que registra todas las peticiones HTTP"""
    
    async def dispatch(self, request: Request, call_next):
        # Generar ID único para la request
        request_id = str(uuid.uuid4())[:8]
        
        # Tiempo de inicio
        start_time = time.time()
        
        # Info de la request
        method = request.method
        url = str(request.url.path)
        client_ip = request.client.host if request.client else "unknown"
        
        # Log de entrada
        api_logger.info(
            f"[{request_id}] --> {method} {url} | IP: {client_ip}"
        )
        
        # Procesar request
        try:
            response = await call_next(request)
            
            # Tiempo de procesamiento
            process_time = (time.time() - start_time) * 1000  # ms
            
            # Log de salida
            status_code = response.status_code
            log_level = "INFO" if status_code < 400 else "WARNING" if status_code < 500 else "ERROR"
            
            log_msg = f"[{request_id}] <-- {method} {url} | Status: {status_code} | Time: {process_time:.2f}ms"
            
            if log_level == "INFO":
                api_logger.info(log_msg)
            elif log_level == "WARNING":
                api_logger.warning(log_msg)
            else:
                api_logger.error(log_msg)
            
            return response
            
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            api_logger.error(
                f"[{request_id}] <-- {method} {url} | ERROR: {str(e)} | Time: {process_time:.2f}ms"
            )
            raise


