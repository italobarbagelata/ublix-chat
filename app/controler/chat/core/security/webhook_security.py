"""
Sistema de seguridad para webhooks con autenticación HMAC y protecciones adicionales.
Previene ataques de webhook spoofing y garantiza la integridad de las cargas útiles.
"""

import hmac
import hashlib
import secrets
import time
import json
import logging
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class WebhookSecurityConfig:
    """Configuración de seguridad para webhooks."""
    secret_key: str
    max_age_seconds: int = 300  # 5 minutos
    require_https: bool = True
    allowed_hosts: Optional[list] = None
    rate_limit_per_minute: int = 60

class WebhookSecurity:
    """
    Sistema de seguridad robusto para webhooks.
    Implementa autenticación HMAC, verificación de timestamp y protecciones adicionales.
    """
    
    def __init__(self, config: WebhookSecurityConfig):
        self.config = config
        self.rate_limit_cache = {}  # En producción usar Redis
        
    @staticmethod
    def generate_webhook_secret() -> str:
        """
        Genera una clave secreta segura para webhooks.
        
        Returns:
            Clave secreta de 64 caracteres hexadecimales
        """
        return secrets.token_hex(32)
    
    def create_signature(self, payload: str, timestamp: str) -> str:
        """
        Crea una signature HMAC-SHA256 para el payload.
        
        Args:
            payload: Datos del webhook en formato JSON string
            timestamp: Timestamp Unix como string
            
        Returns:
            Signature HMAC en formato hexadecimal
        """
        # Crear el mensaje para firmar: timestamp + payload
        message = f"{timestamp}.{payload}"
        
        # Crear signature HMAC-SHA256
        signature = hmac.new(
            self.config.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_signature(self, payload: str, received_signature: str, timestamp: str) -> Tuple[bool, str]:
        """
        Verifica la signature HMAC del webhook.
        
        Args:
            payload: Datos del webhook en formato JSON string
            received_signature: Signature recibida en el header
            timestamp: Timestamp del webhook
            
        Returns:
            Tuple (es_válida, mensaje_error)
        """
        try:
            # Crear signature esperada
            expected_signature = self.create_signature(payload, timestamp)
            
            # Comparación segura contra timing attacks
            if not hmac.compare_digest(expected_signature, received_signature):
                return False, "Signature HMAC inválida"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error verificando signature webhook: {str(e)}")
            return False, f"Error interno verificando signature: {str(e)}"
    
    def verify_timestamp(self, timestamp: str) -> Tuple[bool, str]:
        """
        Verifica que el timestamp del webhook esté dentro del rango permitido.
        
        Args:
            timestamp: Timestamp Unix como string
            
        Returns:
            Tuple (es_válido, mensaje_error)
        """
        try:
            webhook_time = int(timestamp)
            current_time = int(time.time())
            
            # Verificar que no sea muy antiguo
            if current_time - webhook_time > self.config.max_age_seconds:
                return False, f"Webhook expirado (máximo {self.config.max_age_seconds} segundos)"
            
            # Verificar que no sea del futuro (con margen de 30 segundos)
            if webhook_time > current_time + 30:
                return False, "Timestamp del webhook es del futuro"
            
            return True, ""
            
        except (ValueError, TypeError):
            return False, "Formato de timestamp inválido"
    
    def verify_url_security(self, webhook_url: str) -> Tuple[bool, str]:
        """
        Verifica que la URL del webhook sea segura.
        
        Args:
            webhook_url: URL del webhook a verificar
            
        Returns:
            Tuple (es_válida, mensaje_error)
        """
        try:
            parsed = urlparse(webhook_url)
            
            # Verificar HTTPS en producción
            if self.config.require_https and parsed.scheme != 'https':
                return False, "Webhook debe usar HTTPS"
            
            # Verificar hosts permitidos
            if self.config.allowed_hosts:
                if parsed.netloc not in self.config.allowed_hosts:
                    return False, f"Host no permitido: {parsed.netloc}"
            
            # Verificar contra IPs privadas/localhost
            dangerous_hosts = [
                'localhost', '127.0.0.1', '0.0.0.0', '::1',
                '10.', '192.168.', '172.16.', '172.17.', '172.18.',
                '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
                '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
                '172.29.', '172.30.', '172.31.'
            ]
            
            host_lower = parsed.netloc.lower()
            for dangerous_host in dangerous_hosts:
                if dangerous_host in host_lower:
                    return False, f"No se permite apuntar a IPs privadas/localhost: {parsed.netloc}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Error validando URL: {str(e)}"
    
    def check_rate_limit(self, webhook_url: str) -> Tuple[bool, str]:
        """
        Verifica que el webhook no exceda el rate limit.
        
        Args:
            webhook_url: URL del webhook
            
        Returns:
            Tuple (está_permitido, mensaje_error)
        """
        try:
            current_minute = int(time.time() // 60)
            key = f"{webhook_url}:{current_minute}"
            
            # Obtener contador actual
            current_count = self.rate_limit_cache.get(key, 0)
            
            if current_count >= self.config.rate_limit_per_minute:
                return False, f"Rate limit excedido ({self.config.rate_limit_per_minute}/minuto)"
            
            # Incrementar contador
            self.rate_limit_cache[key] = current_count + 1
            
            # Limpiar entradas antiguas (mantener solo último minuto)
            keys_to_delete = [
                k for k in self.rate_limit_cache.keys() 
                if int(k.rsplit(':', 1)[1]) < current_minute - 1
            ]
            for key_to_delete in keys_to_delete:
                del self.rate_limit_cache[key_to_delete]
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error verificando rate limit: {str(e)}")
            return False, f"Error interno verificando rate limit"
    
    def prepare_secure_webhook_payload(self, data: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
        """
        Prepara un payload de webhook con signature y headers de seguridad.
        
        Args:
            data: Datos a enviar en el webhook
            
        Returns:
            Tuple (payload_json, headers_seguros)
        """
        # Agregar timestamp
        timestamp = str(int(time.time()))
        
        # Serializar datos
        payload = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        # Crear signature
        signature = self.create_signature(payload, timestamp)
        
        # Preparar headers de seguridad
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": signature,
            "User-Agent": "Ublix-Webhook/2.0-Secure",
            "X-Delivered-At": datetime.utcnow().isoformat() + "Z"
        }
        
        return payload, headers
    
    def verify_incoming_webhook(self, payload: str, headers: Dict[str, str], webhook_url: str) -> Tuple[bool, str]:
        """
        Verifica completamente un webhook entrante.
        
        Args:
            payload: Payload del webhook
            headers: Headers HTTP del webhook
            webhook_url: URL del webhook
            
        Returns:
            Tuple (es_válido, mensaje_error)
        """
        # Verificar rate limit
        rate_limit_ok, rate_limit_error = self.check_rate_limit(webhook_url)
        if not rate_limit_ok:
            return False, f"Rate limit: {rate_limit_error}"
        
        # Verificar URL de seguridad
        url_ok, url_error = self.verify_url_security(webhook_url)
        if not url_ok:
            return False, f"URL insegura: {url_error}"
        
        # Obtener headers requeridos
        timestamp = headers.get("X-Webhook-Timestamp")
        signature = headers.get("X-Webhook-Signature")
        
        if not timestamp:
            return False, "Header X-Webhook-Timestamp faltante"
        
        if not signature:
            return False, "Header X-Webhook-Signature faltante"
        
        # Verificar timestamp
        timestamp_ok, timestamp_error = self.verify_timestamp(timestamp)
        if not timestamp_ok:
            return False, f"Timestamp inválido: {timestamp_error}"
        
        # Verificar signature
        signature_ok, signature_error = self.verify_signature(payload, signature, timestamp)
        if not signature_ok:
            return False, f"Signature inválida: {signature_error}"
        
        return True, ""

class WebhookSecurityManager:
    """
    Manager para configuraciones de seguridad de webhooks por proyecto.
    """
    
    def __init__(self):
        self.project_configs = {}  # En producción usar base de datos
        
    def get_or_create_security_config(self, project_id: str) -> WebhookSecurityConfig:
        """
        Obtiene o crea configuración de seguridad para un proyecto.
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Configuración de seguridad del proyecto
        """
        if project_id not in self.project_configs:
            # En producción, esto debería leer desde base de datos
            # Por ahora, crear configuración por defecto
            secret_key = WebhookSecurity.generate_webhook_secret()
            self.project_configs[project_id] = WebhookSecurityConfig(
                secret_key=secret_key,
                max_age_seconds=300,
                require_https=True,
                rate_limit_per_minute=60
            )
            
            logger.info(f"Created new webhook security config for project {project_id}")
        
        return self.project_configs[project_id]
    
    def create_secure_webhook(self, project_id: str, webhook_url: str, data: Dict[str, Any]) -> Tuple[str, Dict[str, str], bool, str]:
        """
        Crea un webhook seguro para un proyecto.
        
        Args:
            project_id: ID del proyecto
            webhook_url: URL del webhook
            data: Datos a enviar
            
        Returns:
            Tuple (payload, headers, es_válido, mensaje_error)
        """
        config = self.get_or_create_security_config(project_id)
        webhook_security = WebhookSecurity(config)
        
        # Verificar URL
        url_ok, url_error = webhook_security.verify_url_security(webhook_url)
        if not url_ok:
            return "", {}, False, f"URL insegura: {url_error}"
        
        # Verificar rate limit
        rate_limit_ok, rate_limit_error = webhook_security.check_rate_limit(webhook_url)
        if not rate_limit_ok:
            return "", {}, False, f"Rate limit: {rate_limit_error}"
        
        # Preparar payload seguro
        payload, headers = webhook_security.prepare_secure_webhook_payload(data)
        
        return payload, headers, True, ""

# Instancia global del manager
webhook_security_manager = WebhookSecurityManager()