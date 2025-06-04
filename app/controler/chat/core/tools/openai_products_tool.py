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
    model: str = "gpt-4o-mini"
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


@tool(parse_docstring=False)
def list_openai_vector_stores(state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta para listar los vector stores de OpenAI disponibles en el proyecto actual.
    
    Esta herramienta muestra qué archivos y vector stores están disponibles para búsqueda
    en el proyecto actual.
    
    Args:
        state (dict): Estado del sistema que contiene información del proyecto
        
    Returns:
        str: Lista de vector stores disponibles en el proyecto
    """
    logger.info("Tool list_openai_vector_stores llamado")
    
    try:
        # Obtener project_id del estado
        project = state.get("project")
        if not project:
            logger.error("No se encontró información del proyecto en el estado")
            return "Error: No se pudo identificar el proyecto actual."
        
        project_id = project.id
        logger.info(f"Listando vector stores del proyecto: {project_id}")
        
        # Obtener vector stores del proyecto
        vector_stores = list_project_vector_stores(project_id)
        
        if not vector_stores:
            return "No se encontraron vector stores de OpenAI en este proyecto. Asegúrate de haber subido archivos con la opción de crear vector store habilitada."
        
        # Formatear respuesta
        response = f"**Vector Stores de OpenAI en el proyecto:**\n\n"
        
        for i, store in enumerate(vector_stores, 1):
            response += f"{i}. **{store['name']}**\n"
            response += f"   - ID: {store['id']}\n"
            response += f"   - Datasource ID: {store['datasource_id']}\n\n"
        
        response += f"Total: {len(vector_stores)} vector store(s) disponible(s)"
        
        logger.info(f"Listado exitoso, encontrados {len(vector_stores)} vector stores")
        return response
        
    except Exception as e:
        logger.error(f"Error en list_openai_vector_stores: {str(e)}")
        return f"Error al listar vector stores: {str(e)}"


def search_openai_products(
    query: str,
    project_id: str,
    vector_store_id: Optional[str] = None,
    max_results: int = 5  # Más resultados para productos ya que suelen ser más cortos
) -> Dict[str, Any]:
    """
    Buscar productos en vector stores de OpenAI específicos para productos
    """
    if not client:
        return {"error": "Cliente de OpenAI no configurado. Verifique OPENAI_API_KEY"}
    
    try:
        import httpx
        
        # Si no se proporciona vector_store_id, intentar construir uno usando el patrón project_id + "_products"
        if not vector_store_id:
            # Construir el vector store ID usando el patrón: project_id_products
            vector_store_id = f"{project_id}_products"
            logger.info(f"Construyendo vector store ID para productos: {vector_store_id}")

        # Realizar búsqueda usando el endpoint REST directo (mismo patrón que search_openai_files)
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

        logger.info(f"Realizando búsqueda REST de productos en endpoint: {endpoint}")
        logger.info(f"Payload: {payload}")
        
        response = httpx.post(endpoint, headers=headers, json=payload, timeout=60)
        logger.info(f"Respuesta HTTP status: {response.status_code}")
        
        response.raise_for_status()
        search_data = response.json()
        logger.info(f"Datos de búsqueda de productos recibidos: {search_data}")

        # Formatear resultados específicos para productos
        formatted_results = []
        raw_results = search_data.get("data", [])
        logger.info(f"Número de productos encontrados: {len(raw_results)}")
        
        for i, result in enumerate(raw_results):
            logger.info(f"Procesando producto {i+1}: {result}")
            content_text = ""
            if result.get("content"):
                content_text = result["content"][0].get("text", "") if result["content"] else ""
            
            # Para productos, mantener más contenido ya que suelen ser estructurados y más cortos
            max_content_per_product = 2000  # Más contenido para productos vs 1500 para documentos
            if len(content_text) > max_content_per_product:
                # Buscar un punto de corte natural
                truncated = content_text[:max_content_per_product]
                last_period = truncated.rfind('.')
                last_newline = truncated.rfind('\n')
                
                cut_point = max(last_period, last_newline)
                if cut_point > max_content_per_product * 0.7:  # Si el corte está en el último 30%
                    content_text = content_text[:cut_point + 1] + "..."
                else:
                    content_text = content_text[:max_content_per_product] + "..."
                
                logger.info(f"Contenido del producto {i+1} truncado de {len(result['content'][0].get('text', ''))} a {len(content_text)} caracteres")
            
            formatted_result = {
                "content": content_text,
                "filename": result.get("filename", "Producto desconocido"),
                "score": result.get("score", 0),
                "file_id": result.get("file_id", ""),
                "attributes": result.get("attributes", {})
            }
            logger.info(f"Producto formateado {i+1}: filename='{formatted_result['filename']}', content_length={len(formatted_result['content'])}, score={formatted_result['score']}")
            formatted_results.append(formatted_result)

        final_result = {
            "query": query,
            "vector_store_id": vector_store_id,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
        logger.info(f"Resultado final de search_openai_products: {final_result}")
        return final_result

    except ImportError:
        logger.error("[OpenAI Product Search] httpx no está instalado")
        return {"error": "Dependencia httpx requerida para búsqueda de productos"}
    except Exception as e:
        logger.error(f"[OpenAI Product Search] Error: {str(e)}")
        return {"error": str(e)}


def search_products_with_chat_completions(
    query: str, 
    vector_store_id: str,
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    Buscar productos usando Chat Completions API con file_search como fallback
    """
    if not client:
        return {"error": "Cliente de OpenAI no configurado. Verifique OPENAI_API_KEY"}
    
    try:
        logger.info(f"Iniciando búsqueda con Chat Completions para vector store: {vector_store_id}")
        
        # Crear un asistente temporal con file_search
        assistant = client.beta.assistants.create(
            name="Búsqueda de productos temporal",
            instructions="Eres un asistente especializado en buscar productos. Responde basándote únicamente en el contenido de los archivos de productos. Proporciona información detallada sobre los productos encontrados incluyendo características, precios y especificaciones.",
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
            content=f"Busca productos relacionados con: {query}. Proporciona información detallada de los productos encontrados."
        )

        # Ejecutar
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )

        # Esperar a que termine (máximo 30 segundos)
        max_wait = 30
        wait_time = 0
        while run.status in ['queued', 'in_progress'] and wait_time < max_wait:
            import time
            time.sleep(1)
            wait_time += 1
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            logger.info(f"Estado del run: {run.status}, tiempo esperado: {wait_time}s")

        # Obtener respuesta
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        
        # Limpiar recursos temporales
        try:
            client.beta.assistants.delete(assistant.id)
            client.beta.threads.delete(thread.id)
        except:
            pass  # Ignorar errores de limpieza

        if messages.data and run.status == 'completed':
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

            # Formatear como respuesta de productos
            formatted_results = [{
                "content": answer,
                "filename": "Búsqueda con Chat Completions",
                "score": 1.0,
                "file_id": "chat_completions",
                "attributes": {"method": "chat_completions", "citations": len(citations)}
            }]

            return {
                "query": query,
                "vector_store_id": vector_store_id,
                "results": formatted_results,
                "total_results": 1,
                "method": "chat_completions",
                "citations": citations
            }
        else:
            logger.error(f"Run no completado correctamente. Estado final: {run.status}")
            return {"error": f"No se pudo completar la búsqueda. Estado: {run.status}"}

    except Exception as e:
        logger.error(f"[Chat Completions Product Search] Error: {str(e)}")
        return {"error": str(e)}


