import os
import logging
from typing import Optional, Dict, Any, List
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
from openai import OpenAI
from dotenv import load_dotenv

# App imports
from app.resources.postgresql import SupabaseDatabase

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


def search_openai_files(
    query: str,
    project_id: str,
    vector_store_id: Optional[str] = None,
    max_results: int = 3  # Reducido de 5 a 3 para evitar respuestas muy largas
) -> Dict[str, Any]:
    """
    Buscar en archivos de OpenAI usando vector store con endpoint REST
    """
    if not client:
        return {"error": "Cliente de OpenAI no configurado. Verifique OPENAI_API_KEY"}
    
    try:
        import httpx
        
        if not vector_store_id:
            # Buscar vector stores del proyecto
            logger.info(f"Buscando vector stores para proyecto: {project_id}")
            vector_stores = list_project_vector_stores(project_id)
            logger.info(f"Vector stores encontrados: {len(vector_stores)}")
            if not vector_stores:
                return {"error": "No se encontraron vector stores para este proyecto"}
            vector_store_id = vector_stores[0]["id"]
            logger.info(f"Usando vector store: {vector_store_id}")

        # Realizar búsqueda usando el endpoint REST directo
        endpoint = f"https://api.openai.com/v1/vector_stores/{vector_store_id}/search"
        headers = {
            'Authorization': f'Bearer {openai_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            "query": query,
            "max_num_results": min(max_results, 50),  # Máximo 50 según la API
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
            
            # Limitar el contenido de cada resultado individual para evitar chunks excesivamente largos
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
                "attributes": result.get("attributes", {})
            }
            logger.info(f"Resultado formateado {i+1}: filename='{formatted_result['filename']}', content_length={len(formatted_result['content'])}, score={formatted_result['score']}")
            formatted_results.append(formatted_result)

        final_result = {
            "query": query,
            "vector_store_id": vector_store_id,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
        logger.info(f"Resultado final de search_openai_files: {final_result}")
        return final_result

    except ImportError:
        logger.error("[OpenAI Search] httpx no está instalado")
        return {"error": "Dependencia httpx requerida para búsqueda directa"}
    except Exception as e:
        logger.error(f"[OpenAI Search] Error: {str(e)}")
        return {"error": str(e)}


def list_project_vector_stores(project_id: str) -> List[Dict[str, Any]]:
    """
    Listar vector stores de un proyecto
    """
    try:
        logger.info(f"[List Vector Stores] Consultando datasources para proyecto: {project_id}")
        db = SupabaseDatabase()
        result = db.select(
            "datasources", 
            filters={"project_id": project_id}
        )
        logger.info(f"[List Vector Stores] Datasources encontrados: {len(result) if result else 0}")
        
        vector_stores = []
        if result:
            for i, item in enumerate(result):
                logger.info(f"[List Vector Stores] Procesando datasource {i+1}: {item}")
                metadata = item.get("metadata", {})
                logger.info(f"[List Vector Stores] Metadata del datasource {i+1}: {metadata}")
                if metadata.get("vector_store_id"):
                    vector_store = {
                        "id": metadata["vector_store_id"],
                        "name": item["name"],
                        "datasource_id": item["datasource_id"]
                    }
                    logger.info(f"[List Vector Stores] Vector store válido encontrado: {vector_store}")
                    vector_stores.append(vector_store)
                else:
                    logger.info(f"[List Vector Stores] Datasource {i+1} no tiene vector_store_id")
        
        logger.info(f"[List Vector Stores] Total vector stores encontrados: {len(vector_stores)}")
        return vector_stores
        
    except Exception as e:
        logger.error(f"[List Vector Stores] Error: {str(e)}")
        return []


def search_with_chat_completions(
    query: str,
    project_id: str,
    vector_store_id: Optional[str] = None,
    model: str = os.getenv("MODEL_CHATBOT")
) -> Dict[str, Any]:
    """
    Buscar usando Chat Completions API con file_search
    """
    if not client:
        return {"error": "Cliente de OpenAI no configurado. Verifique OPENAI_API_KEY"}
    
    try:
        if not vector_store_id:
            # Buscar vector stores del proyecto
            vector_stores = list_project_vector_stores(project_id)
            if not vector_stores:
                return {"error": "No se encontraron vector stores para este proyecto"}
            vector_store_id = vector_stores[0]["id"]

        # Crear un asistente temporal con file_search
        assistant = client.beta.assistants.create(
            name="Búsqueda temporal",
            instructions="Eres un asistente que busca información en archivos. Responde basándote únicamente en el contenido de los archivos.",
            model=model,
            tools=[{"type": "file_search"}],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [vector_store_id]
                }
            }
        )

        # Crear un thread
        thread = client.beta.threads.create()

        # Enviar mensaje
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=query
        )

        # Ejecutar
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )

        # Esperar a que termine
        while run.status in ['queued', 'in_progress']:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

        # Obtener respuesta
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        
        # Limpiar recursos temporales
        try:
            client.beta.assistants.delete(assistant.id)
            client.beta.threads.delete(thread.id)
        except:
            pass  # Ignorar errores de limpieza

        if messages.data:
            answer = messages.data[0].content[0].text.value
            
            # Extraer archivos citados si están disponibles
            citations = []
            if hasattr(messages.data[0].content[0].text, 'annotations'):
                for annotation in messages.data[0].content[0].text.annotations:
                    if hasattr(annotation, 'file_citation'):
                        citations.append({
                            "file_id": annotation.file_citation.file_id,
                            "quote": annotation.file_citation.quote
                        })

            return {
                "query": query,
                "answer": answer,
                "citations": citations,
                "vector_store_id": vector_store_id,
                "model": model
            }
        else:
            return {"error": "No se pudo obtener respuesta"}

    except Exception as e:
        logger.error(f"[Chat Completions Search] Error: {str(e)}")
        return {"error": str(e)}


