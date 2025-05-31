import os
import logging
from supabase import create_client
from langchain_openai import OpenAIEmbeddings
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated

# Configurar logging
logger = logging.getLogger(__name__)

# Configuración simple de Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Configuración de embeddings
embeddings = OpenAIEmbeddings()

def retrieve(query: str, project_id: str = None):
    """Retrieve information related to a query."""
    logger.info(f"Iniciando búsqueda con query: '{query}'")
    
    try:
        # Obtener embedding de la query
        query_embedding = embeddings.embed_query(query)
        logger.info(f"Embedding generado para la query")
        
        # Preparar filtros
        filter_metadata = {}
        if project_id:
            filter_metadata["project_id"] = project_id
            logger.info(f"Aplicando filtro por project_id: {project_id}")
        
        # Llamar a la función match_documents_v7 con la estructura correcta
        response = supabase.rpc(
            'match_documents_v11',
            {
                'query_embedding': query_embedding,
                'filter': {},
                'match_threshold': 0.0  # Umbral de similitud mínima
            }
        ).execute()
        
        retrieved_docs = response.data if response.data else []
        logger.info(f"Documentos encontrados: {len(retrieved_docs)}")
        
        if not retrieved_docs:
            logger.warning("No se encontraron documentos en la búsqueda")
            return "", []
        
        # Procesar los documentos encontrados
        processed_docs = []
        for i, doc in enumerate(retrieved_docs):
            logger.info(f"Documento {i+1}: metadata={doc.get('metadata', {})}, content_length={len(doc.get('content', ''))}, similarity={doc.get('similarity', 0)}")
            logger.info(f"Contenido del documento {i+1}: {doc.get('content', '')[:500]}{'...' if len(doc.get('content', '')) > 500 else ''}")
            
            # Crear objeto similar a Document para compatibilidad
            processed_doc = {
                'page_content': doc.get('content', ''),
                'metadata': doc.get('metadata', {}),
                'similarity': doc.get('similarity', 0)
            }
            processed_docs.append(processed_doc)
        
        # Serializar el contenido
        serialized = "\n\n".join(
            (f"Source: {doc['metadata']}\n" f"Content: {doc['page_content']}")
            for doc in processed_docs
        )
        
        logger.info(f"Contenido serializado generado, longitud: {len(serialized)}")
        logger.info(f"Contenido serializado completo: {serialized[:1000]}{'...' if len(serialized) > 1000 else ''}")
        return serialized, processed_docs
        
    except Exception as e:
        logger.error(f"Error durante la búsqueda: {str(e)}")
        raise

@tool(parse_docstring=False)
def search_items_retriever(query: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta simple para buscar información usando vector store.
    
    Args:
        query (str): La consulta del usuario
        state (dict): Estado del sistema
        
    Returns:
        str: Contenido relevante encontrado
    """
    logger.info(f"Tool search_items_retriever llamado con query: '{query}'")
    
    try:
        # Obtener project_id del estado si está disponible
        project = state.get("project")
        project_id = project.id if project else None
        
        serialized, docs = retrieve(query, project_id)
        
        if not serialized.strip():
            logger.warning("No se encontró información relevante - contenido vacío")
            return "No se encontró información relevante."
        
        logger.info("Búsqueda exitosa, retornando contenido")
        return serialized
        
    except Exception as e:
        logger.error(f"Error en search_items_retriever: {str(e)}")
        return f"Error al buscar información: {str(e)}" 