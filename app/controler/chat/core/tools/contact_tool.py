from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from app.controler.chat.services.contact_service import ContactService
from pydantic import Field, PrivateAttr

class SaveContactTool(BaseTool):
    project_id: str = Field(description="ID del proyecto")
    user_id: str = Field(description="ID del usuario")
    _contact_service: ContactService = PrivateAttr(default_factory=ContactService)
    
    def __init__(self, project_id: str, user_id: str):
        super().__init__(
            name="save_contact_tool",
            description="""
            Herramienta para guardar o actualizar información de contacto de un usuario.
            Úsala cuando el usuario proporcione su nombre, email o teléfono.
            Si el usuario ya tiene información guardada, la devolverá.
            Para actualizar información específica, proporciona solo los campos que deseas actualizar.
            """,
            project_id=project_id,
            user_id=user_id
        )

    async def _get_existing_contact(self) -> Optional[dict]:
        """
        Obtiene la información de contacto existente para el usuario actual.
        """
        return await self._contact_service.get_contact_by_user_id(self.project_id, self.user_id)

    def _format_contact_info(self, contact: dict) -> str:
        """
        Formatea la información del contacto para mostrarla.
        """
        return f"Información de contacto:\nNombre: {contact.get('name', 'No disponible')}\nEmail: {contact.get('email', 'No disponible')}\nTeléfono: {contact.get('phone_number', 'No disponible')}"

    def _get_update_message(self, existing: dict, new: dict) -> str:
        """
        Genera un mensaje describiendo los cambios realizados.
        """
        changes = []
        if new.get('name') and new['name'] != existing.get('name'):
            changes.append(f"nombre: {existing.get('name', 'No disponible')} → {new['name']}")
        if new.get('email') and new['email'] != existing.get('email'):
            changes.append(f"email: {existing.get('email', 'No disponible')} → {new['email']}")
        if new.get('phone_number') and new['phone_number'] != existing.get('phone_number'):
            changes.append(f"teléfono: {existing.get('phone_number', 'No disponible')} → {new['phone_number']}")
        
        if changes:
            return f"Se actualizó la siguiente información:\n" + "\n".join(changes)
        return "No se realizaron cambios en la información."

    def _run(self, name: Optional[str] = None, email: Optional[str] = None, phone_number: Optional[str] = None) -> str:
        """
        Guarda o actualiza la información de contacto.
        
        Args:
            name: Nombre del contacto
            email: Email del contacto
            phone_number: Número de teléfono del contacto
            
        Returns:
            str: Mensaje de confirmación o información del contacto existente
        """
        try:
            # Primero verificar si existe información del contacto
            existing_contact = self._contact_service.get_contact_by_user_id(self.project_id, self.user_id)
            
            # Si no hay datos nuevos y existe información, mostrar la información existente
            if existing_contact and not any([name, email, phone_number]):
                return self._format_contact_info(existing_contact)

            # Si hay datos nuevos, actualizar la información
            if any([name, email, phone_number]):
                result = self._contact_service.save_or_update_contact(
                    project_id=self.project_id,
                    user_id=self.user_id,
                    name=name,
                    email=email,
                    phone_number=phone_number
                )
                
                if result:
                    if existing_contact:
                        # Si existía información previa, mostrar los cambios
                        return self._get_update_message(existing_contact, result)
                    else:
                        return "Información de contacto guardada exitosamente."
                else:
                    return "No se pudo guardar la información de contacto."
            
            return "No se proporcionó información para actualizar."
                
        except Exception as e:
            return f"Error al guardar la información de contacto: {str(e)}"

    async def _arun(self, name: Optional[str] = None, email: Optional[str] = None, phone_number: Optional[str] = None) -> str:
        """
        Versión asíncrona de _run
        """
        try:
            # Primero verificar si existe información del contacto
            existing_contact = await self._contact_service.get_contact_by_user_id(self.project_id, self.user_id)
            
            # Si no hay datos nuevos y existe información, mostrar la información existente
            if existing_contact and not any([name, email, phone_number]):
                return self._format_contact_info(existing_contact)

            # Si hay datos nuevos, actualizar la información
            if any([name, email, phone_number]):
                result = await self._contact_service.save_or_update_contact(
                    project_id=self.project_id,
                    user_id=self.user_id,
                    name=name,
                    email=email,
                    phone_number=phone_number
                )
                
                if result:
                    if existing_contact:
                        # Si existía información previa, mostrar los cambios
                        return self._get_update_message(existing_contact, result)
                    else:
                        return "Información de contacto guardada exitosamente."
                else:
                    return "No se pudo guardar la información de contacto."
            
            return "No se proporcionó información para actualizar."
                
        except Exception as e:
            return f"Error al guardar la información de contacto: {str(e)}" 