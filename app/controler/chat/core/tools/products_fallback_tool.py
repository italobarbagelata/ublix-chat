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
    limit: int = 8
) -> str:
    """Búsqueda híbrida de productos combinando embeddings semánticos y búsqueda por texto."""
    
    logger.info(f"🔍 search_products_unified iniciada con query: '{query}'")
    logger.info(f"🔍 Parámetros: category={category}, limit={limit}")
    
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
        
        logger.info("🔄 Ejecutando búsqueda híbrida en Supabase...")
        response = db.supabase.rpc(
            'match_documents_hybrid',
            {
                'query_embedding': query_embedding,
                'query_text': query,
                'match_count': limit,
                'project_id_filter': project_id,
                'type_filter': 'product',
                'category_filter': category,
                'similarity_threshold': 0.6
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
            stock = producto.get('stock', 0)
            similarity = producto.get('similarity', 0)
            images = producto.get('images', [])
            logger.info(f"  {i}. {titulo} - ${precio:,.0f} {moneda} - Similarity: {similarity:.3f}")
        
        # Respuesta simple
        respuesta = f"Encontré {len(productos)} productos:\n\n"
        
        for i, producto in enumerate(productos, 1):
            titulo = producto.get('title', 'Sin título')
            description = producto.get('description', 'Sin descripción')
            precio = producto.get('price', 0)
            moneda = producto.get('currency', 'CLP')
            stock = producto.get('stock', 0)
            source_url = producto.get('source_url', 'Sin URL')
            images = producto.get('images', [])
            
            respuesta += f"{i}. {titulo}"
            if precio > 0:
                respuesta += f" - ${precio:,.0f} {moneda}"
            respuesta += f" - {description}"
            respuesta += f" - URL: {source_url}"
            if stock > 0:
                respuesta += f" - Stock disponible: {stock} unidades"
            elif stock == 0:
                respuesta += f" - ⚠️ SIN STOCK"
            if images:
                respuesta += f"\n   Imágenes:\n"
                for j, img_url in enumerate(images, 1):
                    respuesta += f"   {j}. {img_url}\n"
            respuesta += "\n"
        
        logger.info(f"✅ Respuesta generada exitosamente. Longitud: {len(respuesta)} caracteres")
        return respuesta
        
    except Exception as e:
        error_msg = f"Error en la búsqueda: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg 