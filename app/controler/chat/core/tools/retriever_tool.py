import logging
from langchain.tools import tool
from supabase.client import Client, create_client
from langchain_openai import OpenAIEmbeddings
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
import os
from typing import List
import re

# Configure logging
logger = logging.getLogger(__name__)

def extract_keywords(query: str) -> List[str]:
    """
    Extrae palabras clave relevantes de la consulta para la búsqueda híbrida.
    
    Args:
        query (str): La consulta del usuario
        
    Returns:
        List[str]: Lista de palabras clave extraídas
    """
    # Convertir a minúsculas y dividir por espacios y signos de puntuación
    words = re.findall(r'\b\w+\b', query.lower())
    
    # Filtrar palabras comunes (stop words) en español
    stop_words = {
        'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 
        'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del', 'los', 'las',
        'como', 'pero', 'sus', 'le', 'ha', 'esta', 'si', 'porque', 'o', 'cuando',
        'muy', 'sin', 'sobre', 'este', 'ya', 'todo', 'esta', 'uno', 'puede', 'hay',
        'me', 'mi', 'tu', 'nos', 'yo', 'he', 'ser', 'estar', 'tener', 'hacer'
    }
    
    # Filtrar palabras que sean demasiado cortas o sean stop words
    keywords = [word for word in words if len(word) >= 3 and word not in stop_words]
    
    # Limitar a las primeras 10 palabras clave más relevantes
    return keywords[:10]

