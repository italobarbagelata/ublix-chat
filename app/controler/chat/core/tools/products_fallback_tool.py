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
    
    # Validar proyecto
    project_state = state.get("project")
    if not project_state or not project_state.id:
        return "Error: No se encontró información del proyecto."
    
    project_id = project_state.id
    
    try:
        # Búsqueda semántica
        embeddings = OpenAIEmbeddings()
        query_embedding = embeddings.embed_query(query)
        
        response = db.supabase.rpc(
            'match_documents_v20',
            {
                'query_embedding': query_embedding,
                'match_count': limit,
                'project_id_filter': project_id,
                'type_filter': 'product',
                'category_filter': category,
                'min_price': min_price,
                'max_price': max_price
            }
        ).execute()
        
        productos = response.data if response.data else []
        
        if not productos:
            return f"No encontré productos relacionados con '{query}'."
        
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
            respuesta += f" - {images}"
            respuesta += "\n"
        
        return respuesta
        
    except Exception as e:
        return f"Error en la búsqueda: {str(e)}" 