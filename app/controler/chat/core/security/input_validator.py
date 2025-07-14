"""
Validador de entrada robusto para herramientas de calendario y agenda.
Implementa validaciones de seguridad para prevenir inyecciones y datos maliciosos.
"""

import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse
import pytz
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Resultado de validación con detalles específicos."""
    is_valid: bool
    sanitized_value: Any = None
    error_message: str = ""
    error_code: str = ""

class InputValidator:
    """
    Validador de entrada seguro para aplicaciones de calendario y agenda.
    Previene inyecciones SQL, XSS, y valida formatos de datos críticos.
    """
    
    # Patrones de validación
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?@[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$'
    )
    
    PHONE_PATTERN = re.compile(
        r'^\+?[\d\s\-\(\)]{7,20}$'
    )
    
    # Patrón para IDs de WhatsApp (formato: número@s.whatsapp.net)
    WHATSAPP_ID_PATTERN = re.compile(
        r'^\d+@s\.whatsapp\.net$'
    )
    
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    # Caracteres peligrosos para prevenir inyecciones
    SQL_INJECTION_PATTERNS = [
        r'(\'|\"|;|--|\*|\/\*|\*\/)',
        r'(union|select|insert|update|delete|drop|create|alter|exec|execute)',
        r'(script|javascript|vbscript|onload|onerror|onclick)'
    ]
    
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>'
    ]
    
    CHILE_TZ = pytz.timezone('America/Santiago')
    
    @classmethod
    def validate_project_id(cls, project_id: Any) -> ValidationResult:
        """
        Valida ID de proyecto.
        
        Args:
            project_id: ID del proyecto a validar
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not project_id:
            return ValidationResult(False, None, "Project ID es requerido", "MISSING_PROJECT_ID")
        
        # Convertir a string y sanitizar
        project_id_str = str(project_id).strip()
        
        # Verificar longitud razonable
        if len(project_id_str) > 100:
            return ValidationResult(False, None, "Project ID demasiado largo", "PROJECT_ID_TOO_LONG")
        
        # Verificar si es UUID válido
        if cls.UUID_PATTERN.match(project_id_str):
            return ValidationResult(True, project_id_str, "", "")
        
        # Si no es UUID, verificar que solo contenga caracteres alfanuméricos y guiones
        if re.match(r'^[a-zA-Z0-9_-]+$', project_id_str):
            return ValidationResult(True, project_id_str, "", "")
        
        return ValidationResult(False, None, "Project ID contiene caracteres inválidos", "INVALID_PROJECT_ID")
    
    @classmethod
    def validate_user_id(cls, user_id: Any) -> ValidationResult:
        """
        Valida ID de usuario (número de teléfono, WhatsApp ID, UUID o alfanumérico).
        
        Formatos soportados:
        - Números de teléfono: +56949031247, 56949031247
        - WhatsApp IDs: 56949031247@s.whatsapp.net
        - UUIDs: f47ac10b-58cc-4372-a567-0e02b2c3d479
        - Alfanuméricos: user123, test_user
        
        Args:
            user_id: ID del usuario a validar
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not user_id:
            return ValidationResult(False, None, "User ID es requerido", "MISSING_USER_ID")
        
        user_id_str = str(user_id).strip()
        
        # Verificar longitud razonable
        if len(user_id_str) > 50:
            return ValidationResult(False, None, "User ID demasiado largo", "USER_ID_TOO_LONG")
        
        # Si parece ser un número de teléfono
        if cls.PHONE_PATTERN.match(user_id_str):
            # Sanitizar: solo números, + y espacios
            sanitized = re.sub(r'[^\d\+\s]', '', user_id_str)
            return ValidationResult(True, sanitized, "", "")
        
        # Si es un ID de WhatsApp (formato: número@s.whatsapp.net)
        if cls.WHATSAPP_ID_PATTERN.match(user_id_str):
            return ValidationResult(True, user_id_str, "", "")
        
        # Si es UUID
        if cls.UUID_PATTERN.match(user_id_str):
            return ValidationResult(True, user_id_str, "", "")
        
        # Si es alfanumérico
        if re.match(r'^[a-zA-Z0-9_-]+$', user_id_str):
            return ValidationResult(True, user_id_str, "", "")
        
        return ValidationResult(False, None, "User ID contiene caracteres inválidos", "INVALID_USER_ID")
    
    @classmethod
    def validate_email(cls, email: Any) -> ValidationResult:
        """
        Valida dirección de email con verificaciones de seguridad.
        
        Args:
            email: Email a validar
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not email:
            return ValidationResult(False, None, "Email es requerido", "MISSING_EMAIL")
        
        email_str = str(email).strip().lower()
        
        # Verificar longitud
        if len(email_str) > 254:  # RFC 5321 limit
            return ValidationResult(False, None, "Email demasiado largo", "EMAIL_TOO_LONG")
        
        # Verificar patrones de inyección
        for pattern in cls.SQL_INJECTION_PATTERNS + cls.XSS_PATTERNS:
            if re.search(pattern, email_str, re.IGNORECASE):
                return ValidationResult(False, None, "Email contiene caracteres peligrosos", "DANGEROUS_EMAIL")
        
        # Validar formato de email
        if not cls.EMAIL_PATTERN.match(email_str):
            return ValidationResult(False, None, "Formato de email inválido", "INVALID_EMAIL_FORMAT")
        
        return ValidationResult(True, email_str, "", "")
    
    @classmethod
    def validate_datetime(cls, dt_str: Any, field_name: str = "datetime") -> ValidationResult:
        """
        Valida string de fecha/hora ISO.
        
        Args:
            dt_str: String de fecha/hora a validar
            field_name: Nombre del campo para mensajes de error
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not dt_str:
            return ValidationResult(False, None, f"{field_name} es requerido", "MISSING_DATETIME")
        
        dt_str_clean = str(dt_str).strip()
        
        # Verificar longitud razonable
        if len(dt_str_clean) > 50:
            return ValidationResult(False, None, f"{field_name} demasiado largo", "DATETIME_TOO_LONG")
        
        try:
            # Intentar parsear diferentes formatos
            if dt_str_clean.endswith('Z'):
                dt_str_clean = dt_str_clean.replace('Z', '+00:00')
            
            parsed_dt = datetime.fromisoformat(dt_str_clean)
            
            # Verificar que la fecha esté en un rango razonable
            now = datetime.now(cls.CHILE_TZ)
            min_date = now - timedelta(days=365)  # Máximo 1 año atrás
            max_date = now + timedelta(days=365 * 2)  # Máximo 2 años adelante
            
            # Convertir a UTC para comparación
            if parsed_dt.tzinfo is None:
                parsed_dt = cls.CHILE_TZ.localize(parsed_dt)
            
            parsed_dt_utc = parsed_dt.astimezone(pytz.UTC)
            now_utc = now.astimezone(pytz.UTC)
            min_date_utc = min_date.astimezone(pytz.UTC)
            max_date_utc = max_date.astimezone(pytz.UTC)
            
            if parsed_dt_utc < min_date_utc:
                return ValidationResult(False, None, f"{field_name} muy en el pasado", "DATETIME_TOO_OLD")
            
            if parsed_dt_utc > max_date_utc:
                return ValidationResult(False, None, f"{field_name} muy en el futuro", "DATETIME_TOO_FUTURE")
            
            return ValidationResult(True, parsed_dt.isoformat(), "", "")
            
        except ValueError as e:
            return ValidationResult(False, None, f"Formato de {field_name} inválido: {str(e)}", "INVALID_DATETIME_FORMAT")
    
    @classmethod
    def validate_event_id(cls, event_id: Any) -> ValidationResult:
        """
        Valida ID de evento de Google Calendar.
        
        Args:
            event_id: ID del evento a validar
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not event_id:
            return ValidationResult(False, None, "Event ID es requerido", "MISSING_EVENT_ID")
        
        event_id_str = str(event_id).strip()
        
        # Google Calendar IDs tienen longitud específica
        if len(event_id_str) > 1024:
            return ValidationResult(False, None, "Event ID demasiado largo", "EVENT_ID_TOO_LONG")
        
        # Verificar caracteres válidos para Google Calendar IDs
        if not re.match(r'^[a-zA-Z0-9_-]+$', event_id_str):
            return ValidationResult(False, None, "Event ID contiene caracteres inválidos", "INVALID_EVENT_ID")
        
        return ValidationResult(True, event_id_str, "", "")
    
    @classmethod
    def validate_text_input(cls, text: Any, field_name: str, max_length: int = 1000, required: bool = False) -> ValidationResult:
        """
        Valida entrada de texto general con sanitización.
        
        Args:
            text: Texto a validar
            field_name: Nombre del campo
            max_length: Longitud máxima permitida
            required: Si el campo es requerido
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not text:
            if required:
                return ValidationResult(False, None, f"{field_name} es requerido", "MISSING_REQUIRED_FIELD")
            return ValidationResult(True, "", "", "")
        
        text_str = str(text).strip()
        
        # Verificar longitud
        if len(text_str) > max_length:
            return ValidationResult(False, None, f"{field_name} demasiado largo (máximo {max_length} caracteres)", "TEXT_TOO_LONG")
        
        # Verificar patrones peligrosos
        for pattern in cls.SQL_INJECTION_PATTERNS + cls.XSS_PATTERNS:
            if re.search(pattern, text_str, re.IGNORECASE):
                logger.warning(f"Patrón peligroso detectado en {field_name}: {pattern}")
                return ValidationResult(False, None, f"{field_name} contiene caracteres peligrosos", "DANGEROUS_INPUT")
        
        # Sanitizar caracteres de control
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text_str)
        
        return ValidationResult(True, sanitized, "", "")
    
    @classmethod
    def validate_url(cls, url: Any, field_name: str = "URL") -> ValidationResult:
        """
        Valida URL con verificaciones de seguridad.
        
        Args:
            url: URL a validar
            field_name: Nombre del campo
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not url:
            return ValidationResult(False, None, f"{field_name} es requerido", "MISSING_URL")
        
        url_str = str(url).strip()
        
        # Verificar longitud
        if len(url_str) > 2048:
            return ValidationResult(False, None, f"{field_name} demasiado largo", "URL_TOO_LONG")
        
        try:
            parsed = urlparse(url_str)
            
            # Verificar esquema
            if parsed.scheme not in ['http', 'https']:
                return ValidationResult(False, None, f"{field_name} debe usar HTTP o HTTPS", "INVALID_URL_SCHEME")
            
            # Verificar que tenga host
            if not parsed.netloc:
                return ValidationResult(False, None, f"{field_name} debe tener un host válido", "INVALID_URL_HOST")
            
            # Verificar contra IPs privadas/localhost para webhooks
            if field_name.lower() == "webhook":
                if any(danger in parsed.netloc.lower() for danger in ['localhost', '127.0.0.1', '0.0.0.0', '10.', '192.168.', '172.']):
                    return ValidationResult(False, None, "Webhook URL no puede apuntar a IPs privadas", "PRIVATE_WEBHOOK_URL")
            
            return ValidationResult(True, url_str, "", "")
            
        except Exception:
            return ValidationResult(False, None, f"Formato de {field_name} inválido", "INVALID_URL_FORMAT")
    
    @classmethod
    def validate_workflow_type(cls, workflow_type: Any) -> ValidationResult:
        """
        Valida tipo de workflow permitido.
        
        Args:
            workflow_type: Tipo de workflow a validar
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        if not workflow_type:
            return ValidationResult(False, None, "Workflow type es requerido", "MISSING_WORKFLOW_TYPE")
        
        workflow_str = str(workflow_type).strip().upper()
        
        # Lista de workflows permitidos
        allowed_workflows = {
            "BUSQUEDA_HORARIOS",
            "AGENDA_COMPLETA", 
            "ACTUALIZACION_COMPLETA",
            "CANCELACION_WORKFLOW",
            "COMUNICACION_EVENTO"
        }
        
        if workflow_str not in allowed_workflows:
            return ValidationResult(
                False, 
                None, 
                f"Workflow type '{workflow_str}' no permitido. Permitidos: {', '.join(allowed_workflows)}", 
                "INVALID_WORKFLOW_TYPE"
            )
        
        return ValidationResult(True, workflow_str, "", "")

class SecurityAuditLogger:
    """Logger especializado para eventos de seguridad."""
    
    def __init__(self):
        self.logger = logging.getLogger("security_audit")
    
    def log_validation_failure(self, field_name: str, error_code: str, error_message: str, 
                             user_id: str = None, project_id: str = None, ip_address: str = None):
        """
        Registra fallos de validación para auditoría de seguridad.
        
        Args:
            field_name: Nombre del campo que falló la validación
            error_code: Código de error
            error_message: Mensaje de error
            user_id: ID del usuario (opcional)
            project_id: ID del proyecto (opcional)
            ip_address: Dirección IP (opcional)
        """
        audit_data = {
            "event_type": "VALIDATION_FAILURE",
            "field_name": field_name,
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "project_id": project_id,
            "ip_address": ip_address
        }
        
        self.logger.warning(f"Security validation failure: {audit_data}")
    
    def log_dangerous_input(self, field_name: str, pattern_matched: str, 
                           user_id: str = None, project_id: str = None):
        """
        Registra detección de entrada peligrosa.
        
        Args:
            field_name: Nombre del campo
            pattern_matched: Patrón peligroso detectado
            user_id: ID del usuario (opcional)
            project_id: ID del proyecto (opcional)
        """
        audit_data = {
            "event_type": "DANGEROUS_INPUT_DETECTED",
            "field_name": field_name,
            "pattern_matched": pattern_matched,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "project_id": project_id
        }
        
        self.logger.error(f"Dangerous input detected: {audit_data}")