from typing import Optional, Dict, Any
import re
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

    async def save_or_update_contact(
        self,
        project_id: str,
        user_id: str,
        name: Optional[str] = None,
        phone_number: Optional[str] = None,
        email: Optional[str] = None
    ) -> Optional[dict]:
        """
        Guarda o actualiza un contacto en la base de datos usando Supabase.
        Si el contacto ya existe (por user_id), actualiza la información.
        Retorna None si no hay suficiente información para guardar.
        """
        if not any([name, phone_number, email]):
            return None

        try:
            # Buscar contacto existente por user_id
            contact = await self.get_contact_by_user_id(project_id, user_id)

            if contact:
                # Actualizar contacto existente
                update_data = {
                    "name": name if name else contact["name"],
                    "phone_number": phone_number if phone_number else contact["phone_number"],
                    "email": email if email else contact["email"],
                    "updated_at": datetime.utcnow().isoformat()
                }
                response = self.client.client.table("contacts").update(update_data).eq("id", contact["id"]).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0]
            else:
                # Crear nuevo contacto
                new_contact = {
                    "project_id": project_id,
                    "user_id": user_id,
                    "name": name,
                    "phone_number": phone_number,
                    "email": email,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                response = self.client.client.table("contacts").insert(new_contact).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0]

        except Exception as e:
            print(f"Error saving/updating contact: {str(e)}")
            return None 