@tool(parse_docstring=False)
def document_retriever(query: str, state: Annotated[dict, InjectedState], filenames: List[str] = None) -> str:
    """
    Herramienta para buscar documentos relevantes en la base de conocimiento usando búsqueda semántica.
    
    Esta herramienta realiza una búsqueda de similitud semántica específicamente en documentos
    y devuelve el contenido más relevante encontrado.
    
    Args:
        query (str): La consulta del usuario
        state (dict): Estado del sistema que incluye la configuración del proyecto
        filenames (List[str], optional): Lista de nombres de archivos específicos para filtrar
        
    Returns:
        str: Documentos relevantes encontrados, formateados y combinados
        
    Raises:
        ValueError: Si no se encuentra el proyecto o las credenciales de Supabase
    """
    try:
        logger.info(f"=== INICIO DE DOCUMENT RETRIEVER ===")
        logger.info(f"Query recibida: {query}")
        logger.info(f"Filtros - Archivos: {filenames}")

        project = state.get("project")
        if not project:
            logger.error("No se encontró el proyecto en el estado")
            raise ValueError("Project not found in state")

        # Obtener credenciales de Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        if not supabase_url or not supabase_key:
            logger.error("No se encontraron las credenciales de Supabase en las variables de entorno")
            raise ValueError("Supabase credentials not found in environment variables")

        # Inicializar cliente de Supabase
        supabase_client = create_client(supabase_url, supabase_key)
        logger.info("Cliente de Supabase inicializado correctamente")

        # Inicializar embeddings de OpenAI
        logger.info("Inicializando embeddings de OpenAI")
        embeddings = OpenAIEmbeddings()

        # Extraer palabras clave de la consulta
        search_keywords = extract_keywords(query)
        logger.info(f"Palabras clave extraídas: {search_keywords}")

        # Realizar búsqueda semántica e híbrida de documentos
        logger.info(f"Realizando búsqueda semántica para: {query}")
        
        # Generar embedding de la consulta
        query_embedding = embeddings.embed_query(query)
        
        # Buscar documentos similares usando la función RPC match_documents_v1
        response = supabase_client.rpc(
            'match_documents_v20',
            {
                'query_embedding': query_embedding,
                'match_count': 20,
                'project_id_filter': project.id,
                'type_filter': 'document',
                'category_filter': None,
                'min_price': None,
                'max_price': None
            }
        ).execute()
        
        logger.info(f"Respuesta recibida. Documentos encontrados: {len(response.data) if response.data else 0}")

        if not response.data:
            logger.warning("No se encontraron documentos relevantes")
            return "No se encontró información relevante para tu consulta."

        # Filtrar por project_id en el código Python
        filtered_docs = [doc for doc in response.data if doc.get('project_id') == project.id]
        logger.info(f"Documentos filtrados por project_id: {len(filtered_docs)}")
        
        # Filtrar por nombres de archivos si se proporcionan
        if filenames:
            filtered_docs = [doc for doc in filtered_docs if doc.get('filename') in filenames]
            logger.info(f"Documentos filtrados por filename: {len(filtered_docs)}")
        
        # Limitar a los mejores 8 resultados (como estaba antes)
        filtered_docs = filtered_docs[:8]
        
        if not filtered_docs:
            logger.warning("No se encontraron documentos relevantes después del filtrado")
            return "No se encontró información relevante para tu consulta en este proyecto."

        # Procesar y formatear resultados de documentos
        all_documents = []
        seen_content = set()

        logger.info(f"Procesando {len(filtered_docs)} documentos")
        
        # Agregar log detallado de los primeros documentos encontrados
        logger.info("=== DOCUMENTOS ENCONTRADOS ===")
        for i, doc in enumerate(filtered_docs[:3]):  # Solo los primeros 3 para no saturar logs
            logger.info(f"--- Documento {i+1} ---")
            logger.info(f"ID: {doc.get('id')}")
            logger.info(f"Título: {doc.get('title')}")
            logger.info(f"Descripción: {doc.get('description')[:100] if doc.get('description') else 'Sin descripción'}...")
            logger.info(f"Filename: {doc.get('filename')}")
            logger.info(f"Pregunta: {doc.get('question')}")
            logger.info(f"Respuesta: {doc.get('answer')[:100] if doc.get('answer') else 'Sin respuesta'}...")
            logger.info(f"Contenido: {doc.get('content')[:100] if doc.get('content') else 'Sin contenido'}...")
            logger.info(f"Tags: {doc.get('tags')}")
            logger.info(f"Similarity: {doc.get('similarity', 'N/A')}")
            logger.info(f"Keyword matches: {doc.get('keyword_matches', 'N/A')}")
            logger.info(f"Hybrid score: {doc.get('hybrid_score', 'N/A')}")
            logger.info("--- Fin Documento ---")
        
        logger.info("=== FIN DOCUMENTOS ===")
        
        for doc in filtered_docs:
            content_parts = []

            # Agregar título si existe
            if doc.get('title'):
                content_parts.append(f"**{doc['title']}**")

            # Agregar filename si existe
            if doc.get('filename'):
                content_parts.append(f"Archivo: {doc['filename']}")
            
            # Agregar descripción si existe
            if doc.get('description'):
                content_parts.append(f"Descripción: {doc['description']}")

            # Para FAQs o documentos Q&A, agregar pregunta y respuesta
            if doc.get('question') and doc.get('answer'):
                content_parts.append(f"Pregunta: {doc['question']}")
                content_parts.append(f"Respuesta: {doc['answer']}")

            # Agregar contenido solo si no es HTML puro y es relevante
            # Evitamos contenido HTML crudo que no sea útil
            if doc.get('content') and not doc['content'].startswith('<'):
                # Limitar la longitud del contenido para evitar respuestas muy largas
                content = doc['content']
                if len(content) > 500:
                    content = content[:500] + "..."
                content_parts.append(f"Contenido: {content}")

            # Agregar tags si existen
            if doc.get('tags') and doc['tags']:
                tags_str = ", ".join(doc['tags'])
                content_parts.append(f"Tags: {tags_str}")

            # Agregar metadatos relevantes
            if doc.get('metadata') and doc['metadata']:
                metadata = doc['metadata']
                if isinstance(metadata, dict):
                    meta_parts = []
                    for key, value in metadata.items():
                        if key in ['author', 'created_date', 'updated_date', 'version', 'section']:
                            meta_parts.append(f"{key.title()}: {value}")
                    if meta_parts:
                        content_parts.append("Metadatos: " + ", ".join(meta_parts))

            # Agregar información de relevancia mejorada
            relevance_info = []
            if doc.get('similarity'):
                relevance_info.append(f"Similitud semántica: {doc['similarity']:.2%}")
            if doc.get('keyword_matches') is not None:
                relevance_info.append(f"Coincidencias de palabras clave: {doc['keyword_matches']}")
            if doc.get('hybrid_score'):
                relevance_info.append(f"Puntuación híbrida: {doc['hybrid_score']:.2%}")
            
            if relevance_info:
                content_parts.append("Relevancia: " + " | ".join(relevance_info))

            if not content_parts:
                continue

            # Formatear como documento
            formatted_content = f"[DOCUMENTO]\n" + "\n".join(content_parts)

            # Evitar contenido duplicado usando ID como clave única
            content_key = doc.get('id', '')
            if content_key not in seen_content:
                all_documents.append(formatted_content)
                seen_content.add(content_key)

        if not all_documents:
            return "No se encontró contenido relevante para tu consulta."

        # Combinar todos los documentos
        combined_content = "\n\n---\n\n".join(all_documents)
        logger.info(f"Se recuperaron {len(all_documents)} documentos únicos")

        # Log del contenido final que se envía al agente
        logger.info("=== CONTENIDO FINAL ENVIADO AL AGENTE ===")
        logger.info(f"Longitud del contenido: {len(combined_content)} caracteres")
        logger.info(f"Número de documentos: {len(all_documents)}")
        logger.info("=== FIN CONTENIDO FINAL ===")

        return combined_content

    except Exception as e:
        logger.error(f"Error en document retriever tool: {str(e)}")
        return f"Error al buscar información: {str(e)}"