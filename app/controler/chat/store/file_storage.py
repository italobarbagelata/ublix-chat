import os
import logging
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from datetime import datetime

logger = logging.getLogger(__name__)

# Storage directory for uploaded files
STORAGE_DIR = os.getenv("FILE_STORAGE_DIR", "/tmp/ublix_storage")


class FileStorage:
    """Clase para manejar el almacenamiento de archivos.

    NOTA: Tras migrar de Supabase a PostgreSQL directo, el almacenamiento
    de archivos se maneja localmente o via un servicio externo configurable.
    Configure FILE_STORAGE_DIR y FILE_STORAGE_BASE_URL en las variables de entorno.
    """

    def __init__(self):
        self.storage_dir = STORAGE_DIR
        self.base_url = os.getenv("FILE_STORAGE_BASE_URL", "")
        os.makedirs(self.storage_dir, exist_ok=True)

    def _generate_filename(self, original_filename: str) -> str:
        """
        Genera un nombre de archivo unico con fecha.

        Args:
            original_filename: Nombre original del archivo

        Returns:
            str: Nombre de archivo generado
        """
        # Obtener extension del archivo
        file_extension = os.path.splitext(original_filename)[1]

        # Generar timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generar UUID
        unique_id = str(uuid4())

        # Combinar todo
        return f"{timestamp}_{unique_id}{file_extension}"

    async def save_image(self, project_id: str, file: UploadFile, content_type: str = None) -> str:
        """
        Guarda una imagen en el almacenamiento local.

        Args:
            project_id: ID del proyecto
            file: Archivo de imagen a guardar
            content_type: Tipo de contenido de la imagen (opcional)

        Returns:
            str: URL de la imagen guardada
        """
        try:
            bucket_name = "imagenes"

            # Generar nombre unico para el archivo
            filename = self._generate_filename(file.filename)

            # Crear ruta con estructura: project_id/YYYY/MM/DD/filename
            current_date = datetime.now()
            relative_path = f"{bucket_name}/{project_id}/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}/{filename}"

            # Crear directorio si no existe
            full_dir = os.path.join(self.storage_dir, os.path.dirname(relative_path))
            os.makedirs(full_dir, exist_ok=True)

            # Leer contenido del archivo
            file_content = await file.read()

            # Escribir archivo
            full_path = os.path.join(self.storage_dir, relative_path)
            with open(full_path, 'wb') as f:
                f.write(file_content)

            # Generar URL
            url = f"{self.base_url}/{relative_path}" if self.base_url else full_path

            # Resetear el archivo para futuras lecturas
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
        Elimina una imagen del almacenamiento.

        Args:
            project_id: ID del proyecto
            filename: Nombre del archivo a eliminar

        Returns:
            bool: True si se elimino correctamente, False en caso contrario
        """
        try:
            bucket_name = "imagenes"
            file_path = os.path.join(self.storage_dir, bucket_name, project_id, filename)

            if os.path.exists(file_path):
                os.remove(file_path)
            return True

        except Exception as e:
            logger.error(f"Error al eliminar imagen: {str(e)}")
            return False

    async def get_image_url(self, project_id: str, filename: str) -> str:
        """
        Obtiene la URL de una imagen.

        Args:
            project_id: ID del proyecto
            filename: Nombre del archivo

        Returns:
            str: URL de la imagen
        """
        try:
            bucket_name = "imagenes"
            relative_path = f"{bucket_name}/{project_id}/{filename}"

            if self.base_url:
                return f"{self.base_url}/{relative_path}"
            return os.path.join(self.storage_dir, relative_path)

        except Exception as e:
            logger.error(f"Error al obtener URL de imagen: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"Imagen no encontrada: {str(e)}"
            )

    async def list_project_images(self, project_id: str) -> list:
        """
        Lista todas las imagenes de un proyecto.

        Args:
            project_id: ID del proyecto

        Returns:
            list: Lista de URLs de imagenes
        """
        try:
            bucket_name = "imagenes"
            project_dir = os.path.join(self.storage_dir, bucket_name, project_id)

            if not os.path.exists(project_dir):
                return []

            urls = []
            for root, dirs, files in os.walk(project_dir):
                for file_name in files:
                    full_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(full_path, self.storage_dir)

                    url = f"{self.base_url}/{relative_path}" if self.base_url else full_path
                    stat = os.stat(full_path)

                    urls.append({
                        "url": url,
                        "name": file_name,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "size": stat.st_size
                    })

            return urls

        except Exception as e:
            logger.error(f"Error al listar imagenes del proyecto: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al listar imagenes: {str(e)}"
            )