@tool(parse_docstring=False)
def openai_product_search(query: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta para buscar productos en vector stores de OpenAI específicos para productos.
    
    Esta herramienta permite buscar información sobre productos que han sido almacenados
    en vector stores de OpenAI del proyecto. Busca directamente en el vector store de productos
    usando el patrón: project_id_products.
    
    Args:
        query (str): La consulta o pregunta sobre productos del usuario
        state (dict): Estado del sistema que contiene información del proyecto
        
    Returns:
        str: Respuesta con la información de productos encontrada en los vector stores de OpenAI
    """
    logger.info(f"Tool openai_product_search llamado con query: '{query}'")
    
    try:
        # Obtener project_id del estado
        project = state.get("project")
        if not project:
            logger.error("No se encontró información del proyecto en el estado")
            return "Error: No se pudo identificar el proyecto actual."
        
        project_id = project.id
        logger.info(f"Buscando productos en vector store del proyecto: {project_id}")
        
        # Buscar productos directamente sin depender de datasources
        logger.info("Iniciando búsqueda de productos en vector store...")
        result = search_openai_products(query, project_id)
        logger.info(f"Resultado de búsqueda de productos: {result}")
        
        if "error" in result:
            logger.error(f"Error en búsqueda de productos: {result['error']}")
            return f"No se pudo realizar la búsqueda de productos: {result['error']}\n\nVerifica que exista un vector store de productos con ID: {project_id}_products"
        
        # Formatear respuesta específica para productos
        results = result.get("results", [])
        logger.info(f"Búsqueda de productos exitosa - Número de productos encontrados: {len(results)}")
        
        if not results:
            logger.warning("Lista de productos está vacía")
            return f"No se encontraron productos relevantes para esta consulta en el vector store: {project_id}_products"
        
        # Log detallado de cada producto encontrado
        for i, product in enumerate(results):
            logger.info(f"Producto {i+1}: filename='{product.get('filename')}', score={product.get('score')}, content_length={len(product.get('content', ''))}")
        
        # Construir respuesta formateada específica para productos
        response = f"**🛍️ Productos encontrados para: \"{query}\"**\n\n"
        response += f"*Vector Store utilizado: {result.get('vector_store_id')}*\n\n"
        
        for i, product in enumerate(results, 1):
            content = product.get("content", "").strip()
            filename = product.get("filename", "Producto desconocido")
            score = product.get("score", 0)
            
            logger.info(f"Procesando producto {i}: filename='{filename}', content_empty={not content}")
            
            if content:
                response += f"**{i}. 📦 {filename}** (Relevancia: {score:.2f})\n"
                response += f"{content}\n\n"
                response += "---\n\n"
            else:
                logger.warning(f"Producto {i} tiene contenido vacío")
        
        logger.info(f"Respuesta de productos final construida (longitud: {len(response)}): {response[:200]}...")
        logger.info(f"Búsqueda de productos exitosa, retornando {len(results)} productos")
        logger.info(f"RESPUESTA COMPLETA DE PRODUCTOS QUE SE VA A RETORNAR: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Error en openai_product_search: {str(e)}")
        return f"Error al buscar productos en OpenAI: {str(e)}"


@tool(parse_docstring=False)
def openai_product_search_custom(query: str, vector_store_id: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta para buscar productos en un vector store específico de OpenAI.
    
    Esta herramienta permite buscar en un vector store específico de productos 
    proporcionando directamente el ID del vector store.
    
    Args:
        query (str): La consulta o pregunta sobre productos del usuario
        vector_store_id (str): ID específico del vector store de productos (ej: 57262c65-dfc0-4ecc-9c82-e2f97676329e_products)
        state (dict): Estado del sistema que contiene información del proyecto
        
    Returns:
        str: Respuesta con la información de productos encontrada en el vector store especificado
    """
    logger.info(f"Tool openai_product_search_custom llamado con query: '{query}' y vector_store_id: '{vector_store_id}'")
    
    try:
        # Obtener project_id del estado
        project = state.get("project")
        if not project:
            logger.error("No se encontró información del proyecto en el estado")
            return "Error: No se pudo identificar el proyecto actual."
        
        project_id = project.id
        logger.info(f"Buscando productos en vector store específico: {vector_store_id}")
        
        # Buscar productos usando el vector store ID específico
        logger.info("Iniciando búsqueda de productos en vector store específico...")
        result = search_openai_products(query, project_id, vector_store_id)
        logger.info(f"Resultado de búsqueda de productos: {result}")
        
        if "error" in result:
            logger.error(f"Error en búsqueda de productos: {result['error']}")
            return f"No se pudo realizar la búsqueda de productos en el vector store {vector_store_id}: {result['error']}"
        
        # Formatear respuesta específica para productos
        results = result.get("results", [])
        logger.info(f"Búsqueda de productos exitosa - Número de productos encontrados: {len(results)}")
        
        if not results:
            logger.warning("Lista de productos está vacía")
            return f"No se encontraron productos relevantes para esta consulta en el vector store: {vector_store_id}"
        
        # Log detallado de cada producto encontrado
        for i, product in enumerate(results):
            logger.info(f"Producto {i+1}: filename='{product.get('filename')}', score={product.get('score')}, content_length={len(product.get('content', ''))}")
        
        # Construir respuesta formateada específica para productos
        response = f"**🛍️ Productos encontrados para: \"{query}\"**\n\n"
        response += f"*Vector Store utilizado: {vector_store_id}*\n\n"
        
        for i, product in enumerate(results, 1):
            content = product.get("content", "").strip()
            filename = product.get("filename", "Producto desconocido")
            score = product.get("score", 0)
            
            logger.info(f"Procesando producto {i}: filename='{filename}', content_empty={not content}")
            
            if content:
                response += f"**{i}. 📦 {filename}** (Relevancia: {score:.2f})\n"
                response += f"{content}\n\n"
                response += "---\n\n"
            else:
                logger.warning(f"Producto {i} tiene contenido vacío")
        
        logger.info(f"Respuesta de productos final construida (longitud: {len(response)}): {response[:200]}...")
        logger.info(f"Búsqueda de productos exitosa, retornando {len(results)} productos")
        logger.info(f"RESPUESTA COMPLETA DE PRODUCTOS QUE SE VA A RETORNAR: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Error en openai_product_search_custom: {str(e)}")
        return f"Error al buscar productos en OpenAI: {str(e)}"


@tool(parse_docstring=False)
def list_openai_product_vector_stores(state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta para mostrar información sobre el vector store de productos del proyecto actual.
    
    Esta herramienta muestra el ID del vector store de productos que se utiliza
    para búsquedas, usando el patrón: project_id_products.
    
    Args:
        state (dict): Estado del sistema que contiene información del proyecto
        
    Returns:
        str: Información del vector store de productos del proyecto
    """
    logger.info("Tool list_openai_product_vector_stores llamado")
    
    try:
        # Obtener project_id del estado
        project = state.get("project")
        if not project:
            logger.error("No se encontró información del proyecto en el estado")
            return "Error: No se pudo identificar el proyecto actual."
        
        project_id = project.id
        logger.info(f"Mostrando información del vector store de productos del proyecto: {project_id}")
        
        # Construir el vector store ID esperado
        expected_vector_store_id = f"{project_id}_products"
        
        # Formatear respuesta específica para productos
        response = f"**🛍️ Vector Store de Productos en el proyecto:**\n\n"
        response += f"**📦 Vector Store de Productos**\n"
        response += f"   - ID esperado: **{expected_vector_store_id}**\n"
        response += f"   - Proyecto: {project_id}\n"
        response += f"   - Tipo: Vector Store de Productos (OpenAI)\n\n"
        response += f"*Nota: Este vector store se usa directamente para búsquedas de productos, no depende de datasources.*\n\n"
        response += f"Para buscar productos, usa la herramienta `openai_product_search` o `openai_product_search_custom` si tienes un ID específico."
        
        logger.info(f"Información del vector store de productos mostrada")
        return response
        
    except Exception as e:
        logger.error(f"Error en list_openai_product_vector_stores: {str(e)}")
        return f"Error al mostrar información del vector store de productos: {str(e)}"


@tool(parse_docstring=False)
def list_all_openai_vector_stores(state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta para mostrar información sobre vector stores de productos esperados.
    
    Esta herramienta muestra qué vector stores de productos deberían existir según el patrón
    usado, sin acceder directamente a la API de OpenAI.
    
    Args:
        state (dict): Estado del sistema que contiene información del proyecto
        
    Returns:
        str: Información sobre vector stores esperados
    """
    logger.info("Tool list_all_openai_vector_stores llamado")
    
    try:
        # Obtener project_id del estado para contexto
        project = state.get("project")
        if not project:
            return "Error: No se pudo identificar el proyecto actual."
        
        project_id = project.id
        logger.info(f"Mostrando información de vector stores para proyecto: {project_id}")
        
        # Formatear respuesta
        response = f"**🗂️ Información de Vector Stores para el proyecto:**\n\n"
        response += f"*Proyecto actual: {project_id}*\n\n"
        
        # Vector store de productos esperado
        expected_product_store = f"{project_id}_products"
        response += f"## 🛍️ Vector Store de Productos:\n\n"
        response += f"**Vector Store esperado para productos:**\n"
        response += f"   - ID: `{expected_product_store}`\n"
        response += f"   - Patrón: `{{project_id}}_products`\n"
        response += f"   - Tipo: Productos\n\n"
        
        response += f"## 📄 Vector Stores de Documentos:\n\n"
        response += f"**Los documentos usan datasources diferentes.**\n"
        response += f"Para ver vector stores de documentos, usa la herramienta `list_openai_vector_stores`\n\n"
        
        response += f"## 🔍 Cómo verificar si existe:\n\n"
        response += f"1. **Intenta buscar productos** con `openai_product_search`\n"
        response += f"2. **Si obtienes error 400 o 404**: El vector store no existe\n"
        response += f"3. **Si obtienes resultados**: El vector store existe y funciona\n\n"
        
        response += f"## 📝 Cómo crear el vector store:\n\n"
        response += f"1. Sube archivos de productos a OpenAI\n"
        response += f"2. Crea un vector store con ID: `{expected_product_store}`\n"
        response += f"3. Asigna los archivos al vector store\n\n"
        
        response += f"**Nota:** Esta herramienta no accede directamente a la API de OpenAI para listar vector stores, sino que muestra la información esperada según el patrón usado."
        
        logger.info(f"Información mostrada correctamente")
        return response
        
    except Exception as e:
        logger.error(f"Error en list_all_openai_vector_stores: {str(e)}")
        return f"Error al mostrar información de vector stores: {str(e)}" 