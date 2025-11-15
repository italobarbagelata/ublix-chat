"""
⚠️ HERRAMIENTA DEPRECADA - NO USAR ⚠️

Esta herramienta ha sido deprecada en favor de unified_search_tool.

USAR EN SU LUGAR:
    unified_search_tool(query, state, content_types=['faq'])

RAZONES DE DEPRECACIÓN:
- unified_search_tool proporciona mejor contexto global
- Combina FAQs con documentos y productos para respuestas más completas
- Menos llamadas al LLM (ahorro de ~30% tokens)
- Menor latencia (~200-400ms menos)
- Ranking global por relevancia

Este archivo se mantiene temporalmente por compatibilidad pero NO se usa.
Fecha de deprecación: 2025-01-XX
"""

import logging
from langchain.tools import tool
from supabase.client import Client, create_client
from langchain_openai import OpenAIEmbeddings
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
import os
from typing import List
import re
from functools import lru_cache

# Configure logging
logger = logging.getLogger(__name__)

# Singleton para cliente de embeddings
@lru_cache(maxsize=1)
def get_embeddings_client():
    """
    Singleton para el cliente de embeddings de OpenAI.
    Se inicializa una sola vez y se reutiliza en todas las llamadas.
    """
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        dimensions=384
    )

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
def faq_retriever(query: str, state: Annotated[dict, InjectedState], limit: int = 8) -> str:
    """
    Herramienta para buscar FAQs (Preguntas Frecuentes) relevantes en la base de conocimiento usando búsqueda semántica.
    
    Esta herramienta realiza una búsqueda de similitud semántica específicamente en FAQs
    y devuelve las preguntas y respuestas más relevantes encontradas.
    
    Args:
        query (str): La consulta del usuario
        state (dict): Estado del sistema que incluye la configuración del proyecto
        limit (int): Número máximo de FAQs a retornar (por defecto 8)
        
    Returns:
        str: FAQs relevantes encontradas, formateadas y combinadas
        
    Raises:
        ValueError: Si no se encuentra el proyecto o las credenciales de Supabase
    """
    try:
        logger.info(f"=== INICIO DE FAQ RETRIEVER ===")
        logger.info(f"Query recibida: {query}")
        logger.info(f"Límite de resultados: {limit}")

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

        # Obtener cliente de embeddings (singleton)
        logger.info("Obteniendo cliente de embeddings de OpenAI")
        embeddings = get_embeddings_client()

        # Extraer palabras clave de la consulta
        search_keywords = extract_keywords(query)
        logger.info(f"Palabras clave extraídas: {search_keywords}")

        # Realizar búsqueda semántica de FAQs
        logger.info(f"Realizando búsqueda semántica de FAQs para: {query}")
        
        # Generar embedding de la consulta
        query_embedding = embeddings.embed_query(query)
        
        # Buscar FAQs similares usando la función RPC search_faqs_semantic
        response = supabase_client.rpc(
            'search_faqs_semantic',
            {
                'query_embedding': query_embedding,
                'project_id_param': project.id,
                'similarity_threshold': 0.7,
                'limit_param': limit,
                'offset_param': 0
            }
        ).execute()
        
        logger.info(f"Respuesta recibida. FAQs encontradas: {len(response.data) if response.data else 0}")

        if not response.data:
            logger.warning("No se encontraron FAQs relevantes")
            return "No se encontraron preguntas frecuentes relevantes para tu consulta."

        # Procesar y formatear resultados de FAQs
        all_faqs = []
        seen_content = set()

        logger.info(f"Procesando {len(response.data)} FAQs")
        
        # Agregar log detallado de las primeras FAQs encontradas
        logger.info("=== FAQS ENCONTRADAS ===")
        for i, faq in enumerate(response.data[:3]):  # Solo las primeras 3 para no saturar logs
            logger.info(f"--- FAQ {i+1} ---")
            logger.info(f"ID: {faq.get('id')}")
            logger.info(f"Pregunta: {faq.get('question')}")
            logger.info(f"Respuesta: {faq.get('answer')[:100] if faq.get('answer') else 'Sin respuesta'}...")
            logger.info(f"Título: {faq.get('title')}")
            logger.info(f"Descripción: {faq.get('description')[:100] if faq.get('description') else 'Sin descripción'}...")
            logger.info(f"Similarity Score: {faq.get('similarity_score', 'N/A')}")
            logger.info("--- Fin FAQ ---")
        
        logger.info("=== FIN FAQS ===")
        
        for faq in response.data:
            faq_parts = []

            # Agregar título si existe
            if faq.get('title'):
                faq_parts.append(f"**{faq['title']}**")

            # Agregar descripción si existe
            if faq.get('description'):
                faq_parts.append(f"Descripción: {faq['description']}")

            # Agregar pregunta y respuesta (parte principal de la FAQ)
            if faq.get('question'):
                faq_parts.append(f"**Pregunta:** {faq['question']}")

            if faq.get('answer'):
                # Limitar la longitud de la respuesta para evitar respuestas muy largas
                answer = faq['answer']
                if len(answer) > 800:
                    answer = answer[:800] + "..."
                faq_parts.append(f"**Respuesta:** {answer}")

            # Agregar metadatos relevantes
            if faq.get('metadata') and faq['metadata']:
                metadata = faq['metadata']
                if isinstance(metadata, dict):
                    meta_parts = []
                    for key, value in metadata.items():
                        if key in ['author', 'created_date', 'updated_date', 'version', 'category', 'tags']:
                            meta_parts.append(f"{key.title()}: {value}")
                    if meta_parts:
                        faq_parts.append("Metadatos: " + ", ".join(meta_parts))

            # Agregar información de relevancia
            if faq.get('similarity_score') is not None:
                faq_parts.append(f"Relevancia: {faq['similarity_score']:.2%}")

            if not faq_parts:
                continue

            # Formatear como FAQ
            formatted_faq = f"[FAQ]\n" + "\n".join(faq_parts)

            # Evitar contenido duplicado usando ID como clave única
            content_key = faq.get('id', '')
            if content_key not in seen_content:
                all_faqs.append(formatted_faq)
                seen_content.add(content_key)

        if not all_faqs:
            return "No se encontraron preguntas frecuentes relevantes para tu consulta."

        # Combinar todas las FAQs
        combined_content = "\n\n---\n\n".join(all_faqs)
        logger.info(f"Se recuperaron {len(all_faqs)} FAQs únicas")

        # Log del contenido final que se envía al agente
        logger.info("=== CONTENIDO FINAL ENVIADO AL AGENTE ===")
        logger.info(f"Longitud del contenido: {len(combined_content)} caracteres")
        logger.info(f"Número de FAQs: {len(all_faqs)}")
        logger.info("=== FIN CONTENIDO FINAL ===")

        return combined_content

    except Exception as e:
        logger.error(f"Error en FAQ retriever tool: {str(e)}")
        return f"Error al buscar preguntas frecuentes: {str(e)}" 