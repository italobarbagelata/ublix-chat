import logging
from langchain.tools import tool
from supabase.client import Client, create_client
from langchain_openai import OpenAIEmbeddings
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
import os
from typing import List, Optional, Dict, Any
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
def unified_search_tool(
    query: str, 
    state: Annotated[dict, InjectedState], 
    content_types: Optional[List[str]] = None,
    limit: int = 15,
    category: Optional[str] = None
) -> str:
    """
    Herramienta unificada para buscar en todos los tipos de contenido (documentos, FAQs, productos) 
    usando búsqueda semántica y por texto.
    
    Esta herramienta reemplaza las herramientas separadas de documentos, FAQs y productos,
    proporcionando una búsqueda más eficiente y completa.
    
    Args:
        query (str): La consulta del usuario
        state (dict): Estado del sistema que incluye la configuración del proyecto
        content_types (List[str], optional): Tipos de contenido a buscar. 
            Opciones: ['document', 'faq', 'product']. Por defecto busca en todos.
        limit (int): Número máximo de resultados a retornar (por defecto 15)
        category (str, optional): Categoría específica para filtrar productos
        
    Returns:
        str: Contenido relevante encontrado, formateado y organizado por tipo
        
    Raises:
        ValueError: Si no se encuentra el proyecto o las credenciales de Supabase
    """
    try:
        logger.info(f"=== INICIO DE UNIFIED SEARCH TOOL ===")
        logger.info(f"Query recibida: {query}")
        logger.info(f"Tipos de contenido: {content_types}")
        logger.info(f"Límite: {limit}")
        logger.info(f"Categoría: {category}")

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
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=384
        )

        # Extraer palabras clave de la consulta
        search_keywords = extract_keywords(query)
        logger.info(f"Palabras clave extraídas: {search_keywords}")

        # Configurar tipos de contenido por defecto si no se especifican
        if content_types is None:
            content_types = ['document', 'faq', 'product']
        
        # Generar embedding de la consulta
        query_embedding = embeddings.embed_query(query)
        
        # Realizar búsqueda unificada
        logger.info(f"Realizando búsqueda unificada para: {query}")
        
        # Preparar parámetros para la función RPC
        rpc_params = {
            'query_embedding': query_embedding,
            'query_text': query,
            'project_id_filter': project.id,
            'content_types': content_types,
            'match_count': limit,
            'similarity_threshold': 0.5,
            'category_filter': category,
            'min_price': None,
            'max_price': None
        }
        
        # Buscar contenido usando la función RPC unificada
        response = supabase_client.rpc(
            'search_all_content_unified',
            rpc_params
        ).execute()
        
        logger.info(f"Respuesta recibida. Resultados encontrados: {len(response.data) if response.data else 0}")

        if not response.data:
            logger.warning("No se encontró contenido relevante")
            return "No se encontró información relevante para tu consulta."

        # Organizar resultados por tipo
        results_by_type = {
            'faq': [],
            'document': [],
            'product': []
        }
        
        for item in response.data:
            item_type = item.get('type', 'unknown')
            if item_type in results_by_type:
                results_by_type[item_type].append(item)

        # Procesar y formatear resultados
        all_content = []
        
        # Procesar FAQs primero (prioridad alta)
        if results_by_type['faq']:
            faq_section = ["## 📋 PREGUNTAS FRECUENTES"]
            for faq in results_by_type['faq']:
                faq_parts = []
                
                if faq.get('title'):
                    faq_parts.append(f"**{faq['title']}**")
                
                if faq.get('question'):
                    faq_parts.append(f"**Pregunta:** {faq['question']}")
                
                if faq.get('answer'):
                    answer = faq['answer']
                    if len(answer) > 500:
                        answer = answer[:500] + "..."
                    faq_parts.append(f"**Respuesta:** {answer}")
                
                if faq.get('similarity'):
                    faq_parts.append(f"*Relevancia: {faq['similarity']:.1%}*")
                
                if faq_parts:
                    faq_section.append("\n".join(faq_parts))
                    faq_section.append("---")
            
            if len(faq_section) > 1:  # Si hay más que solo el título
                all_content.append("\n".join(faq_section[:-1]))  # Excluir el último "---"

        # Procesar documentos
        if results_by_type['document']:
            doc_section = ["## 📄 DOCUMENTOS"]
            for doc in results_by_type['document']:
                doc_parts = []
                
                if doc.get('title'):
                    doc_parts.append(f"**{doc['title']}**")
                
                if doc.get('filename'):
                    doc_parts.append(f"*Archivo: {doc['filename']}*")
                
                if doc.get('description'):
                    doc_parts.append(f"**Descripción:** {doc['description']}")
                
                if doc.get('content'):
                    content = doc['content']
                    if len(content) > 400:
                        content = content[:400] + "..."
                    doc_parts.append(f"**Contenido:** {content}")
                
                if doc.get('tags') and doc['tags']:
                    tags_str = ", ".join(doc['tags'])
                    doc_parts.append(f"**Tags:** {tags_str}")
                
                if doc.get('similarity'):
                    doc_parts.append(f"*Relevancia: {doc['similarity']:.1%}*")
                
                if doc_parts:
                    doc_section.append("\n".join(doc_parts))
                    doc_section.append("---")
            
            if len(doc_section) > 1:
                all_content.append("\n".join(doc_section[:-1]))

        # Procesar productos
        if results_by_type['product']:
            product_section = ["## 🛍️ PRODUCTOS"]
            for product in results_by_type['product']:
                product_parts = []
                
                if product.get('title'):
                    product_parts.append(f"**{product['title']}**")
                
                if product.get('price') is not None:
                    price = product['price']
                    currency = product.get('currency', 'CLP')
                    product_parts.append(f"**Precio:** ${price:,.0f} {currency}")
                
                if product.get('description'):
                    product_parts.append(f"**Descripción:** {product['description']}")
                
                if product.get('stock') is not None:
                    stock = product['stock']
                    if stock > 0:
                        product_parts.append(f"**Stock:** {stock} unidades disponibles")
                    else:
                        product_parts.append("**Stock:** ⚠️ Sin stock")
                
                if product.get('source_url'):
                    product_parts.append(f"**URL:** {product['source_url']}")
                
                if product.get('images') and product['images']:
                    images = product['images']
                    if isinstance(images, list) and len(images) > 0:
                        product_parts.append(f"**Imágenes:** {len(images)} disponible(s)")
                
                if product.get('similarity'):
                    product_parts.append(f"*Relevancia: {product['similarity']:.1%}*")
                
                if product_parts:
                    product_section.append("\n".join(product_parts))
                    product_section.append("---")
            
            if len(product_section) > 1:
                all_content.append("\n".join(product_section[:-1]))

        if not all_content:
            return "No se encontró contenido relevante para tu consulta."

        # Combinar todo el contenido
        combined_content = "\n\n".join(all_content)
        
        # Agregar resumen de resultados
        summary_parts = []
        if results_by_type['faq']:
            summary_parts.append(f"{len(results_by_type['faq'])} FAQ(s)")
        if results_by_type['document']:
            summary_parts.append(f"{len(results_by_type['document'])} documento(s)")
        if results_by_type['product']:
            summary_parts.append(f"{len(results_by_type['product'])} producto(s)")
        
        summary = f"**Resumen:** Encontré {', '.join(summary_parts)} relevantes para tu consulta."
        
        final_response = f"{summary}\n\n{combined_content}"
        
        logger.info(f"Se recuperaron {len(response.data)} resultados totales")
        logger.info(f"Distribución: {len(results_by_type['faq'])} FAQs, {len(results_by_type['document'])} docs, {len(results_by_type['product'])} productos")

        return final_response

    except Exception as e:
        logger.error(f"Error en unified search tool: {str(e)}")
        return f"Error al buscar información: {str(e)}" 