@tool(parse_docstring=False)
def openai_vector_search(query: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta para buscar información en archivos subidos a OpenAI usando vector stores.
    
    Esta herramienta permite consultar documentos que han sido subidos a OpenAI y 
    almacenados en vector stores del proyecto. Es útil para buscar información específica
    en documentos, PDFs, archivos de texto y otros formatos soportados.
    
    Args:
        query (str): La consulta o pregunta del usuario
        state (dict): Estado del sistema que contiene información del proyecto
        
    Returns:
        str: Respuesta con la información encontrada en los archivos de OpenAI
    """
    logger.info(f"Tool openai_vector_search llamado con query: '{query}'")
    
    try:
        # Obtener project_id del estado
        project = state.get("project")
        if not project:
            logger.error("No se encontró información del proyecto en el estado")
            return "Error: No se pudo identificar el proyecto actual."
        
        project_id = project.id
        logger.info(f"Buscando en vector stores del proyecto: {project_id}")
        
        # Primero intentar con la búsqueda directa en vector store
        logger.info("Iniciando búsqueda directa en vector store...")
        result = search_openai_files(query, project_id)
        logger.info(f"Resultado de búsqueda directa: {result}")
        
        if "error" in result:
            logger.warning(f"Error en búsqueda directa: {result['error']}")
            # Si falla la búsqueda directa, intentar con Chat Completions
            logger.info("Intentando con Chat Completions...")
            result = search_with_chat_completions(query, project_id)
            logger.info(f"Resultado de Chat Completions: {result}")
            
            if "error" in result:
                logger.error(f"Error en ambos métodos de búsqueda: {result['error']}")
                return f"No se pudo realizar la búsqueda: {result['error']}"
            
            # Formatear respuesta de Chat Completions
            answer = result.get("answer", "No se encontró información")
            citations = result.get("citations", [])
            logger.info(f"Chat Completions - Answer: {answer[:100]}..., Citations: {len(citations)}")
            
            response = f"**Respuesta:** {answer}\n\n"
            if citations:
                response += "**Fuentes citadas:**\n"
                for i, citation in enumerate(citations, 1):
                    response += f"{i}. Archivo ID: {citation['file_id']}\n"
                    if citation.get('quote'):
                        response += f"   Cita: \"{citation['quote'][:200]}...\"\n"
            
            logger.info(f"Retornando respuesta de Chat Completions (longitud: {len(response)})")
            return response
        
        # Formatear respuesta de búsqueda directa
        results = result.get("results", [])
        logger.info(f"Búsqueda directa exitosa - Número de resultados: {len(results)}")
        
        if not results:
            logger.warning("Lista de resultados está vacía")
            return "No se encontró información relevante en los archivos de OpenAI para esta consulta."
        
        # Log detallado de cada resultado
        for i, doc in enumerate(results):
            logger.info(f"Resultado {i+1}: filename='{doc.get('filename')}', score={doc.get('score')}, content_length={len(doc.get('content', ''))}")
        
        # Construir respuesta formateada
        response = f"**Información encontrada para: \"{query}\"**\n\n"
        
        for i, doc in enumerate(results, 1):
            content = doc.get("content", "").strip()
            filename = doc.get("filename", "Archivo desconocido")
            score = doc.get("score", 0)
            
            logger.info(f"Procesando resultado {i}: filename='{filename}', content_empty={not content}")
            
            if content:
                response += f"**{i}. {filename}** (Relevancia: {score:.2f})\n"
                # Mostrar el contenido completo sin truncar para preservar información relevante
                response += f"{content}\n\n"
            else:
                logger.warning(f"Resultado {i} tiene contenido vacío")
        
        logger.info(f"Respuesta final construida (longitud: {len(response)}): {response[:200]}...")
        logger.info(f"Búsqueda exitosa, retornando {len(results)} resultados")
        logger.info(f"RESPUESTA COMPLETA QUE SE VA A RETORNAR: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Error en openai_vector_search: {str(e)}")
        return f"Error al buscar en archivos de OpenAI: {str(e)}" 