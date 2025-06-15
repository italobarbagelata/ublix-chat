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
            """,
            project_id=project_id,
            user_id=user_id
        )

    def _run(self, name: Optional[str] = None, email: Optional[str] = None, phone_number: Optional[str] = None) -> str:
        """
        Guarda o actualiza la información de contacto.
        
        Args:
            name: Nombre del contacto
            email: Email del contacto
            phone_number: Número de teléfono del contacto
            
        Returns:
            str: Mensaje de confirmación
        """
        try:
            result = self._contact_service.save_or_update_contact(
                project_id=self.project_id,
                user_id=self.user_id,
                name=name,
                email=email,
                phone_number=phone_number
            )
            
            if result:
                return "Información de contacto guardada exitosamente."
            else:
                return "No se pudo guardar la información de contacto."
                
        except Exception as e:
            return f"Error al guardar la información de contacto: {str(e)}"

    async def _arun(self, name: Optional[str] = None, email: Optional[str] = None, phone_number: Optional[str] = None) -> str:
        """
        Versión asíncrona de _run
        """
        try:
            result = await self._contact_service.save_or_update_contact(
                project_id=self.project_id,
                user_id=self.user_id,
                name=name,
                email=email,
                phone_number=phone_number
            )
            
            if result:
                return "Información de contacto guardada exitosamente."
            else:
                return "No se pudo guardar la información de contacto."
                
        except Exception as e:
            return f"Error al guardar la información de contacto: {str(e)}" 