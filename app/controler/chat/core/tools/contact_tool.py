from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from app.controler.chat.services.contact_service import ContactService
from pydantic import Field, PrivateAttr
import asyncio
import logging
import json

# ===========================
# FUNCIONES INDEPENDIENTES EXTENDIDAS
# ===========================

async def get_contact_async(project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Función independiente para obtener información de contacto completa (campos base + adicionales).
    
    Parámetros:
    - project_id: ID del proyecto
    - user_id: ID del usuario
    
    Retorna:
    - Dict con información completa del contacto o None si no existe
    
    Ejemplo de uso:
    ```python
    from app.controler.chat.core.tools.contact_tool import get_contact_async
    
    contact = await get_contact_async("proj_123", "user_456")
    if contact:
        print(f"Nombre: {contact.get('name')}")
        print(f"Email: {contact.get('email')}")
        print(f"Campos adicionales: {contact.get('additional_fields', {})}")
    ```
    """
    try:
        contact_service = ContactService()
        contact = await contact_service.get_contact_by_user_id(project_id, user_id)
        
        if contact and contact.get('additional_fields'):
            # Si viene como string (backward compatibility), parsearlo a dict
            if isinstance(contact['additional_fields'], str):
                try:
                    contact['additional_fields'] = json.loads(contact['additional_fields'])
                except json.JSONDecodeError:
                    contact['additional_fields'] = {}
            # Si ya es un dict, dejarlo como está (JSONB devuelve dict directamente)
                
        return contact
    except Exception as e:
        logging.error(f"Error obteniendo contacto: {str(e)}")
        return None

async def save_contact_async(
    project_id: str, 
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None,
    lead_status: Optional[str] = None,
    additional_fields: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Función independiente para guardar o actualizar información de contacto completa.
    SOLO guarda campos adicionales que estén definidos en contact_field_configs.
    
    Parámetros:
    - project_id: ID del proyecto
    - user_id: ID del usuario
    - name: Nombre del contacto (opcional)
    - email: Email del contacto (opcional)
    - phone_number: Teléfono del contacto (opcional)
    - lead_status: Estado del lead ('new', 'engaged', 'qualified', 'converted') (opcional)
    - additional_fields: Campos adicionales como dict (opcional)
    
    Retorna:
    - Dict con información actualizada del contacto o None si falló
    
    Ejemplo de uso:
    ```python
    from app.controler.chat.core.tools.contact_tool import save_contact_async
    
    # Guardar contacto con campos adicionales
    contact = await save_contact_async(
        project_id="proj_123",
        user_id="user_456",
        name="Juan Pérez",
        email="juan@email.com",
        additional_fields={
            "direccion": "Santiago Centro",  # Solo si está en contact_field_configs
            "edad": 35,                      # Solo si está en contact_field_configs
            "ha_invertido": True            # Solo si está en contact_field_configs
        }
    )
    ```
    """
    try:
        contact_service = ContactService()
        
        # Filtrar campos adicionales para usar solo los configurados
        filtered_additional_fields = None
        if additional_fields:
            # Obtener configuración del proyecto
            project_config = await contact_service.get_project_field_config(project_id)
            if project_config:
                # Solo guardar campos que estén en la configuración
                filtered_additional_fields = {
                    key: value for key, value in additional_fields.items() 
                    if key in project_config
                }
            # Si no hay configuración del proyecto, no guardar campos adicionales
            
        return await contact_service.save_or_update_contact(
            project_id, user_id, name, phone_number, email, lead_status, filtered_additional_fields
        )
    except Exception as e:
        logging.error(f"Error guardando contacto: {str(e)}")
        return None

async def auto_extract_fields_async(
    project_id: str,
    user_id: str,
    conversation_text: str
) -> Optional[Dict[str, Any]]:
    """
    Función independiente para extraer campos automáticamente usando la configuración del proyecto.
    
    Parámetros:
    - project_id: ID del proyecto
    - user_id: ID del usuario  
    - conversation_text: Texto completo de la conversación
    
    Retorna:
    - Dict con los campos extraídos y guardados automáticamente
    
    Ejemplo de uso:
    ```python
    from app.controler.chat.core.tools.contact_tool import auto_extract_fields_async
    
    result = await auto_extract_fields_async(
        "proj_123", "user_456", 
        "Hola, tengo 30 años y vivo en Santiago"
    )
    ```
    """
    try:
        contact_service = ContactService()
        extraction_result = await contact_service.auto_extract_from_conversation(
            project_id, conversation_text
        )
        
        if extraction_result:
            base_fields = extraction_result.get('base_fields', {})
            additional_fields = extraction_result.get('additional_fields', {})
            
            # Solo guardar si hay información para guardar
            if any([base_fields.get('name'), base_fields.get('email'), 
                   base_fields.get('phone_number'), additional_fields]):
                
                return await save_contact_async(
                    project_id, 
                    user_id, 
                    name=base_fields.get('name'),
                    email=base_fields.get('email'),
                    phone_number=base_fields.get('phone_number'),
                    additional_fields=additional_fields if additional_fields else None
                )
        
        return None
    except Exception as e:
        logging.error(f"Error en extracción automática: {str(e)}")
        return None

async def extract_additional_fields_async(
    project_id: str,
    user_id: str,
    conversation_text: str,
    field_config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Función independiente para extraer campos adicionales de una conversación.
    
    Parámetros:
    - project_id: ID del proyecto
    - user_id: ID del usuario  
    - conversation_text: Texto completo de la conversación
    - field_config: Configuración de campos a extraer
    
    Retorna:
    - Dict con los campos extraídos y guardados
    
    Ejemplo de uso:
    ```python
    from app.controler.chat.core.tools.contact_tool import extract_additional_fields_async
    
    config = {
        "direccion": {
            "keywords": ["vivo en", "mi dirección"],
            "type": "string"
        },
        "edad": {
            "keywords": ["tengo", "años"],
            "type": "number"
        }
    }
    
    result = await extract_additional_fields_async(
        "proj_123", "user_456", 
        "Hola, me llamo Juan, tengo 30 años y vivo en Santiago", 
        config
    )
    ```
    """
    try:
        contact_service = ContactService()
        extracted_fields = contact_service.extract_additional_fields_with_llm(
            conversation_text, field_config
        )
        
        if extracted_fields:
            # Guardar los campos extraídos
            return await save_contact_async(
                project_id, user_id, additional_fields=extracted_fields
            )
        
        return None
    except Exception as e:
        logging.error(f"Error extrayendo campos adicionales: {str(e)}")
        return None

def get_contact_sync(project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Función síncrona para obtener información de contacto completa.
    
    Wrapper síncrono para get_contact_async usando asyncio.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(get_contact_async(project_id, user_id))
                )
                return future.result()
        else:
            return asyncio.run(get_contact_async(project_id, user_id))
    except Exception as e:
        logging.error(f"Error en get_contact_sync: {str(e)}")
        return None

def save_contact_sync(
    project_id: str, 
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None,
    lead_status: Optional[str] = None,
    additional_fields: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Función síncrona para guardar o actualizar información de contacto completa.
    
    Wrapper síncrono para save_contact_async usando asyncio.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(save_contact_async(
                        project_id, user_id, name, email, phone_number, lead_status, additional_fields
                    ))
                )
                return future.result()
        else:
            return asyncio.run(save_contact_async(
                project_id, user_id, name, email, phone_number, lead_status, additional_fields
            ))
    except Exception as e:
        logging.error(f"Error en save_contact_sync: {str(e)}")
        return None

def format_contact_info(contact: Optional[Dict[str, Any]]) -> str:
    """
    Función utilitaria para formatear información de contacto completa.
    
    Parámetros:
    - contact: Dict con información del contacto
    
    Retorna:
    - String formateado con la información completa
    """
    if not contact:
        return "No hay información de contacto disponible"
    
    base_info = f""" INFORMACIÓN DE CONTACTO:
 Nombre: {contact.get('name', 'No disponible')}
 Email: {contact.get('email', 'No disponible')}
 Teléfono: {contact.get('phone_number', 'No disponible')}
 Estado del Lead: {contact.get('lead_status', 'new')}"""

    # Agregar campos adicionales si existen
    additional_fields = contact.get('additional_fields', {})
    if additional_fields:
        # Manejar tanto string (backward compatibility) como dict (JSONB)
        if isinstance(additional_fields, str):
            try:
                additional_fields = json.loads(additional_fields)
            except:
                additional_fields = {}
        
        if additional_fields and isinstance(additional_fields, dict):
            base_info += "\n\n INFORMACIÓN ADICIONAL:"
            for key, value in additional_fields.items():
                formatted_key = key.replace('_', ' ').title()
                base_info += f"\n• {formatted_key}: {value}"
    
    return base_info

def get_field_config_examples() -> Dict[str, Dict]:
    """
    Función para obtener ejemplos de configuraciones de campos.
    
    Retorna:
    - Dict con ejemplos de configuraciones para diferentes tipos de bot
    """
    contact_service = ContactService()
    return contact_service.get_field_configuration_examples()

# ===========================
# HERRAMIENTA PRINCIPAL EXTENDIDA
# ===========================

class SaveContactTool(BaseTool):
    project_id: str = Field(description="ID del proyecto")
    user_id: str = Field(description="ID del usuario")
    _contact_service: ContactService = PrivateAttr()
    
    def __init__(self, project_id: str, user_id: str):
        super().__init__(
            name="save_contact_tool",
            coroutine=self._arun,  # Usar método asíncrono por defecto para mejor rendimiento
            description="""
             HERRAMIENTA INTELIGENTE DE GESTIÓN DE CONTACTOS CON CONTROL DE CALIDAD Y LEAD TRACKING
            
            🚨 IMPORTANTE PARA EL ASISTENTE:
            - Si el usuario envía SOLO un número (ej: "312321312", "987654321"), 
              usar: save_contact_tool(phone_number="312321312")
            - Si el usuario envía SOLO un email (ej: "juan@gmail.com"),
              usar: save_contact_tool(email="juan@gmail.com") 
            - Si el usuario envía SOLO un nombre (ej: "María González"),
              usar: save_contact_tool(name="María González")
            - NUNCA llamar save_contact_tool() sin parámetros cuando el usuario proporcionó información
            
            ====================================================================
             PROPÓSITO: Sistema controlado de captura y almacenamiento de información 
            de contacto. SOLO guarda campos adicionales definidos en contact_field_configs 
            para mantener la data limpia y estructurada.
            ====================================================================
            
             CAPACIDADES PRINCIPALES:
            
             CAMPOS BASE (UNIVERSALES):
            • Nombre completo del usuario
            • Email de contacto  
            • Número de teléfono
            • Lead Status: 'new' → 'engaged' → 'qualified' → 'converted'
            
             CAMPOS DINÁMICOS (CONFIGURADOS EN contact_field_configs):
            • SOLO campos definidos en la tabla contact_field_configs del proyecto
            • Bot de Inversiones: dirección, ciudad, edad, ha_invertido, experiencia_inversión
            • Bot de E-commerce: producto_interés, presupuesto, fecha_compra, método_pago
            • Bot de Servicios: tipo_servicio, urgencia, disponibilidad
            • NO guarda campos que no estén configurados (mantiene data limpia)
            
             EXTRACCIÓN INTELIGENTE:
            • Analiza conversaciones completas para detectar información
            • Usa palabras clave configurables para cada campo
            • Soporta diferentes tipos de datos: string, number, boolean
            • Combina información existente con nueva información sin pérdida
            
            =====================================================================
             MODOS DE OPERACIÓN:
            =====================================================================
            
             1. CAPTURA BÁSICA (SIN PARÁMETROS):
            save_contact_tool()
            → Muestra información existente del usuario
            → Si no existe, explica cómo capturar información
            
             2. ALMACENAMIENTO SELECTIVO (CAMPOS BASE):
            save_contact_tool(name="Juan Pérez")
            save_contact_tool(email="juan@email.com")
            save_contact_tool(phone_number="123456789")
            save_contact_tool(name="Juan", email="juan@email.com", phone_number="123456789")
            save_contact_tool(lead_status="engaged")  # Usuario muestra interés
            save_contact_tool(lead_status="qualified")  # Usuario pregunta precios/detalles
            save_contact_tool(lead_status="converted")  # Usuario compra/contrata
            
             3. CAMPOS DINÁMICOS (SOLO CONFIGURADOS):
            save_contact_tool(additional_fields='{"direccion": "Santiago", "edad": 30, "ha_invertido": true}')
            #  SOLO guarda campos que existan en contact_field_configs del proyecto
            save_contact_tool(name="Juan", additional_fields='{"producto_interes": "Laptop", "presupuesto": 500000}')
            
             4. EXTRACCIÓN AUTOMÁTICA CON CONFIGURACIÓN DEL PROYECTO:
            save_contact_tool(
                conversation_text="Hola, soy María, tengo 25 años y vivo en Valparaíso. He invertido antes en acciones.",
                auto_extract=true
            )
            
             5. EXTRACCIÓN AUTOMÁTICA CON CONFIGURACIÓN MANUAL:
            save_contact_tool(
                conversation_text="Hola, soy María, tengo 25 años y vivo en Valparaíso. He invertido antes en acciones.",
                field_config='{"edad": {"keywords": ["tengo", "años"], "type": "number"}, "ciudad": {"keywords": ["vivo en"], "type": "string"}, "ha_invertido": {"keywords": ["he invertido", "inversión"], "type": "boolean"}}'
            )
            
            =====================================================================
             CONFIGURACIONES PREDEFINIDAS POR TIPO DE BOT:
            =====================================================================
            
             BOT DE INVERSIONES:
            {
                "direccion": {"keywords": ["vivo en", "mi dirección"], "type": "string"},
                "ciudad": {"keywords": ["ciudad", "vivo en"], "type": "string"},  
                "edad": {"keywords": ["tengo", "años"], "type": "number"},
                "ha_invertido": {"keywords": ["he invertido", "inversión", "broker"], "type": "boolean"},
                "experiencia_inversion": {"keywords": ["experiencia", "años invirtiendo"], "type": "string"}
            }
            
             BOT DE E-COMMERCE:
            {
                "producto_interes": {"keywords": ["me interesa", "quiero", "busco"], "type": "string"},
                "presupuesto": {"keywords": ["presupuesto", "puedo pagar"], "type": "number"},
                "fecha_compra": {"keywords": ["cuando", "fecha", "para cuándo"], "type": "string"},
                "metodo_pago": {"keywords": ["pago", "transferencia", "tarjeta"], "type": "string"}
            }
            
             BOT DE SERVICIOS:
            {
                "tipo_servicio": {"keywords": ["necesito", "servicio", "requiero"], "type": "string"},
                "urgencia": {"keywords": ["urgente", "pronto", "rápido"], "type": "string"},
                "disponibilidad": {"keywords": ["disponible", "horario", "prefiero"], "type": "string"}
            }
            
            =====================================================================
             EJEMPLOS DE USO PRÁCTICOS:
            =====================================================================
            
             CASO 1 - Usuario menciona información básica:
            Usuario: "Hola, soy Juan Pérez, mi email es juan@gmail.com"
            → save_contact_tool(name="Juan Pérez", email="juan@gmail.com")
            
             CASO 2 - Usuario da información específica de inversiones:
            Usuario: "Tengo 35 años, vivo en Santiago y ya he invertido en acciones antes"
            → save_contact_tool(
                conversation_text="Tengo 35 años, vivo en Santiago y ya he invertido en acciones antes",
                field_config='{"edad": {"keywords": ["tengo", "años"], "type": "number"}, "ciudad": {"keywords": ["vivo en"], "type": "string"}, "ha_invertido": {"keywords": ["he invertido", "acciones"], "type": "boolean"}}'
            )
            
             CASO 3 - Actualización de información específica:
            → save_contact_tool(additional_fields='{"presupuesto": 1000000, "urgencia": "alta"}')
            
            =====================================================================
             INTEGRACIÓN AUTOMÁTICA:
            =====================================================================
            • Se integra con google_calendar_tool para emails automáticos
            • Proporciona datos a send_email para personalización
            • Soporte para APIs que requieren información del usuario
            • Usado por otras herramientas para obtener datos del usuario
            
            =====================================================================
             FUNCIONALIDADES AVANZADAS:
            =====================================================================
            • Validación automática de formatos (email, teléfono)
            • Combinación inteligente de información nueva con existente
            • Soporte para múltiples tipos de datos (string, number, boolean)
            • Mensajes informativos sobre cambios realizados
            • Prevención de pérdida de datos en actualizaciones
            
            Parámetros (todos opcionales):
            - name: Nombre completo del usuario
            - email: Dirección de correo electrónico válida  
            - phone_number: Número de teléfono en cualquier formato
            - lead_status: Estado del lead ('new', 'engaged', 'qualified', 'converted')
            - additional_fields: JSON string con campos adicionales {"campo": "valor"}
            - conversation_text: Texto de conversación para extraer información
            - field_config: JSON string con configuración de campos a extraer
            - auto_extract: Boolean para usar configuración automática del proyecto
            """,
            project_id=project_id,
            user_id=user_id
        )
        self._contact_service = ContactService()

    async def _get_existing_contact(self) -> Optional[dict]:
        """Obtiene la información de contacto existente para el usuario actual."""
        return await get_contact_async(self.project_id, self.user_id)

    def _format_contact_info(self, contact: dict) -> str:
        """Formatea la información del contacto para mostrarla."""
        return format_contact_info(contact)

    def _parse_additional_fields(self, additional_fields_str: str) -> Dict[str, Any]:
        """Parsea el string JSON de campos adicionales."""
        try:
            return json.loads(additional_fields_str)
        except json.JSONDecodeError:
            return {}

    def _parse_field_config(self, field_config_str: str) -> Dict[str, Any]:
        """Parsea el string JSON de configuración de campos."""
        try:
            return json.loads(field_config_str)
        except json.JSONDecodeError:
            return {}

    def _extract_recent_user_message(self) -> Optional[str]:
        """
        Simula la extracción del mensaje más reciente del usuario.
        En una implementación real, esto vendría del contexto de la conversación.
        """
        # Por ahora, retornar None para que use conversation_text si está disponible
        # En el futuro, esto se puede conectar al contexto real de la conversación
        return None
    
    def _validate_status_transition(self, current_status: str, new_status: str) -> bool:
        """
        Valida que la transición de estado sea lógica.
        Retorna True si la transición es válida, False si no lo es.
        """
        # Definir transiciones válidas
        valid_transitions = {
            'nuevo_chat': ['eligiendo_servicio', 'recopilando_datos'],
            'eligiendo_servicio': ['eligiendo_horario', 'recopilando_datos'],
            'eligiendo_horario': ['recopilando_datos', 'esperando_confirmacion'],
            'recopilando_datos': ['esperando_confirmacion', 'eligiendo_servicio', 'eligiendo_horario'],
            'esperando_confirmacion': ['reservado', 'eligiendo_horario'],
            'reservado': []  # Estado final, no debería cambiar
        }
        
        # Si no hay estado actual, cualquier estado es válido
        if not current_status:
            return True
            
        # Si el estado actual es el mismo que el nuevo, es válido
        if current_status == new_status:
            return True
            
        # Verificar si la transición está en la lista de transiciones válidas
        return new_status in valid_transitions.get(current_status, [])
    
    def _get_next_expected_status(self, current_status: str) -> str:
        """
        Retorna el próximo estado esperado en el flujo.
        """
        next_status_map = {
            'nuevo_chat': 'eligiendo_servicio',
            'eligiendo_servicio': 'eligiendo_horario',
            'eligiendo_horario': 'recopilando_datos',
            'recopilando_datos': 'esperando_confirmacion',
            'esperando_confirmacion': 'reservado',
            'reservado': 'reservado'
        }
        return next_status_map.get(current_status, 'nuevo_chat')
    
    def _detect_lead_status(self, message: str) -> Optional[str]:
        """
        Detecta automáticamente el estado del lead basado en el contenido del mensaje.
        
        Estados para sistema de agendamiento:
            'nuevo_chat': Usuario inició contacto
            'eligiendo_servicio': Usuario está eligiendo qué servicio necesita
            'eligiendo_horario': Usuario está seleccionando fecha y hora
            'recopilando_datos': Usuario está dando sus datos personales
            'esperando_confirmacion': Cita armada, esperando confirmación
            'reservado': Cita confirmada y agendada
        """
        if not message:
            return None
            
        message_lower = message.lower()
        
        # Patrones para 'reservado' (confirmación final)
        reservado_patterns = [
            'confirmo', 'sí acepto', 'perfecto', 'de acuerdo',
            'está bien', 'confirmado', 'lo confirmo', 'si, confirmo',
            'sí, por favor', 'adelante', 'procedamos'
        ]
        
        # Patrones para 'recopilando_datos' (dando información personal)
        datos_patterns = [
            'mi nombre es', 'me llamo', 'mi correo', 'mi email',
            'mi teléfono', 'mi número', '@', 'gmail', 'hotmail'
        ]
        
        # Patrones para 'eligiendo_horario' (combina fecha y hora)
        horario_patterns = [
            # Horarios
            'mañana', 'tarde', 'noche', ':00', ':30', ':15', ':45',
            'a las', 'prefiero', 'disponible', 'horario',
            'temprano', 'después de', 'antes de',
            # Fechas
            'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo',
            'pasado mañana', 'próxima semana', 'este mes',
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
            'hoy', 'fecha', 'día', 'cuando', 'cuándo'
        ]
        
        # Patrones para 'eligiendo_servicio'
        servicio_patterns = [
            'servicio', 'necesito', 'quiero', 'quisiera', 'me interesa',
            'consulta', 'cita', 'turno', 'reserva', 'agendar',
            'qué ofrecen', 'opciones', 'tipos de'
        ]
        
        # Verificar patrones en orden de prioridad (de más específico a menos)
        import re
        
        # Verificar si tiene formato de email
        if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}', message):
            return 'recopilando_datos'
        
        # Verificar si tiene número de teléfono
        if re.search(r'\b\d{8,12}\b', message):
            return 'recopilando_datos'
        
        for pattern in reservado_patterns:
            if pattern in message_lower:
                return 'reservado'
                
        for pattern in datos_patterns:
            if pattern in message_lower:
                return 'recopilando_datos'
                
        for pattern in horario_patterns:
            if pattern in message_lower:
                return 'eligiendo_horario'
                
        for pattern in servicio_patterns:
            if pattern in message_lower:
                return 'eligiendo_servicio'
                
        # Si no se detecta ningún patrón específico, es un nuevo chat
        return 'nuevo_chat'
    
    def _extract_basic_contact_info(self, message: str) -> Dict[str, Optional[str]]:
        """
        Extrae información básica de contacto usando patrones simples.
        Especialmente útil para números de teléfono enviados como texto plano.
        """
        contact_info = {
            "name": None,
            "email": None,  
            "phone_number": None
        }
        
        import re
        
        # Patrón para email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            contact_info["email"] = email_match.group(0)
        
        # Patrón para números de teléfono - más flexible para números como "342423423"
        phone_patterns = [
            r'\b\d{9,12}\b',  # 9-12 dígitos consecutivos (como 342423423)
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # Formatos estándar
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{3,4}\b'  # Formato chileno típico
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, message)
            if phone_match:
                phone = phone_match.group(0)
                # Validar que sea un número válido (no solo números secuenciales cortos)
                if len(re.sub(r'[^\d]', '', phone)) >= 8:  # Al menos 8 dígitos
                    contact_info["phone_number"] = phone
                    break
        
        # Patrón básico para nombres (palabras con mayúscula inicial)
        # Solo detectar si hay palabras como "soy", "me llamo", etc.
        name_patterns = [
            r'(?:soy|me llamo|mi nombre es)\s+([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)*)',
            r'([A-Z][a-záéíóúñ]+\s+[A-Z][a-záéíóúñ]+)'  # Dos palabras con mayúscula
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, message, re.IGNORECASE)
            if name_match:
                potential_name = name_match.group(1) if len(name_match.groups()) > 0 else name_match.group(0)
                # Validar que no sea un número o algo irrelevante
                if not re.match(r'^\d+$', potential_name.replace(' ', '')):
                    contact_info["name"] = potential_name.strip()
                    break
        
        return contact_info

    def _get_update_message(self, existing: dict, updated: dict) -> str:
        """Genera un mensaje describiendo los cambios realizados."""
        changes = []
        
        # Cambios en campos base
        if updated.get('name') and updated['name'] != existing.get('name'):
            changes.append(f" Nombre: {existing.get('name', 'No disponible')} → {updated['name']}")
        if updated.get('email') and updated['email'] != existing.get('email'):
            changes.append(f" Email: {existing.get('email', 'No disponible')} → {updated['email']}")
        if updated.get('phone_number') and updated['phone_number'] != existing.get('phone_number'):
            changes.append(f" Teléfono: {existing.get('phone_number', 'No disponible')} → {updated['phone_number']}")
        if updated.get('lead_status') and updated['lead_status'] != existing.get('lead_status'):
            changes.append(f" Estado del Lead: {existing.get('lead_status', 'new')} → {updated['lead_status']}")
        
        # Cambios en campos adicionales
        existing_additional = existing.get('additional_fields', {})
        updated_additional = updated.get('additional_fields', {})
        
        # Manejar backward compatibility para strings JSON
        if isinstance(existing_additional, str):
            try:
                existing_additional = json.loads(existing_additional)
            except:
                existing_additional = {}
        elif not isinstance(existing_additional, dict):
            existing_additional = {}
        
        if isinstance(updated_additional, str):
            try:
                updated_additional = json.loads(updated_additional)
            except:
                updated_additional = {}
        elif not isinstance(updated_additional, dict):
            updated_additional = {}
        
        for key, value in updated_additional.items():
            if key not in existing_additional:
                formatted_key = key.replace('_', ' ').title()
                changes.append(f" {formatted_key}: Nuevo → {value}")
            elif existing_additional[key] != value:
                formatted_key = key.replace('_', ' ').title()
                changes.append(f" {formatted_key}: {existing_additional[key]} → {value}")
        
        if changes:
            return f" INFORMACIÓN ACTUALIZADA:\n" + "\n".join(changes)
        return " No se realizaron cambios en la información."

    def _run(
        self, 
        name: Optional[str] = None, 
        email: Optional[str] = None, 
        phone_number: Optional[str] = None,
        lead_status: Optional[str] = None,
        additional_fields: Optional[str] = None,
        conversation_text: Optional[str] = None,
        field_config: Optional[str] = None,
        auto_extract: Optional[bool] = None
    ) -> str:
        """
        Herramienta para gestión completa de contactos con campos dinámicos.
        Usar _arun() para mejor rendimiento en contextos asíncronos.
        """
        try:
            # Detectar si estamos en un contexto asíncrono
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si estamos en un contexto asíncrono, usar ThreadPoolExecutor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_sync_helper, name, email, phone_number, lead_status, additional_fields, conversation_text, field_config, auto_extract)
                    return future.result()
            else:
                # Contexto síncrono, usar directamente
                return self._run_sync_helper(name, email, phone_number, lead_status, additional_fields, conversation_text, field_config, auto_extract)
                
        except Exception as e:
            return f" Error al procesar contacto: {str(e)}"

    def _run_sync_helper(
        self, 
        name: Optional[str] = None, 
        email: Optional[str] = None, 
        phone_number: Optional[str] = None,
        lead_status: Optional[str] = None,
        additional_fields: Optional[str] = None,
        conversation_text: Optional[str] = None,
        field_config: Optional[str] = None,
        auto_extract: Optional[bool] = None
    ) -> str:
        """
        Helper síncrono para ejecutar la lógica de contact_tool sin bloquear el hilo principal.
        """
        try:
            # Modo 1A: Extracción automática usando configuración del proyecto
            if conversation_text and auto_extract:
                result = asyncio.run(auto_extract_fields_async(
                    self.project_id, self.user_id, conversation_text
                ))
                if result:
                    return ""
                else:
                    # Si no se extrajo nada, mostrar información existente
                    existing = asyncio.run(self._get_existing_contact())
                    if existing:
                        return f""" No se detectaron campos nuevos para extraer.

{self._format_contact_info(existing)}"""
                    else:
                        return " No se detectó información para capturar automáticamente."
            
            # Modo 1B: Extracción con configuración manual
            if conversation_text and field_config:
                config = self._parse_field_config(field_config)
                if config:
                    result = asyncio.run(extract_additional_fields_async(
                        self.project_id, self.user_id, conversation_text, config
                    ))
                    if result:
                        return ""
                    else:
                        return " No se pudo extraer información adicional de la conversación con la configuración proporcionada."
            
            # Parsear campos adicionales si se proporcionaron
            additional_fields_dict = None
            if additional_fields:
                additional_fields_dict = self._parse_additional_fields(additional_fields)
            
            # Modo 2: Si no se proporcionó información directa, intentar extracción automática
            if not any([name, email, phone_number, lead_status, additional_fields_dict]):
                # CRÍTICO: Intentar extracción automática del último mensaje del usuario
                # Esto es especialmente importante para números de teléfono enviados como texto simple
                try:
                    # Obtener el mensaje más reciente de la conversación (usuario enviado al tool)
                    # Simular conversation_text con un mensaje típico que contenga la información
                    recent_message = conversation_text or self._extract_recent_user_message()
                    
                    if recent_message:
                        # Intentar extracción automática con la configuración del proyecto
                        extraction_result = asyncio.run(auto_extract_fields_async(
                            self.project_id, self.user_id, recent_message
                        ))
                        
                        if extraction_result:
                                return ""
                        
                        # Si la extracción automática no funcionó, intentar patrones básicos
                        basic_extraction = self._extract_basic_contact_info(recent_message)
                        if any(basic_extraction.values()):
                            extraction_result = asyncio.run(save_contact_async(
                                self.project_id, 
                                self.user_id,
                                name=basic_extraction.get('name'),
                                email=basic_extraction.get('email'), 
                                phone_number=basic_extraction.get('phone_number'),
                                lead_status=self._detect_lead_status(recent_message) if not lead_status else lead_status
                            ))
                            if extraction_result:
                                return ""
                except Exception as e:
                    # Si la extracción automática falla, continuar con el flujo normal
                    pass
                
                # Flujo original: mostrar información existente o instrucciones
                contact = asyncio.run(self._get_existing_contact())
                if contact:
                    return self._format_contact_info(contact)
                else:
                    examples = get_field_config_examples()
                    return f""" NO HAY INFORMACIÓN DE CONTACTO GUARDADA AÚN
                    
 FORMAS DE GUARDAR INFORMACIÓN:

 1. CAMPOS BÁSICOS:
• save_contact_tool(name="Juan Pérez")
• save_contact_tool(email="juan@email.com") 
• save_contact_tool(phone_number="123456789")

 2. CAMPOS DINÁMICOS:
• save_contact_tool(additional_fields='{{"direccion": "Santiago", "edad": 30}}')

 3. EXTRACCIÓN AUTOMÁTICA:
• save_contact_tool(
    conversation_text="texto de la conversación",
    field_config='{{"edad": {{"keywords": ["tengo", "años"], "type": "number"}}}}'
)

 CONFIGURACIONES PREDEFINIDAS:
• Bot de Inversiones: {list(examples['bot_inversiones'].keys())}
• Bot de E-commerce: {list(examples['bot_ecommerce'].keys())}
• Bot de Servicios: {list(examples['bot_servicios'].keys())}

IMPORTANTE: Si el usuario ha mencionado información de contacto en la conversación, 
extrae esa información y úsala para guardar los datos."""

            # Modo 3: Guardar o actualizar contacto
            try:
                existing_contact = asyncio.run(self._get_existing_contact())
            except Exception as e:
                existing_contact = None
            
            # Validar transición de estado si se proporciona lead_status
            if lead_status and existing_contact:
                current_status = existing_contact.get('lead_status', 'nuevo_chat')
                if not self._validate_status_transition(current_status, lead_status):
                    next_expected = self._get_next_expected_status(current_status)
                    return f"""⚠️ Transición de estado no válida.
                    
Estado actual: {current_status}
Estado solicitado: {lead_status}
Próximo estado esperado: {next_expected}

Para forzar el cambio, primero actualiza al estado intermedio correspondiente."""
            
            contact = asyncio.run(save_contact_async(
                self.project_id, 
                self.user_id, 
                name, 
                email,
                phone_number,
                lead_status,
                additional_fields_dict
            ))
            
            if contact:
                if existing_contact:
                    # Es una actualización
                    return ""
                else:
                    # Es un nuevo contacto
                    return ""
            else:
                return " No se pudo guardar el contacto. Verifica que la información esté en formato válido."
                
        except Exception as e:
            return f" Error al procesar contacto: {str(e)}"

    async def _arun(
        self, 
        name: Optional[str] = None, 
        email: Optional[str] = None, 
        phone_number: Optional[str] = None,
        lead_status: Optional[str] = None,
        additional_fields: Optional[str] = None,
        conversation_text: Optional[str] = None,
        field_config: Optional[str] = None,
        auto_extract: Optional[bool] = None
    ) -> str:
        """Versión asíncrona de _run"""
        try:
            # Modo extracción automática con configuración del proyecto
            if conversation_text and auto_extract:
                result = await auto_extract_fields_async(
                    self.project_id, self.user_id, conversation_text
                )
                if result:
                    return ""
                else:
                    return " No se encontró información para extraer con la configuración del proyecto."
            
            # Modo extracción automática con configuración manual
            if conversation_text and field_config:
                config = self._parse_field_config(field_config)
                if config:
                    result = await extract_additional_fields_async(
                        self.project_id, self.user_id, conversation_text, config
                    )
                    if result:
                        return ""
                    else:
                        return " No se encontró información para extraer."

            # Parsear campos adicionales
            additional_fields_dict = None
            if additional_fields:
                additional_fields_dict = self._parse_additional_fields(additional_fields)

            # Si no hay datos nuevos, intentar extracción automática o mostrar información existente
            if not any([name, email, phone_number, lead_status, additional_fields_dict]):
                # CRÍTICO: Intentar extracción automática del texto de conversación
                if conversation_text:
                    basic_extraction = self._extract_basic_contact_info(conversation_text)
                    if any(basic_extraction.values()):
                        extraction_result = await save_contact_async(
                            self.project_id, 
                            self.user_id,
                            name=basic_extraction.get('name'),
                            email=basic_extraction.get('email'), 
                            phone_number=basic_extraction.get('phone_number'),
                            lead_status=self._detect_lead_status(conversation_text) if not lead_status else lead_status
                        )
                        if extraction_result:
                                return ""
                
                # Verificar información existente
                existing_contact = await self._get_existing_contact()
                if existing_contact:
                    return self._format_contact_info(existing_contact)
                else:
                    return """❌ No se proporcionó información para guardar.
                    
⚠️ IMPORTANTE: Si el usuario envió un número de teléfono, email o nombre, 
use los parámetros correspondientes del tool (phone_number, email, name)."""

            # Guardar o actualizar información
            if any([name, email, phone_number, lead_status, additional_fields_dict]):
                # Obtener contacto existente para determinar si es creación o actualización
                try:
                    existing_contact = await self._get_existing_contact()
                except Exception as e:
                    existing_contact = None
                
                result = await save_contact_async(
                    project_id=self.project_id,
                    user_id=self.user_id,
                    name=name,
                    email=email,
                    phone_number=phone_number,
                    lead_status=lead_status,
                    additional_fields=additional_fields_dict
                )
                
                if result:
                    if existing_contact:
                        return ""
                    else:
                        return ""
                else:
                    return " No se pudo guardar la información de contacto."
            
            return " No se proporcionó información para actualizar."
                
        except Exception as e:
            logging.error(f"Error al procesar contacto: {str(e)}")
            return f" Error al procesar contacto: {str(e)}" 