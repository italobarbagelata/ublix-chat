from typing import Optional, Dict, Any, List
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
            project_id, user_id, name, phone_number, email, filtered_additional_fields
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
                        project_id, user_id, name, email, phone_number, additional_fields
                    ))
                )
                return future.result()
        else:
            return asyncio.run(save_contact_async(
                project_id, user_id, name, email, phone_number, additional_fields
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
    
    base_info = f"""📋 INFORMACIÓN DE CONTACTO:
👤 Nombre: {contact.get('name', 'No disponible')}
📧 Email: {contact.get('email', 'No disponible')}
📱 Teléfono: {contact.get('phone_number', 'No disponible')}"""

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
            base_info += "\n\n🔍 INFORMACIÓN ADICIONAL:"
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
            🚀 HERRAMIENTA INTELIGENTE DE GESTIÓN DE CONTACTOS CON CONTROL DE CALIDAD
            
            ====================================================================
            🎯 PROPÓSITO: Sistema controlado de captura y almacenamiento de información 
            de contacto. SOLO guarda campos adicionales definidos en contact_field_configs 
            para mantener la data limpia y estructurada.
            ====================================================================
            
            📋 CAPACIDADES PRINCIPALES:
            
            🔹 CAMPOS BASE (UNIVERSALES):
            • Nombre completo del usuario
            • Email de contacto  
            • Número de teléfono
            
            🔹 CAMPOS DINÁMICOS (CONFIGURADOS EN contact_field_configs):
            • SOLO campos definidos en la tabla contact_field_configs del proyecto
            • Bot de Inversiones: dirección, ciudad, edad, ha_invertido, experiencia_inversión
            • Bot de E-commerce: producto_interés, presupuesto, fecha_compra, método_pago
            • Bot de Servicios: tipo_servicio, urgencia, disponibilidad
            • NO guarda campos que no estén configurados (mantiene data limpia)
            
            🧠 EXTRACCIÓN INTELIGENTE:
            • Analiza conversaciones completas para detectar información
            • Usa palabras clave configurables para cada campo
            • Soporta diferentes tipos de datos: string, number, boolean
            • Combina información existente con nueva información sin pérdida
            
            =====================================================================
            🔧 MODOS DE OPERACIÓN:
            =====================================================================
            
            📥 1. CAPTURA BÁSICA (SIN PARÁMETROS):
            save_contact_tool()
            → Muestra información existente del usuario
            → Si no existe, explica cómo capturar información
            
            💾 2. ALMACENAMIENTO SELECTIVO (CAMPOS BASE):
            save_contact_tool(name="Juan Pérez")
            save_contact_tool(email="juan@email.com")
            save_contact_tool(phone_number="123456789")
            save_contact_tool(name="Juan", email="juan@email.com", phone_number="123456789")
            
            🎯 3. CAMPOS DINÁMICOS (SOLO CONFIGURADOS):
            save_contact_tool(additional_fields='{"direccion": "Santiago", "edad": 30, "ha_invertido": true}')
            # ⚠️ SOLO guarda campos que existan en contact_field_configs del proyecto
            save_contact_tool(name="Juan", additional_fields='{"producto_interes": "Laptop", "presupuesto": 500000}')
            
            🤖 4. EXTRACCIÓN AUTOMÁTICA CON CONFIGURACIÓN DEL PROYECTO:
            save_contact_tool(
                conversation_text="Hola, soy María, tengo 25 años y vivo en Valparaíso. He invertido antes en acciones.",
                auto_extract=true
            )
            
            🔧 5. EXTRACCIÓN AUTOMÁTICA CON CONFIGURACIÓN MANUAL:
            save_contact_tool(
                conversation_text="Hola, soy María, tengo 25 años y vivo en Valparaíso. He invertido antes en acciones.",
                field_config='{"edad": {"keywords": ["tengo", "años"], "type": "number"}, "ciudad": {"keywords": ["vivo en"], "type": "string"}, "ha_invertido": {"keywords": ["he invertido", "inversión"], "type": "boolean"}}'
            )
            
            =====================================================================
            📊 CONFIGURACIONES PREDEFINIDAS POR TIPO DE BOT:
            =====================================================================
            
            💰 BOT DE INVERSIONES:
            {
                "direccion": {"keywords": ["vivo en", "mi dirección"], "type": "string"},
                "ciudad": {"keywords": ["ciudad", "vivo en"], "type": "string"},  
                "edad": {"keywords": ["tengo", "años"], "type": "number"},
                "ha_invertido": {"keywords": ["he invertido", "inversión", "broker"], "type": "boolean"},
                "experiencia_inversion": {"keywords": ["experiencia", "años invirtiendo"], "type": "string"}
            }
            
            🛒 BOT DE E-COMMERCE:
            {
                "producto_interes": {"keywords": ["me interesa", "quiero", "busco"], "type": "string"},
                "presupuesto": {"keywords": ["presupuesto", "puedo pagar"], "type": "number"},
                "fecha_compra": {"keywords": ["cuando", "fecha", "para cuándo"], "type": "string"},
                "metodo_pago": {"keywords": ["pago", "transferencia", "tarjeta"], "type": "string"}
            }
            
            🔧 BOT DE SERVICIOS:
            {
                "tipo_servicio": {"keywords": ["necesito", "servicio", "requiero"], "type": "string"},
                "urgencia": {"keywords": ["urgente", "pronto", "rápido"], "type": "string"},
                "disponibilidad": {"keywords": ["disponible", "horario", "prefiero"], "type": "string"}
            }
            
            =====================================================================
            💡 EJEMPLOS DE USO PRÁCTICOS:
            =====================================================================
            
            📝 CASO 1 - Usuario menciona información básica:
            Usuario: "Hola, soy Juan Pérez, mi email es juan@gmail.com"
            → save_contact_tool(name="Juan Pérez", email="juan@gmail.com")
            
            📝 CASO 2 - Usuario da información específica de inversiones:
            Usuario: "Tengo 35 años, vivo en Santiago y ya he invertido en acciones antes"
            → save_contact_tool(
                conversation_text="Tengo 35 años, vivo en Santiago y ya he invertido en acciones antes",
                field_config='{"edad": {"keywords": ["tengo", "años"], "type": "number"}, "ciudad": {"keywords": ["vivo en"], "type": "string"}, "ha_invertido": {"keywords": ["he invertido", "acciones"], "type": "boolean"}}'
            )
            
            📝 CASO 3 - Actualización de información específica:
            → save_contact_tool(additional_fields='{"presupuesto": 1000000, "urgencia": "alta"}')
            
            =====================================================================
            🔄 INTEGRACIÓN AUTOMÁTICA:
            =====================================================================
            • Se integra con google_calendar_tool para emails automáticos
            • Proporciona datos a send_email para personalización
            • Soporte para APIs que requieren información del usuario
            • Usado por otras herramientas para obtener datos del usuario
            
            =====================================================================
            ⚡ FUNCIONALIDADES AVANZADAS:
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

    def _get_update_message(self, existing: dict, updated: dict) -> str:
        """Genera un mensaje describiendo los cambios realizados."""
        changes = []
        
        # Cambios en campos base
        if updated.get('name') and updated['name'] != existing.get('name'):
            changes.append(f"👤 Nombre: {existing.get('name', 'No disponible')} → {updated['name']}")
        if updated.get('email') and updated['email'] != existing.get('email'):
            changes.append(f"📧 Email: {existing.get('email', 'No disponible')} → {updated['email']}")
        if updated.get('phone_number') and updated['phone_number'] != existing.get('phone_number'):
            changes.append(f"📱 Teléfono: {existing.get('phone_number', 'No disponible')} → {updated['phone_number']}")
        
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
                changes.append(f"🔹 {formatted_key}: Nuevo → {value}")
            elif existing_additional[key] != value:
                formatted_key = key.replace('_', ' ').title()
                changes.append(f"🔹 {formatted_key}: {existing_additional[key]} → {value}")
        
        if changes:
            return f"✅ INFORMACIÓN ACTUALIZADA:\n" + "\n".join(changes)
        return "ℹ️ No se realizaron cambios en la información."

    def _run(
        self, 
        name: Optional[str] = None, 
        email: Optional[str] = None, 
        phone_number: Optional[str] = None,
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
                    future = executor.submit(self._run_sync_helper, name, email, phone_number, additional_fields, conversation_text, field_config, auto_extract)
                    return future.result()
            else:
                # Contexto síncrono, usar directamente
                return self._run_sync_helper(name, email, phone_number, additional_fields, conversation_text, field_config, auto_extract)
                
        except Exception as e:
            return f"❌ Error al procesar contacto: {str(e)}"

    def _run_sync_helper(
        self, 
        name: Optional[str] = None, 
        email: Optional[str] = None, 
        phone_number: Optional[str] = None,
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
                    return f"""✅ INFORMACIÓN CAPTURADA AUTOMÁTICAMENTE:
{self._format_contact_info(result)}

🎯 Campos detectados usando configuración del proyecto."""
                else:
                    # Si no se extrajo nada, mostrar información existente
                    existing = asyncio.run(self._get_existing_contact())
                    if existing:
                        return f"""ℹ️ No se detectaron campos nuevos para extraer.

{self._format_contact_info(existing)}"""
                    else:
                        return "ℹ️ No se detectó información para capturar automáticamente."
            
            # Modo 1B: Extracción con configuración manual
            if conversation_text and field_config:
                config = self._parse_field_config(field_config)
                if config:
                    result = asyncio.run(extract_additional_fields_async(
                        self.project_id, self.user_id, conversation_text, config
                    ))
                    if result:
                        return f"""🤖 EXTRACCIÓN AUTOMÁTICA COMPLETADA (CONFIG MANUAL):
{self._format_contact_info(result)}

✨ Se analizó la conversación y se extrajeron {len(config)} campos automáticamente."""
                    else:
                        return "🔍 No se pudo extraer información adicional de la conversación con la configuración proporcionada."
            
            # Parsear campos adicionales si se proporcionaron
            additional_fields_dict = None
            if additional_fields:
                additional_fields_dict = self._parse_additional_fields(additional_fields)
            
            # Modo 2: Si no se proporcionó información, mostrar información existente
            if not any([name, email, phone_number, additional_fields_dict]):
                contact = asyncio.run(self._get_existing_contact())
                if contact:
                    return self._format_contact_info(contact)
                else:
                    examples = get_field_config_examples()
                    return f"""📝 NO HAY INFORMACIÓN DE CONTACTO GUARDADA AÚN
                    
🔧 FORMAS DE GUARDAR INFORMACIÓN:

📋 1. CAMPOS BÁSICOS:
• save_contact_tool(name="Juan Pérez")
• save_contact_tool(email="juan@email.com") 
• save_contact_tool(phone_number="123456789")

🎯 2. CAMPOS DINÁMICOS:
• save_contact_tool(additional_fields='{{"direccion": "Santiago", "edad": 30}}')

🤖 3. EXTRACCIÓN AUTOMÁTICA:
• save_contact_tool(
    conversation_text="texto de la conversación",
    field_config='{{"edad": {{"keywords": ["tengo", "años"], "type": "number"}}}}'
)

💡 CONFIGURACIONES PREDEFINIDAS:
• Bot de Inversiones: {list(examples['bot_inversiones'].keys())}
• Bot de E-commerce: {list(examples['bot_ecommerce'].keys())}
• Bot de Servicios: {list(examples['bot_servicios'].keys())}

IMPORTANTE: Si el usuario ha mencionado información de contacto en la conversación, 
extrae esa información y úsala para guardar los datos."""

            # Modo 3: Guardar o actualizar contacto
            existing_contact = asyncio.run(self._get_existing_contact())
            
            contact = asyncio.run(save_contact_async(
                self.project_id, 
                self.user_id, 
                name, 
                email,
                phone_number,
                additional_fields_dict
            ))
            
            if contact:
                if existing_contact:
                    # Es una actualización
                    return self._get_update_message(existing_contact, contact)
                else:
                    # Es un nuevo contacto
                    return f"""🎉 NUEVO CONTACTO CREADO EXITOSAMENTE:
{self._format_contact_info(contact)}

🔄 Esta información se usará automáticamente para:
• 📧 Enviar emails personalizados
• 📅 Crear eventos de calendario con el email como asistente
• 🔌 Ejecutar APIs que requieran datos de contacto
• 🎯 Personalizar respuestas con información del usuario
• 💼 Seguimiento de leads y conversiones"""
            else:
                return "❌ No se pudo guardar el contacto. Verifica que la información esté en formato válido."
                
        except Exception as e:
            return f"❌ Error al procesar contacto: {str(e)}"

    async def _arun(
        self, 
        name: Optional[str] = None, 
        email: Optional[str] = None, 
        phone_number: Optional[str] = None,
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
                    return f"""🤖 EXTRACCIÓN AUTOMÁTICA COMPLETADA (CONFIG PROYECTO):
{self._format_contact_info(result)}"""
                else:
                    return "🔍 No se encontró información para extraer con la configuración del proyecto."
            
            # Modo extracción automática con configuración manual
            if conversation_text and field_config:
                config = self._parse_field_config(field_config)
                if config:
                    result = await extract_additional_fields_async(
                        self.project_id, self.user_id, conversation_text, config
                    )
                    if result:
                        return f"""🤖 EXTRACCIÓN AUTOMÁTICA COMPLETADA (CONFIG MANUAL):
{self._format_contact_info(result)}"""
                    else:
                        return "🔍 No se encontró información para extraer."

            # Parsear campos adicionales
            additional_fields_dict = None
            if additional_fields:
                additional_fields_dict = self._parse_additional_fields(additional_fields)

            # Verificar información existente
            existing_contact = await self._get_existing_contact()
            
            # Si no hay datos nuevos y existe información, mostrarla
            if existing_contact and not any([name, email, phone_number, additional_fields_dict]):
                return self._format_contact_info(existing_contact)

            # Guardar o actualizar información
            if any([name, email, phone_number, additional_fields_dict]):
                result = await save_contact_async(
                    project_id=self.project_id,
                    user_id=self.user_id,
                    name=name,
                    email=email,
                    phone_number=phone_number,
                    additional_fields=additional_fields_dict
                )
                
                if result:
                    if existing_contact:
                        return self._get_update_message(existing_contact, result)
                    else:
                        return f"""🎉 CONTACTO GUARDADO EXITOSAMENTE:
{self._format_contact_info(result)}"""
                else:
                    return "❌ No se pudo guardar la información de contacto."
            
            return "ℹ️ No se proporcionó información para actualizar."
                
        except Exception as e:
            logging.error(f"Error al procesar contacto: {str(e)}")
            return f"❌ Error al procesar contacto: {str(e)}" 