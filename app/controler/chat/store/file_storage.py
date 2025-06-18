import os
import logging
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from app.resources.postgresql import SupabaseDatabase
from datetime import datetime

logger = logging.getLogger(__name__)

class FileStorage:
    """Clase para manejar el almacenamiento de archivos en Supabase."""
    
    def __init__(self):
        self.db = SupabaseDatabase()
        
    def _generate_filename(self, original_filename: str) -> str:
        """
        Genera un nombre de archivo único con fecha.
        
        Args:
            original_filename: Nombre original del archivo
            
        Returns:
            str: Nombre de archivo generado
        """
        # Obtener extensión del archivo
        file_extension = os.path.splitext(original_filename)[1]
        
        # Generar timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generar UUID
        unique_id = str(uuid4())
        
        # Combinar todo
        return f"{timestamp}_{unique_id}{file_extension}"
        
    async def save_image(self, project_id: str, file: UploadFile, content_type: str = None) -> str:
        """
        Guarda una imagen en el almacenamiento de Supabase.
        
        Args:
            project_id: ID del proyecto
            file: Archivo de imagen a guardar
            content_type: Tipo de contenido de la imagen (opcional)
        
        Returns:
            str: URL de la imagen guardada
        """
        try:
            bucket_name = "imagenes"
            
            # Generar nombre único para el archivo
            filename = self._generate_filename(file.filename)
            
            # Crear ruta con estructura: project_id/YYYY/MM/DD/filename
            current_date = datetime.now()
            file_path = f"{project_id}/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}/{filename}"
            
            # Leer contenido del archivo una sola vez
            file_content = await file.read()
            
            # Verificar si el bucket existe
            buckets = self.db.supabase.storage.list_buckets()
            bucket_exists = any(bucket.name == bucket_name for bucket in buckets)
            
            if not bucket_exists:
                logger.info(f"Creando bucket: {bucket_name}")
                self.db.supabase.storage.create_bucket(
                    bucket_name,
                    options={
                        'public': False,
                        'file_size_limit': 52428800,  # 50MB
                        'allowed_mime_types': [
                            'image/jpeg',
                            'image/png',
                            'image/gif',
                            'image/webp'
                        ]
                    }
                )
            
            # Usar el content_type proporcionado o el del archivo
            final_content_type = content_type or getattr(file, 'content_type', 'image/jpeg')
            
            # Subir archivo
            result = self.db.supabase.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": final_content_type,
                    "cache-control": "3600",
                    "upsert": "true"
                }
            )
            
            # Obtener URL pública
            url = self.db.supabase.storage.from_(bucket_name).get_public_url(file_path)
            
            # Resetear el archivo para futuras lecturas si es necesario
            await file.seek(0)
            
            return url
            
        except Exception as e:
            logger.error(f"Error al guardar imagen: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al guardar la imagen: {str(e)}"
            )
            
    async def delete_image(self, project_id: str, filename: str) -> bool:
        """
        Elimina una imagen del almacenamiento de Supabase.
        
        Args:
            project_id: ID del proyecto
            filename: Nombre del archivo a eliminar
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        try:
            bucket_name = "imagenes"
            file_path = f"{project_id}/{filename}"
            
            self.db.supabase.storage.from_(bucket_name).remove([file_path])
            return True
            
        except Exception as e:
            logger.error(f"Error al eliminar imagen: {str(e)}")
            return False
            
    async def get_image_url(self, project_id: str, filename: str) -> str:
        """
        Obtiene la URL pública de una imagen.
        
        Args:
            project_id: ID del proyecto
            filename: Nombre del archivo
            
        Returns:
            str: URL pública de la imagen
        """
        try:
            bucket_name = "imagenes"
            file_path = f"{project_id}/{filename}"
            
            return self.db.supabase.storage.from_(bucket_name).get_public_url(file_path)
            
        except Exception as e:
            logger.error(f"Error al obtener URL de imagen: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"Imagen no encontrada: {str(e)}"
            )
            
    async def list_project_images(self, project_id: str) -> list:
        """
        Lista todas las imágenes de un proyecto.
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            list: Lista de URLs de imágenes
        """
        try:
            bucket_name = "imagenes"
            
            # Listar archivos en la carpeta del proyecto
            files = self.db.supabase.storage.from_(bucket_name).list(project_id)
            
            # Obtener URLs públicas
            urls = []
            for file in files:
                file_path = f"{project_id}/{file.name}"
                url = self.db.supabase.storage.from_(bucket_name).get_public_url(file_path)
                urls.append({
                    "url": url,
                    "name": file.name,
                    "created_at": file.created_at,
                    "size": file.metadata.get("size", 0)
                })
                
            return urls
            
        except Exception as e:
            logger.error(f"Error al listar imágenes del proyecto: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al listar imágenes: {str(e)}"
            ) 