"""
Gestor especializado para operaciones de contactos.
Maneja persistencia y gestión de datos de contactos de forma eficiente.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.controler.chat.core.agenda_workflow.db_pool_manager import db_pool
from app.controler.chat.core.security.input_validator import InputValidator
from app.controler.chat.core.security.error_handler import raise_calendar_error, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)

class ContactManager:
    """
    Gestor especializado para operaciones de contactos.
    Responsabilidad única: CRUD de contactos con validación y optimización.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._contact_cache = {}  # Cache simple para contactos frecuentes
        self.cache_ttl = 300  # 5 minutos
        
        # Configuración de timeouts y retry
        self.operation_timeout = 10.0  # 10 segundos
        self.max_retries = 3
    
    async def update_or_create_contact(self,
                                     user_id: str,
                                     project_id: str,
                                     email: str = "",
                                     name: str = "",
                                     phone: str = "",
                                     additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Actualiza o crea un contacto con validación completa.
        
        Args:
            user_id: ID del usuario
            project_id: ID del proyecto
            email: Email del contacto
            name: Nombre del contacto
            phone: Teléfono del contacto
            additional_data: Datos adicionales
            
        Returns:
            Resultado de la operación
        """
        try:
            # Validar datos de entrada
            validation_errors = []
            
            # Validar user_id y project_id
            user_validation = InputValidator.validate_user_id(user_id)
            if not user_validation.is_valid:
                validation_errors.append(f"user_id: {user_validation.error_message}")
            
            project_validation = InputValidator.validate_project_id(project_id)
            if not project_validation.is_valid:
                validation_errors.append(f"project_id: {project_validation.error_message}")
            
            # Validar email si se proporciona
            if email:
                email_validation = InputValidator.validate_email(email)
                if not email_validation.is_valid:
                    validation_errors.append(f"email: {email_validation.error_message}")
                else:
                    email = email_validation.sanitized_value
            
            # Validar nombre si se proporciona
            if name:
                name_validation = InputValidator.validate_text_input(name, "name", max_length=100)
                if not name_validation.is_valid:
                    validation_errors.append(f"name: {name_validation.error_message}")
                else:
                    name = name_validation.sanitized_value
            
            # Validar teléfono si se proporciona
            if phone:
                phone_validation = InputValidator.validate_text_input(phone, "phone", max_length=20)
                if not phone_validation.is_valid:
                    validation_errors.append(f"phone: {phone_validation.error_message}")
                else:
                    phone = phone_validation.sanitized_value
            
            if validation_errors:
                raise_calendar_error(
                    f"Errores de validación en contacto: {'; '.join(validation_errors)}",
                    ErrorCategory.VALIDATION,
                    ErrorSeverity.MEDIUM,
                    "CONTACT_VALIDATION_ERROR"
                )
            
            # Usar valores validados
            user_id = user_validation.sanitized_value
            project_id = project_validation.sanitized_value
            
            # Verificar si el contacto ya existe
            existing_contact = await self.get_contact(user_id, project_id)
            
            # Preparar datos del contacto
            contact_data = {
                "user_id": user_id,
                "project_id": project_id,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Agregar datos solo si no están vacíos
            if email:
                contact_data["email"] = email
            if name:
                contact_data["name"] = name
            if phone:
                contact_data["phone_number"] = phone  # CORRECCIÓN: usar phone_number en lugar de phone
            
            # Fusionar datos adicionales
            if additional_data:
                # Validar datos adicionales
                for key, value in additional_data.items():
                    if isinstance(value, str):
                        validated = InputValidator.validate_text_input(value, key, max_length=500)
                        if validated.is_valid:
                            contact_data[key] = validated.sanitized_value
            
            # Ejecutar operación con pool optimizado y timeout
            try:
                if existing_contact:
                    # Actualizar contacto existente con retry automático
                    result = await asyncio.wait_for(
                        db_pool.execute_with_retry(
                            self._update_contact_sync,
                            max_retries=self.max_retries,
                            user_id=user_id,
                            project_id=project_id,
                            contact_data=contact_data
                        ),
                        timeout=self.operation_timeout
                    )
                else:
                    # Crear nuevo contacto con retry automático
                    contact_data["created_at"] = datetime.utcnow().isoformat()
                    result = await asyncio.wait_for(
                        db_pool.execute_with_retry(
                            self._create_contact_sync,
                            max_retries=self.max_retries,
                            contact_data=contact_data
                        ),
                        timeout=self.operation_timeout
                    )
            except asyncio.TimeoutError:
                raise_calendar_error(
                    "Timeout ejecutando operación de contacto",
                    ErrorCategory.DATABASE,
                    ErrorSeverity.HIGH,
                    "CONTACT_OPERATION_TIMEOUT"
                )
            
            # Invalidar cache
            cache_key = f"{user_id}:{project_id}"
            self._contact_cache.pop(cache_key, None)
            
            self.logger.info(f"Contacto {'actualizado' if existing_contact else 'creado'} para user {user_id}")
            
            return {
                'success': True,
                'contact_data': result,
                'operation': 'updated' if existing_contact else 'created'
            }
            
        except Exception as e:
            self.logger.error(f"Error gestionando contacto: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_contact(self, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un contacto específico con cache.
        
        Args:
            user_id: ID del usuario
            project_id: ID del proyecto
            
        Returns:
            Datos del contacto o None si no existe
        """
        try:
            # Verificar cache primero
            cache_key = f"{user_id}:{project_id}"
            cached_contact = self._get_from_cache(cache_key)
            
            if cached_contact is not None:
                return cached_contact
            
            # Buscar en base de datos con pool optimizado
            contact = await asyncio.wait_for(
                db_pool.execute_with_retry(
                    self._get_contact_sync,
                    max_retries=self.max_retries,
                    user_id=user_id,
                    project_id=project_id
                ),
                timeout=self.operation_timeout
            )
            
            # Cachear resultado
            self._set_cache(cache_key, contact)
            
            return contact
            
        except Exception as e:
            self.logger.error(f"Error obteniendo contacto: {str(e)}")
            return None
    
    async def search_contacts(self, 
                            project_id: str,
                            search_term: str = "",
                            limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca contactos en un proyecto.
        
        Args:
            project_id: ID del proyecto
            search_term: Término de búsqueda
            limit: Límite de resultados
            
        Returns:
            Lista de contactos encontrados
        """
        try:
            # Validar project_id
            project_validation = InputValidator.validate_project_id(project_id)
            if not project_validation.is_valid:
                raise_calendar_error(
                    f"project_id inválido: {project_validation.error_message}",
                    ErrorCategory.VALIDATION,
                    ErrorSeverity.MEDIUM,
                    "INVALID_PROJECT_ID"
                )
            
            project_id = project_validation.sanitized_value
            
            # Validar término de búsqueda si se proporciona
            if search_term:
                search_validation = InputValidator.validate_text_input(search_term, "search_term", max_length=100)
                if not search_validation.is_valid:
                    raise_calendar_error(
                        f"Término de búsqueda inválido: {search_validation.error_message}",
                        ErrorCategory.VALIDATION,
                        ErrorSeverity.MEDIUM,
                        "INVALID_SEARCH_TERM"
                    )
                search_term = search_validation.sanitized_value
            
            # Buscar contactos con pool optimizado
            contacts = await asyncio.wait_for(
                db_pool.execute_with_retry(
                    self._search_contacts_sync,
                    max_retries=self.max_retries,
                    project_id=project_id,
                    search_term=search_term,
                    limit=limit
                ),
                timeout=self.operation_timeout
            )
            
            return contacts
            
        except Exception as e:
            self.logger.error(f"Error buscando contactos: {str(e)}")
            return []
    
    def _get_contact_sync(self, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene contacto de forma síncrona usando SupabaseClient directo."""
        from app.controler.chat.store.supabase_client import SupabaseClient
        try:
            client = SupabaseClient()
            response = client.client.table("contacts").select("*").eq("user_id", user_id).eq("project_id", project_id).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error en get_contact_sync: {str(e)}")
            return None
    
    def _create_contact_sync(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea contacto de forma síncrona."""
        from app.controler.chat.store.supabase_client import SupabaseClient
        try:
            client = SupabaseClient()
            response = client.client.table("contacts").insert(contact_data).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            raise Exception("No se pudo crear el contacto")
            
        except Exception as e:
            self.logger.error(f"Error en create_contact_sync: {str(e)}")
            raise
    
    def _update_contact_sync(self, user_id: str, project_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza contacto de forma síncrona."""
        from app.controler.chat.store.supabase_client import SupabaseClient
        try:
            client = SupabaseClient()
            
            # CRÍTICO: Filtrar campos que no existen en la tabla
            safe_contact_data = contact_data.copy()
            # Remover 'phone' si causa problemas de schema
            if 'phone' in safe_contact_data:
                self.logger.warning("Removiendo campo 'phone' - columna no disponible en tabla contacts")
                del safe_contact_data['phone']
            
            response = client.client.table("contacts").update(safe_contact_data).eq("user_id", user_id).eq("project_id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            raise Exception("No se pudo actualizar el contacto")
            
        except Exception as e:
            self.logger.error(f"Error en update_contact_sync: {str(e)}")
            raise
    
    def _search_contacts_sync(self, project_id: str, search_term: str, limit: int) -> List[Dict[str, Any]]:
        """Busca contactos de forma síncrona."""
        from app.controler.chat.store.supabase_client import SupabaseClient
        try:
            client = SupabaseClient()
            query = client.client.table("contacts").select("*").eq("project_id", project_id)
            
            if search_term:
                # Buscar en nombre o email
                query = query.or_(f"name.ilike.%{search_term}%,email.ilike.%{search_term}%")
            
            query = query.limit(limit).order("updated_at", desc=True)
            response = query.execute()
            
            return response.data or []
            
        except Exception as e:
            self.logger.error(f"Error en search_contacts_sync: {str(e)}")
            return []
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene valor del cache con TTL."""
        if key in self._contact_cache:
            cached_item = self._contact_cache[key]
            if datetime.utcnow().timestamp() - cached_item['timestamp'] < self.cache_ttl:
                return cached_item['data']
            else:
                # Cache expirado, eliminar
                del self._contact_cache[key]
        
        return None
    
    def _set_cache(self, key: str, data: Any) -> None:
        """Establece valor en cache con timestamp."""
        self._contact_cache[key] = {
            'data': data,
            'timestamp': datetime.utcnow().timestamp()
        }
        
        # Limpiar cache antiguo si está muy grande
        if len(self._contact_cache) > 100:
            self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Limpia entradas expiradas del cache."""
        current_time = datetime.utcnow().timestamp()
        expired_keys = [
            key for key, value in self._contact_cache.items()
            if current_time - value['timestamp'] > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self._contact_cache[key]
        
        self.logger.debug(f"Cache cleanup: eliminadas {len(expired_keys)} entradas expiradas")
    
    def get_contact_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del gestor de contactos."""
        return {
            'cache_size': len(self._contact_cache),
            'cache_ttl': self.cache_ttl
        }