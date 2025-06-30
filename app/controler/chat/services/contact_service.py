from typing import Optional, Dict, Any, List
import re
import json
from datetime import datetime
from app.controler.chat.store.supabase_client import SupabaseClient

class ContactService:
    def __init__(self):
        self.client = SupabaseClient()

    async def get_contact_by_user_id(self, project_id: str, user_id: str) -> Optional[dict]:
        """
        Obtiene la información de contacto existente para un user_id específico.
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            
        Returns:
            dict: Información del contacto si existe, None si no existe
        """
        try:
            response = self.client.client.table("contacts").select("*").eq("project_id", project_id).eq("user_id", user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error getting contact by user_id: {str(e)}")
            return None

    def extract_contact_info(self, message: str) -> Dict[str, Any]:
        """
        Extrae información de contacto del mensaje usando expresiones regulares.
        Retorna un diccionario con la información encontrada.
        """
        contact_info = {
            "name": None,
            "email": None,
            "phone_number": None
        }

        # Patrones para extraer información
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})(?: *x\d+)?'
        
        # Buscar email
        email_match = re.search(email_pattern, message)
        if email_match:
            contact_info["email"] = email_match.group(0)

        # Buscar teléfono
        phone_match = re.search(phone_pattern, message)
        if phone_match:
            # Reconstruir el número de teléfono
            phone_parts = phone_match.groups()
            phone_number = ''.join(filter(None, phone_parts))
            contact_info["phone_number"] = phone_number

        # Buscar nombre (asumiendo que está después de palabras clave comunes)
        name_keywords = ["me llamo", "mi nombre es", "soy", "me presento"]
        for keyword in name_keywords:
            if keyword in message.lower():
                # Extraer el texto después de la palabra clave
                name_part = message.lower().split(keyword)[1].strip()
                # Tomar la primera frase o hasta 3 palabras
                name = name_part.split('.')[0].split(',')[0].strip()
                name = ' '.join(name.split()[:3])
                if name:
                    contact_info["name"] = name.title()
                break

        return contact_info

    async def get_project_field_config(self, project_id: str) -> Dict[str, Any]:
        """
        Obtiene la configuración de campos adicionales desde la base de datos.
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con configuración de campos para el proyecto
            
        Ejemplo de retorno:
        {
            "edad": {
                "keywords": ["tengo", "años"],
                "type": "number",
                "description": "Edad del cliente"
            },
            "direccion": {
                "keywords": ["vivo en", "mi dirección"],
                "type": "string", 
                "description": "Dirección de residencia"
            }
        }
        """
        try:
            print(f"🔧 DEBUG: Obteniendo configuración para project_id: {project_id}")
            response = self.client.client.rpc(
                'get_contact_field_config', 
                {'project_uuid': project_id}
            ).execute()
            
            print(f"🔧 DEBUG: Respuesta RPC: {response.data}")
            
            if response.data:
                return response.data
            return {}
        except Exception as e:
            print(f"❌ Error obteniendo configuración de campos: {str(e)}")
            return {}

    async def auto_extract_from_conversation(self, project_id: str, conversation_text: str) -> Dict[str, Any]:
        """
        Extrae automáticamente campos según la configuración del proyecto.
        Retorna tanto campos base como adicionales por separado.
        
        Args:
            project_id: ID del proyecto
            conversation_text: Texto de la conversación
            
        Returns:
            Dict con estructura:
            {
                'base_fields': {'name': '...', 'email': '...', 'phone_number': '...'},
                'additional_fields': {'edad': 30, 'direccion': '...', ...}
            }
        """
        try:
            # Obtener configuración del proyecto
            field_config = await self.get_project_field_config(project_id)
            
            # Extraer información básica usando patrones estándar
            base_info = self.extract_contact_info(conversation_text)
            
            # Extraer campos adicionales usando configuración del proyecto
            additional_fields = {}
            if field_config:
                additional_fields = self.extract_additional_fields_with_llm(
                    conversation_text, field_config
                )
            
            return {
                'base_fields': base_info,
                'additional_fields': additional_fields
            }
        except Exception as e:
            print(f"Error en extracción automática: {str(e)}")
            return {'base_fields': {}, 'additional_fields': {}}

    def extract_additional_fields_with_llm(self, conversation_text: str, field_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae campos adicionales usando SOLO la configuración definida en contact_field_configs.
        NO extrae campos que no estén configurados para evitar ensuciar la data.
        
        Args:
            conversation_text: Texto completo de la conversación
            field_config: Configuración de campos a extraer desde contact_field_configs
            
        Returns:
            Dict con SOLO los campos configurados que se encontraron
            
        Ejemplo field_config:
        {
            "direccion": {
                "keywords": ["vivo en", "mi dirección", "dirección es", "domicilio"],
                "type": "string",
                "description": "Dirección de residencia"
            },
            "edad": {
                "keywords": ["tengo", "años", "edad"],
                "type": "number", 
                "description": "Edad del usuario"
            },
            "ha_invertido": {
                "keywords": ["he invertido", "invirtiendo", "inversión", "broker"],
                "type": "boolean",
                "description": "Si ha hecho inversiones anteriormente"
            }
        }
        """
        print(f"🔧 DEBUG: Extrayendo campos de texto: '{conversation_text[:100]}...'")
        print(f"🔧 DEBUG: Configuración recibida: {field_config}")
        
        # Campos que ya tienen columnas dedicadas en la tabla contacts
        # Estos NO deben ir en additional_fields
        base_fields = {'name', 'nombre', 'email', 'correo', 'phone_number', 'telefono', 'teléfono'}
        
        extracted_fields = {}
        
        # SOLO procesar campos que estén definidos en field_config (contact_field_configs)
        for field_name, config in field_config.items():
            print(f"🔧 DEBUG: Procesando campo '{field_name}' con config: {config}")
            
            # Saltar campos base que tienen columnas dedicadas
            if field_name.lower() in base_fields:
                print(f"🔧 DEBUG: Saltando campo base '{field_name}'")
                continue
                
            keywords = config.get("keywords", [])
            field_type = config.get("type", "string")
            
            print(f"🔧 DEBUG: Buscando keywords {keywords} de tipo {field_type} en texto")
            
            # Buscar usando palabras clave
            found_value = self._extract_field_value(conversation_text, keywords, field_type)
            if found_value:
                extracted_fields[field_name] = found_value
                print(f"✅ DEBUG: Campo '{field_name}' extraído con valor: {found_value}")
            else:
                print(f"❌ DEBUG: Campo '{field_name}' no encontrado")
                
        print(f"🎯 DEBUG: Campos finales extraídos: {extracted_fields}")
        return extracted_fields

    def _extract_field_value(self, text: str, keywords: List[str], field_type: str) -> Any:
        """
        Extrae un valor específico del texto basado en palabras clave y tipo.
        """
        text_lower = text.lower()
        print(f"🔍 DEBUG: Buscando en texto: '{text_lower[:150]}...'")
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            print(f"🔍 DEBUG: Verificando keyword: '{keyword_lower}'")
            if keyword_lower in text_lower:
                # Encontrar la posición de la palabra clave
                start_pos = text_lower.find(keyword_lower)
                if start_pos == -1:
                    continue
                    
                # Extraer el contexto después de la palabra clave
                after_keyword = text[start_pos + len(keyword):].strip()
                
                if field_type == "string":
                    # Limpiar palabras conectoras comunes
                    cleaned = after_keyword
                    connectors = [" en ", " como ", " de ", " la ", " el ", " las ", " los "]
                    for conn in connectors:
                        if cleaned.lower().startswith(conn):
                            cleaned = cleaned[len(conn):].strip()
                    
                    # Para strings, tomar hasta el primer punto, coma o salto de línea
                    value = cleaned.split('.')[0].split(',')[0].split('\n')[0].split(' y ')[0].strip()
                    
                    # Casos especiales para profesiones
                    if any(prof_keyword in keyword_lower for prof_keyword in ["profesion", "dedica", "trabajo"]):
                        # Buscar artículos comunes antes de profesiones
                        if value.lower().startswith(("soy ", "como ", "un ", "una ")):
                            words = value.split()
                            if len(words) > 1:
                                value = " ".join(words[1:])
                    
                    if value and len(value) > 1:
                        return value.strip()
                        
                elif field_type == "number":
                    # Buscar números en el contexto
                    numbers = re.findall(r'\d+', after_keyword[:50])  # Buscar en los primeros 50 caracteres
                    if numbers:
                        return int(numbers[0])
                        
                elif field_type == "boolean":
                    # Para campos booleanos como "ha_invertido", la presencia de la keyword ya indica True
                    # A menos que haya negación explícita
                    negative_indicators = ["no he", "nunca he", "jamás he", "no", "nunca", "jamás"]
                    
                    # Verificar contexto anterior y posterior para negaciones
                    before_keyword = text[:start_pos].lower().split()[-3:] if start_pos > 0 else []
                    after_words = after_keyword.lower().split()[:5]
                    
                    all_context = " ".join(before_keyword + [keyword_lower] + after_words)
                    
                    for neg in negative_indicators:
                        if neg in all_context:
                            return False
                    
                    # Si no hay negación explícita, la presencia de la keyword indica True
                    return True
                            
        return None

    async def save_or_update_contact(
        self,
        project_id: str,
        user_id: str,
        name: Optional[str] = None,
        phone_number: Optional[str] = None,
        email: Optional[str] = None,
        additional_fields: Optional[Dict[str, Any]] = None
    ) -> Optional[dict]:
        """
        Guarda o actualiza un contacto en la base de datos usando Supabase.
        Si el contacto ya existe (por user_id), actualiza la información.
        Retorna None si no hay suficiente información para guardar.
        
        Args:
            additional_fields: Campos adicionales como JSON (ej: {"direccion": "Santiago", "edad": 30})
        """
        if not any([name, phone_number, email, additional_fields]):
            return None

        try:
            # Buscar contacto existente por user_id
            contact = await self.get_contact_by_user_id(project_id, user_id)

            if contact:
                # Actualizar contacto existente
                update_data = {
                    "name": name if name else contact.get("name", "Usuario"),
                    "phone_number": phone_number if phone_number else contact.get("phone_number"),
                    "email": email if email else contact.get("email"),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                # Manejar campos adicionales - combinar con existentes
                if additional_fields:
                    existing_additional = contact.get("additional_fields", {})
                    if isinstance(existing_additional, str):
                        try:
                            existing_additional = json.loads(existing_additional)
                        except:
                            existing_additional = {}
                    elif existing_additional is None:
                        existing_additional = {}
                        
                    # Combinar campos existentes con nuevos
                    combined_fields = {**existing_additional, **additional_fields}
                    # Para JSONB en Supabase, pasar el dict directamente
                    update_data["additional_fields"] = combined_fields
                
                response = self.client.client.table("contacts").update(update_data).eq("id", contact["id"]).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0]
            else:
                # Crear nuevo contacto
                new_contact = {
                    "project_id": project_id,
                    "user_id": user_id,
                    "name": name if name else "Usuario",
                    "phone_number": phone_number,
                    "email": email,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                # Agregar campos adicionales
                if additional_fields:
                    # Para JSONB en Supabase, pasar el dict directamente
                    new_contact["additional_fields"] = additional_fields
                
                response = self.client.client.table("contacts").insert(new_contact).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0]

        except Exception as e:
            print(f"Error saving/updating contact: {str(e)}")
            return None

    def get_field_configuration_examples(self) -> Dict[str, Dict]:
        """
        Retorna ejemplos de configuraciones de campos para diferentes tipos de bot.
        """
        return {
            "bot_inversiones": {
                "direccion": {
                    "keywords": ["vivo en", "mi dirección", "dirección es", "domicilio", "resido en"],
                    "type": "string",
                    "description": "Dirección de residencia del cliente"
                },
                "ciudad": {
                    "keywords": ["ciudad", "vivo en", "de la ciudad", "en"],
                    "type": "string", 
                    "description": "Ciudad donde reside"
                },
                "edad": {
                    "keywords": ["tengo", "años", "mi edad", "edad es"],
                    "type": "number",
                    "description": "Edad del cliente"
                },
                "ha_invertido": {
                    "keywords": ["he invertido", "invirtiendo", "inversión", "broker", "acciones", "bolsa"],
                    "type": "boolean",
                    "description": "Si ha hecho inversiones anteriormente"
                },
                "experiencia_inversion": {
                    "keywords": ["experiencia", "años invirtiendo", "tiempo", "desde"],
                    "type": "string",
                    "description": "Experiencia en inversiones"
                }
            },
            "bot_ecommerce": {
                "producto_interes": {
                    "keywords": ["me interesa", "quiero", "busco", "necesito"],
                    "type": "string",
                    "description": "Producto de interés"
                },
                "presupuesto": {
                    "keywords": ["presupuesto", "dispongo", "puedo pagar", "precio máximo"],
                    "type": "number", 
                    "description": "Presupuesto disponible"
                },
                "fecha_compra": {
                    "keywords": ["cuando", "fecha", "para cuándo", "necesito para"],
                    "type": "string",
                    "description": "Fecha estimada de compra"
                },
                "metodo_pago": {
                    "keywords": ["pago", "transferencia", "tarjeta", "efectivo"],
                    "type": "string",
                    "description": "Método de pago preferido"
                }
            },
            "bot_servicios": {
                "tipo_servicio": {
                    "keywords": ["necesito", "servicio", "requiero", "busco"],
                    "type": "string",
                    "description": "Tipo de servicio requerido"
                },
                "urgencia": {
                    "keywords": ["urgente", "pronto", "rápido", "cuando"],
                    "type": "string",
                    "description": "Nivel de urgencia"
                },
                "disponibilidad": {
                    "keywords": ["disponible", "horario", "puede", "prefiero"],
                    "type": "string",
                    "description": "Disponibilidad horaria"
                }
            }
        } 