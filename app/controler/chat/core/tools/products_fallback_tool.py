import logging
from typing import List, Optional, Dict, Any
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
from app.resources.postgresql import SupabaseDatabase
from langchain_openai import OpenAIEmbeddings
import os

# Configurar el logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicializar la base de datos
db = SupabaseDatabase()

@tool("search_products_unified", return_direct=True)
def search_products_unified(
    query: str,
    state: Annotated[dict, InjectedState],
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 10
) -> str:
    """Búsqueda simple de productos con embeddings semánticos."""
    
    logger.info(f"🔍 search_products_unified iniciada con query: '{query}'")
    logger.info(f"🔍 Parámetros: category={category}, min_price={min_price}, max_price={max_price}, limit={limit}")
    
    # Validar proyecto
    project_state = state.get("project")
    if not project_state or not project_state.id:
        logger.error("❌ No se encontró información del proyecto en el estado")
        return "Error: No se encontró información del proyecto."
    
    project_id = project_state.id
    logger.info(f"✅ Proyecto encontrado: {project_id}")
    
    try:
        # Búsqueda semántica
        logger.info("🔄 Generando embeddings...")
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=384
        )
        query_embedding = embeddings.embed_query(query)
        logger.info("✅ Embeddings generados exitosamente")
        
        logger.info("🔄 Ejecutando búsqueda en Supabase...")
        response = db.supabase.rpc(
            'match_documents_v20',
            {
                'query_embedding': query_embedding,
                'match_count': 30,  # Buscar más productos para encontrar los específicos
                'project_id_filter': project_id,
                'type_filter': 'product',
                'category_filter': category,
                'min_price': min_price,
                'max_price': max_price
            }
        ).execute()
        
        productos = response.data if response.data else []
        logger.info(f"✅ Búsqueda completada. Productos encontrados: {len(productos)}")
        
        # Imprimir información de los productos encontrados para debug
        logger.info("📋 Productos encontrados:")
        for i, producto in enumerate(productos, 1):
            titulo = producto.get('title', 'Sin título')
            precio = producto.get('price', 0)
            moneda = producto.get('currency', 'CLP')
            similarity = producto.get('similarity', 0)
            logger.info(f"  {i}. {titulo} - ${precio:,.0f} {moneda} - Similarity: {similarity:.3f}")
        
        # Respuesta simple
        respuesta = f"Encontré {len(productos)} productos:\n\n"
        
        for i, producto in enumerate(productos, 1):
            titulo = producto.get('title', 'Sin título')
            description = producto.get('description', 'Sin descripción')
            precio = producto.get('price', 0)
            moneda = producto.get('currency', 'CLP')
            source_url = producto.get('source_url', 'Sin URL')
            images = producto.get('images', [])
            
            respuesta += f"{i}. {titulo}"
            if precio > 0:
                respuesta += f" - ${precio:,.0f} {moneda}"
            respuesta += f" - {description}"
            respuesta += f" - {source_url}"
            if images:
                respuesta += f" - Imágenes: {len(images)}"
            respuesta += "\n"
        
        logger.info(f"✅ Respuesta generada exitosamente. Longitud: {len(respuesta)} caracteres")
        logger.info(f"📝 Primeros 200 caracteres de la respuesta: {respuesta[:200]}...")
        return respuesta
        
    except Exception as e:
        error_msg = f"Error en la búsqueda: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg 