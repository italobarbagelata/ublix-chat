import os
import re
import logging
from typing import Optional, Dict, Any, List
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
from openai import OpenAI
from dotenv import load_dotenv

# Configurar el logger
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración de OpenAI
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEY no está configurada en las variables de entorno")
    client = None
else:
    client = OpenAI(api_key=openai_api_key)

# App imports
from app.resources.postgresql import SupabaseDatabase


def extract_project_id_from_vector_store(vector_store_name: str) -> Optional[str]:
    """
    Extrae el project_id de un nombre de vector store que sigue el patrón:
    - 57262c65-dfc0-4ecc-9c82-e2f97676329e_products
    - 6a600ba7-57f6-47bb-bacc-9dfa4c33c1ca_vector_store
    """
    # Patrón para extraer UUID seguido de guión bajo y sufijo
    pattern = r'^([a-f0-9\-]{36})_(?:products|vector_store)$'
    match = re.match(pattern, vector_store_name)
    
    if match:
        return match.group(1)
    return None


def search_in_vector_store(query: str, vector_store_id: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Busca información en un vector store específico de OpenAI
    """
    if not client:
        return {"error": "Cliente de OpenAI no configurado. Verifique OPENAI_API_KEY"}
    
    try:
        import httpx
        
        # Realizar búsqueda usando el endpoint REST directo
        endpoint = f"https://api.openai.com/v1/vector_stores/{vector_store_id}/search"
        headers = {
            'Authorization': f'Bearer {openai_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            "query": query,
            "max_num_results": min(max_results, 50),
            "rewrite_query": True
        }

        logger.info(f"Realizando búsqueda REST en endpoint: {endpoint}")
        logger.info(f"Payload: {payload}")
        
        response = httpx.post(endpoint, headers=headers, json=payload, timeout=60)
        logger.info(f"Respuesta HTTP status: {response.status_code}")
        
        response.raise_for_status()
        search_data = response.json()
        logger.info(f"Datos de búsqueda recibidos: {search_data}")

        # Formatear resultados
        formatted_results = []
        raw_results = search_data.get("data", [])
        logger.info(f"Número de resultados raw: {len(raw_results)}")
        
        for i, result in enumerate(raw_results):
            logger.info(f"Procesando resultado raw {i+1}: {result}")
            content_text = ""
            if result.get("content"):
                content_text = result["content"][0].get("text", "") if result["content"] else ""
            
            # Limitar el contenido de cada resultado individual
            max_content_per_result = 1500  # Máximo 1500 caracteres por resultado
            if len(content_text) > max_content_per_result:
                # Buscar un punto de corte natural
                truncated = content_text[:max_content_per_result]
                last_period = truncated.rfind('.')
                last_newline = truncated.rfind('\n')
                
                cut_point = max(last_period, last_newline)
                if cut_point > max_content_per_result * 0.7:  # Si el corte está en el último 30%
                    content_text = content_text[:cut_point + 1] + "..."
                else:
                    content_text = content_text[:max_content_per_result] + "..."
                
                logger.info(f"Contenido del resultado {i+1} truncado de {len(result['content'][0].get('text', ''))} a {len(content_text)} caracteres")
            
            formatted_result = {
                "content": content_text,
                "filename": result.get("filename", "Archivo desconocido"),
                "score": result.get("score", 0),
                "file_id": result.get("file_id", ""),
                "metadata": result.get("attributes", {})
            }
            logger.info(f"Resultado formateado {i+1}: filename='{formatted_result['filename']}', content_length={len(formatted_result['content'])}, score={formatted_result['score']}")
            formatted_results.append(formatted_result)

        final_result = {
            "query": query,
            "vector_store_id": vector_store_id,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
        logger.info(f"Resultado final de search_in_vector_store: {final_result}")
        return final_result

    except ImportError:
        logger.error("httpx no está instalado")
        return {"error": "Dependencia httpx requerida para búsqueda directa"}
    except Exception as e:
        logger.error(f"Error en búsqueda: {str(e)}")
        return {"error": str(e)}


def find_vector_stores_for_project(project_id: str) -> list:
    """
    Busca vector stores que coincidan con el project_id usando la base de datos de Supabase
    """
    try:
        logger.info(f"Consultando datasources para proyecto: {project_id}")
        db = SupabaseDatabase()
        result = db.select(
            "datasources", 
            filters={"project_id": project_id}
        )
        logger.info(f"Datasources encontrados: {len(result) if result else 0}")
        
        vector_stores = []
        if result:
            for i, item in enumerate(result):
                logger.info(f"Procesando datasource {i+1}: {item}")
                metadata = item.get("metadata", {})
                logger.info(f"Metadata del datasource {i+1}: {metadata}")
                if metadata.get("vector_store_id"):
                    vector_store = {
                        "id": metadata["vector_store_id"],
                        "name": item["name"],
                        "datasource_id": item["datasource_id"]
                    }
                    logger.info(f"Vector store válido encontrado: {vector_store}")
                    vector_stores.append(vector_store)
                else:
                    logger.info(f"Datasource {i+1} no tiene vector_store_id")
        
        logger.info(f"Total vector stores encontrados: {len(vector_stores)}")
        return vector_stores
        
    except Exception as e:
        logger.error(f"Error buscando vector stores: {str(e)}")
        return []


@tool(parse_docstring=False)
def buscar_en_vector_openai(query: str, vector_store_id: Optional[str] = None, state: Annotated[dict, InjectedState] = None) -> str:
    """
    Herramienta simple para buscar información en vectores de OpenAI.
    
    Puede detectar automáticamente el ID del proyecto desde un vector store que siga el patrón:
    - 57262c65-dfc0-4ecc-9c82-e2f97676329e_products
    - 6a600ba7-57f6-47bb-bacc-9dfa4c33c1ca_vector_store
    
    Args:
        query (str): La consulta o pregunta del usuario
        vector_store_id (str, opcional): ID específico del vector store. Si no se proporciona, 
                                       busca automáticamente usando el project_id del estado
        state (dict): Estado del sistema que contiene información del proyecto
        
    Returns:
        str: Información encontrada en el vector store de OpenAI
    """
    logger.info(f"Búsqueda en vector OpenAI: '{query}', vector_store_id: {vector_store_id}")
    
    try:
        # Si se proporciona vector_store_id específico, usarlo directamente
        if vector_store_id:
            # Extraer project_id del vector_store_id si es posible
            project_id = extract_project_id_from_vector_store(vector_store_id)
            if project_id:
                logger.info(f"Project ID extraído del vector store: {project_id}")
            
            # Buscar directamente en el vector store especificado
            result = search_in_vector_store(query, vector_store_id)
        else:
            # Obtener project_id del estado
            if not state:
                return "Error: No se proporcionó vector_store_id ni estado del proyecto."
            
            project = state.get("project")
            if not project:
                return "Error: No se encontró información del proyecto en el estado."
            
            project_id = project.id
            logger.info(f"Buscando vector stores para proyecto: {project_id}")
            
            # Primero intentar buscar vector stores del proyecto en Supabase (solo para _vector_store)
            vector_stores = find_vector_stores_for_project(project_id)
            
            if vector_stores:
                # Usar el primer vector store encontrado en Supabase (_vector_store)
                vector_store_id = vector_stores[0]["id"]
                logger.info(f"Usando vector store desde Supabase: {vector_stores[0]['name']} (ID: {vector_store_id})")
                result = search_in_vector_store(query, vector_store_id)
            else:
                # Si no hay datasources en Supabase, intentar directamente con _products
                logger.info(f"No se encontraron datasources en Supabase, intentando con patrón _products")
                products_vector_store = f"{project_id}_products"
                
                logger.info(f"Intentando buscar con vector store: {products_vector_store}")
                result = search_in_vector_store(query, products_vector_store)
                
                if "error" in result:
                    logger.info(f"Vector store _products no funcionó: {result.get('error')}")
                    return f"No se encontraron vector stores para el proyecto {project_id}. Intenté con: {products_vector_store}"
                else:
                    logger.info(f"Vector store _products encontrado: {products_vector_store}")
                    vector_store_id = products_vector_store
        
        # Procesar resultado
        if "error" in result:
            return f"Error en la búsqueda: {result['error']}"
        
        results = result.get("results", [])
        if not results:
            return f"No se encontró información relevante para: '{query}' en el vector store {vector_store_id}"
        
        # Formatear respuesta
        response = f"**🔍 Resultados para: \"{query}\"**\n\n"
        response += f"*Vector Store: {result.get('vector_store_id')}*\n\n"
        
        for i, item in enumerate(results, 1):
            content = item.get("content", "").strip()
            filename = item.get("filename", "Archivo desconocido")
            score = item.get("score", 0)
            
            if content:
                response += f"**{i}. 📄 {filename}** (Relevancia: {score:.2f})\n"
                response += f"{content}\n\n"
                response += "---\n\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error en buscar_en_vector_openai: {str(e)}")
        return f"Error al buscar en vector OpenAI: {str(e)}" 