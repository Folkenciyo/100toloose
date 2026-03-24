"""
Endpoint para visualizar logs del sistema
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import Optional, Literal
from pathlib import Path
import os

from app.core.security import get_current_superuser
from app.models.user import User
from app.core.logging_config import logger

router = APIRouter()

LOGS_DIR = Path("/app/logs")


@router.get("/")
async def list_log_files(
    current_user: User = Depends(get_current_superuser)
):
    """Lista todos los archivos de log disponibles"""
    if not LOGS_DIR.exists():
        return {"files": [], "message": "No logs directory found"}
    
    log_files = []
    for file in LOGS_DIR.glob("*.log*"):
        stat = file.stat()
        log_files.append({
            "name": file.name,
            "size_kb": round(stat.st_size / 1024, 2),
            "size_mb": round(stat.st_size / (1024 * 1024), 4),
            "modified": stat.st_mtime
        })
    
    # Ordenar por fecha de modificación (más reciente primero)
    log_files.sort(key=lambda x: x["modified"], reverse=True)
    
    total_size_mb = sum(f["size_mb"] for f in log_files)
    
    return {
        "files": log_files,
        "total_files": len(log_files),
        "total_size_mb": round(total_size_mb, 2),
        "max_size_per_file_mb": 5
    }


@router.get("/view/{log_type}")
async def view_log(
    log_type: Literal["app", "error", "trades", "api", "deepseek", "email", "telegram"] = "app",
    lines: int = Query(default=100, ge=1, le=1000),
    current_user: User = Depends(get_current_superuser)
):
    """
    Ver contenido de un archivo de log
    
    - **log_type**: Tipo de log (app, error, trades, api, deepseek, email, telegram)
    - **lines**: Número de líneas a mostrar (últimas N líneas)
    """
    log_file = LOGS_DIR / f"{log_type}.log"
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"Log file '{log_type}.log' not found")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            
        # Obtener las últimas N líneas
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "log_type": log_type,
            "total_lines": len(all_lines),
            "showing_lines": len(last_lines),
            "content": "".join(last_lines)
        }
    except Exception as e:
        logger.error(f"Error reading log file {log_type}: {e}")
        raise HTTPException(status_code=500, detail="Error reading log file")


@router.get("/view/{log_type}/raw", response_class=PlainTextResponse)
async def view_log_raw(
    log_type: Literal["app", "error", "trades", "api", "deepseek", "email", "telegram"] = "app",
    lines: int = Query(default=100, ge=1, le=1000),
    current_user: User = Depends(get_current_superuser)
):
    """Ver log en formato texto plano (para terminal/curl)"""
    log_file = LOGS_DIR / f"{log_type}.log"
    
    if not log_file.exists():
        return f"Log file '{log_type}.log' not found"
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "".join(last_lines)
    except Exception as e:
        logger.error(f"Error reading raw log {log_type}: {e}")
        return "Error reading log file"


@router.get("/stats")
async def log_stats(
    current_user: User = Depends(get_current_superuser)
):
    """Estadísticas de los logs"""
    if not LOGS_DIR.exists():
        return {"error": "Logs directory not found"}
    
    stats = {
        "logs_directory": str(LOGS_DIR),
        "files": {}
    }
    
    for log_type in ["app", "error", "trades", "api", "deepseek", "email", "telegram"]:
        log_file = LOGS_DIR / f"{log_type}.log"
        if log_file.exists():
            stat = log_file.stat()
            
            # Contar líneas
            with open(log_file, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
            
            # Contar errores y warnings en el archivo
            error_count = 0
            warning_count = 0
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if "| ERROR" in line:
                        error_count += 1
                    elif "| WARNING" in line:
                        warning_count += 1
            
            stats["files"][log_type] = {
                "size_kb": round(stat.st_size / 1024, 2),
                "size_mb": round(stat.st_size / (1024 * 1024), 4),
                "lines": line_count,
                "errors": error_count,
                "warnings": warning_count,
                "backups": len(list(LOGS_DIR.glob(f"{log_type}.log.*")))
            }
        else:
            stats["files"][log_type] = {"exists": False}
    
    return stats


@router.delete("/clear/{log_type}")
async def clear_log(
    log_type: Literal["app", "error", "trades", "api", "deepseek", "email", "telegram"] = "app",
    current_user: User = Depends(get_current_superuser)
):
    """Limpiar un archivo de log (solo superuser)"""
    log_file = LOGS_DIR / f"{log_type}.log"
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"Log file '{log_type}.log' not found")
    
    try:
        # Truncar el archivo
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("")
        
        logger.info(f"Log file {log_type}.log cleared by user {current_user.username}")
        
        return {"message": f"Log file '{log_type}.log' cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing log file {log_type}: {e}")
        raise HTTPException(status_code=500, detail="Error clearing log file")


