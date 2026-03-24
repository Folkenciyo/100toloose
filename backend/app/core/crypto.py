"""
Encriptación simétrica para campos sensibles en la BD.

Usa Fernet (AES-128-CBC + HMAC-SHA256) — reversible y autenticado.
La clave se carga desde ENCRYPTION_KEY en el entorno.
"""
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


def _get_fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt(value: str) -> str:
    """Encripta un string y devuelve el resultado en base64."""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Desencripta un valor previamente encriptado con encrypt()."""
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Si falla (campo en texto plano antes de la migración), devuelve el valor tal cual
        return value


class EncryptedString(TypeDecorator):
    """TypeDecorator que encripta al guardar y desencripta al leer.

    Drop-in replacement para Column(String). No requiere cambiar
    ningún código que acceda al modelo — la encriptación es transparente.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encripta antes de guardar en BD."""
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):
        """Desencripta al leer de BD."""
        if value is None:
            return None
        return decrypt(value)
