"""
Servicio para gestionar leads desde diferentes plataformas
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import pytz
from app.controler.chat.store.persistence import SupabaseDatabase

logger = logging.getLogger(__name__)

class LeadService:
    """Servicio para gestionar leads de diferentes plataformas."""
    
    def __init__(self):
        self.db = SupabaseDatabase()
        self.timezone = pytz.timezone('America/Santiago')
    
    async def create_or_update_lead(
        self,
        project_id: str,
        platform: str,
        platform_user_id: str,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        profile_data: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea o actualiza un lead basado en la información de la plataforma.
        
        Args:
            project_id: ID del proyecto
            platform: Plataforma de origen (instagram, whatsapp, facebook)
            platform_user_id: ID del usuario en la plataforma
            username: Nombre de usuario en la plataforma
            full_name: Nombre completo del usuario
            profile_data: Datos adicionales del perfil
            message_id: ID del mensaje asociado
            
        Returns:
            Información del lead creado o actualizado
        """
        try:
            # Buscar si el lead ya existe
            existing_lead = self.db.find_one("leads", {
                "project_id": project_id,
                "platform": platform,
                "platform_user_id": platform_user_id
            })
            
            current_time = datetime.now(self.timezone)
            
            if existing_lead:
                # Actualizar lead existente
                update_data = {
                    "last_interaction_at": current_time.isoformat(),
                    "updated_at": current_time.isoformat(),
                    "total_messages": existing_lead.get("total_messages", 0) + 1
                }
                
                # Actualizar campos si vienen nuevos valores
                if username and not existing_lead.get("username"):
                    update_data["username"] = username
                if full_name and not existing_lead.get("full_name"):
                    update_data["full_name"] = full_name
                if message_id:
                    update_data["last_message_id"] = message_id
                if profile_data:
                    existing_profile = existing_lead.get("profile_data", {})
                    update_data["profile_data"] = {**existing_profile, **profile_data}
                
                # Si el lead estaba inactivo, reactivarlo
                if existing_lead.get("lead_status") == "inactive":
                    update_data["lead_status"] = "engaged"
                
                self.db.update("leads", update_data, {"id": existing_lead["id"]})
                
                logger.info(f"✅ Lead actualizado: {full_name or username} ({platform})")
                return {**existing_lead, **update_data}
                
            else:
                # Crear nuevo lead
                new_lead = {
                    "project_id": project_id,
                    "platform": platform,
                    "platform_user_id": platform_user_id,
                    "username": username,
                    "full_name": full_name,
                    "profile_data": profile_data or {},
                    "first_message_id": message_id,
                    "last_message_id": message_id,
                    "total_messages": 1,
                    "lead_status": "new",
                    "tags": [],
                    "created_at": current_time.isoformat(),
                    "updated_at": current_time.isoformat(),
                    "last_interaction_at": current_time.isoformat()
                }
                
                result = self.db.insert("leads", new_lead)
                
                logger.info(f"✅ Nuevo lead creado: {full_name or username} ({platform})")
                return result
                
        except Exception as e:
            logger.error(f"❌ Error gestionando lead: {e}", exc_info=True)
            return None
    
    async def get_lead_by_platform(
        self,
        project_id: str,
        platform: str,
        platform_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene un lead por plataforma y user_id.
        
        Args:
            project_id: ID del proyecto
            platform: Plataforma de origen
            platform_user_id: ID del usuario en la plataforma
            
        Returns:
            Información del lead o None si no existe
        """
        try:
            lead = self.db.find_one("leads", {
                "project_id": project_id,
                "platform": platform,
                "platform_user_id": platform_user_id
            })
            return lead
        except Exception as e:
            logger.error(f"Error obteniendo lead: {e}")
            return None
    
    async def update_lead_status(
        self,
        lead_id: str,
        status: str,
        tags: Optional[list] = None
    ) -> bool:
        """
        Actualiza el estado de un lead.
        
        Args:
            lead_id: ID del lead
            status: Nuevo estado (new, engaged, qualified, converted, inactive)
            tags: Tags opcionales para el lead
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            update_data = {
                "lead_status": status,
                "updated_at": datetime.now(self.timezone).isoformat()
            }
            
            if tags is not None:
                update_data["tags"] = tags
            
            self.db.update("leads", update_data, {"id": lead_id})
            logger.info(f"Lead {lead_id} actualizado a estado: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando estado del lead: {e}")
            return False
    
    async def get_lead_stats(self, project_id: str) -> Dict[str, Any]:
        """
        Obtiene estadísticas de leads del proyecto.
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Estadísticas de leads
        """
        try:
            leads = self.db.select("leads", {"project_id": project_id})
            
            stats = {
                "total": len(leads),
                "by_platform": {},
                "by_status": {},
                "active_today": 0
            }
            
            today = datetime.now(self.timezone).date()
            
            for lead in leads:
                # Por plataforma
                platform = lead.get("platform", "unknown")
                stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1
                
                # Por estado
                status = lead.get("lead_status", "unknown")
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                
                # Activos hoy
                last_interaction = lead.get("last_interaction_at")
                if last_interaction:
                    interaction_date = datetime.fromisoformat(
                        last_interaction.replace("Z", "+00:00")
                    ).astimezone(self.timezone).date()
                    if interaction_date == today:
                        stats["active_today"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"error": str(e)}