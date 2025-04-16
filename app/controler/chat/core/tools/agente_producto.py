import logging
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from app.controler.scraping.web_scraping import WebScrapingTool
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
import unicodedata
from datetime import datetime, timedelta
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory

# Configurar el logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AgenteProducto:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.web_tool = WebScrapingTool()
        self.vector_store = SupabaseVectorStore(
            client=self.web_tool.supabase,
            embedding=self.embeddings,
            table_name="products",
            query_name="match_products_v3"
        )
        self.historial_busquedas = {}
        self.preferencias_clientes = {}
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.llm = ChatOpenAI(temperature=0)
        self._setup_agent()

    def _setup_agent(self):
        """Configura el agente con sus herramientas y prompt"""
        tools = [
            tool(
                "buscar_productos",
                func=self.buscar_productos_interno,
                description="Busca productos en la base de datos. Puedes filtrar por categoría, precio y otros criterios."
            ),
            tool(
                "obtener_recomendaciones",
                func=self.obtener_recomendaciones,
                description="Obtiene recomendaciones personalizadas basadas en el historial del cliente."
            )
        ]

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un agente especializado en ventas y productos. Tu objetivo es ayudar a los usuarios a encontrar los productos que necesitan.
            Usa el historial de conversación para entender mejor las necesidades del usuario.
            Cuando busques productos, considera:
            - Preferencias previas del usuario
            - Categorías frecuentes
            - Promociones activas
            - Disponibilidad de stock
            - Precios competitivos
            
            Siempre intenta proporcionar recomendaciones personalizadas y relevantes."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_openai_functions_agent(self.llm, tools, prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=self.memory,
            verbose=True
        )

    def normalizar_texto(self, text: str) -> str:
        """Normaliza el texto eliminando acentos y convirtiendo a minúsculas."""
        if not text:
            return ""
        return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                      if unicodedata.category(c) != 'Mn')

    def calcular_relevancia(self, producto: Dict, query_words: List[str]) -> float:
        """Calcula la relevancia de un producto basado en la consulta."""
        score = 0
        title = self.normalizar_texto(producto.get("title", ""))
        description = self.normalizar_texto(producto.get("description", ""))
        category = self.normalizar_texto(producto.get("category", ""))
        
        for word in query_words:
            if word in title:
                score += 1.0
            if word in description:
                score += 0.5
            if word in category:
                score += 0.8
                
        # Bonus por productos en promoción
        if producto.get("metadata", {}).get("is_promotion", False):
            score += 0.5
            
        # Bonus por productos con stock disponible
        if producto.get("metadata", {}).get("stock", 0) > 0:
            score += 0.3
            
        return score

    def buscar_sql_directo(
        self,
        query: str,
        project_id: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 5
    ) -> List[Dict]:
        """Búsqueda SQL directa como fallback cuando la búsqueda semántica no da resultados."""
        try:
            # Normalizar la query
            query_normalized = self.normalizar_texto(query)
            query_words = query_normalized.split()
            
            # Construir condiciones de búsqueda
            conditions = []
            for word in query_words:
                if len(word) > 2:  # Solo buscar palabras de más de 2 caracteres
                    conditions.append(f"title.ilike.%{word}%")
                    conditions.append(f"description.ilike.%{word}%")
                    conditions.append(f"category.ilike.%{word}%")
            
            # Construir consulta base
            sql_query = self.web_tool.supabase.table("products").select(
                "id,title,description,price,currency,sku,category,tags,images,metadata,source_url,created_at,project_id"
            )
            
            # Aplicar condiciones de búsqueda
            if conditions:
                sql_query = sql_query.or_(",".join(conditions))
            
            # Aplicar filtros adicionales
            if project_id:
                sql_query = sql_query.eq("project_id", project_id)
            if category:
                sql_query = sql_query.eq("category", category)
            if min_price is not None:
                sql_query = sql_query.gte("price", min_price)
            if max_price is not None:
                sql_query = sql_query.lte("price", max_price)
            
            # Ejecutar consulta
            data = sql_query.limit(limit * 2).execute()
            
            # Procesar resultados
            productos = []
            for item in data.data:
                score = self.calcular_relevancia(item, query_words)
                if score > 0:
                    producto = {
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                        "price": float(item.get("price", 0)) if item.get("price") is not None else 0,
                        "currency": item.get("currency", "CLP"),
                        "sku": item.get("sku", ""),
                        "category": item.get("category", ""),
                        "tags": item.get("tags", []),
                        "images": item.get("images", []),
                        "metadata": item.get("metadata", {}),
                        "source_url": item.get("source_url", ""),
                        "score": score,
                        "stock": item.get("metadata", {}).get("stock", 0),
                        "is_promotion": item.get("metadata", {}).get("is_promotion", False)
                    }
                    productos.append(producto)
            
            # Ordenar por relevancia
            productos.sort(key=lambda x: x["score"], reverse=True)
            return productos[:limit]
            
        except Exception as e:
            logger.error(f"Error en búsqueda SQL directa: {str(e)}")
            return []

    def obtener_recomendaciones(self, cliente_id: str, limit: int = 5) -> List[Dict]:
        """Obtiene recomendaciones personalizadas basadas en el historial del cliente."""
        preferencias = self.preferencias_clientes.get(cliente_id, {})
        if not preferencias:
            return []
            
        # Construir query basada en preferencias
        query_words = []
        if preferencias.get("categorias_frecuentes"):
            query_words.extend(preferencias["categorias_frecuentes"][:3])
        if preferencias.get("ultimas_busquedas"):
            query_words.extend(preferencias["ultimas_busquedas"][:2])
            
        if not query_words:
            return []
            
        query = " ".join(query_words)
        return self.buscar_productos_interno(query, limit=limit)

    def actualizar_preferencias(self, cliente_id: str, busqueda: str, categoria: Optional[str] = None):
        """Actualiza las preferencias del cliente basadas en sus búsquedas."""
        if cliente_id not in self.preferencias_clientes:
            self.preferencias_clientes[cliente_id] = {
                "ultimas_busquedas": [],
                "categorias_frecuentes": [],
                "ultima_actualizacion": datetime.now()
            }
            
        # Actualizar últimas búsquedas
        self.preferencias_clientes[cliente_id]["ultimas_busquedas"].append(busqueda)
        if len(self.preferencias_clientes[cliente_id]["ultimas_busquedas"]) > 10:
            self.preferencias_clientes[cliente_id]["ultimas_busquedas"].pop(0)
            
        # Actualizar categorías frecuentes
        if categoria:
            self.preferencias_clientes[cliente_id]["categorias_frecuentes"].append(categoria)
            if len(self.preferencias_clientes[cliente_id]["categorias_frecuentes"]) > 5:
                self.preferencias_clientes[cliente_id]["categorias_frecuentes"].pop(0)

    def buscar_productos_interno(
        self,
        query: str,
        state: Optional[dict] = None,
        cliente_id: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Método interno para buscar productos."""
        logger.info("===================== INICIO BÚSQUEDA DE PRODUCTOS =====================")
        try:
            # Obtener embedding para la consulta
            query_embedding = self.embeddings.embed_query(query)
            
            # Normalizar y procesar la query
            query_normalized = self.normalizar_texto(query)
            query_words = query_normalized.split()
            
            # Obtener contexto del proyecto
            project_id = state.get("project").id if state and state.get("project") else None
            
            # Realizar búsqueda semántica
            rpc_payload = {
                "query_embedding": query_embedding,
                "match_count": limit * 2,
                "match_threshold": 0.75
            }
            
            if project_id:
                rpc_payload["filter_project_id"] = project_id
                
            results_data = self.web_tool.supabase.rpc(
                "match_products_v3",
                rpc_payload
            ).execute()
            
            # Procesar y filtrar resultados
            productos = []
            for item in results_data.data:
                score = self.calcular_relevancia(item, query_words)
                
                if score > 0:
                    producto = {
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                        "price": float(item.get("price", 0)) if item.get("price") is not None else 0,
                        "currency": item.get("currency", "CLP"),
                        "sku": item.get("sku", ""),
                        "category": item.get("category", ""),
                        "tags": item.get("tags", []),
                        "images": item.get("images", []),
                        "metadata": item.get("metadata", {}),
                        "source_url": item.get("source_url", ""),
                        "score": score,
                        "stock": item.get("metadata", {}).get("stock", 0),
                        "is_promotion": item.get("metadata", {}).get("is_promotion", False)
                    }
                    
                    # Aplicar filtros adicionales
                    if category and producto["category"] != category:
                        continue
                    if min_price is not None and producto["price"] < min_price:
                        continue
                    if max_price is not None and producto["price"] > max_price:
                        continue
                        
                    productos.append(producto)
            
            # Si no hay resultados con búsqueda semántica, intentar SQL directo
            if not productos:
                logger.info("No se encontraron resultados con búsqueda semántica, intentando SQL directo")
                productos = self.buscar_sql_directo(
                    query=query,
                    project_id=project_id,
                    category=category,
                    min_price=min_price,
                    max_price=max_price,
                    limit=limit
                )
            
            # Ordenar por relevancia
            productos.sort(key=lambda x: x["score"], reverse=True)
            productos = productos[:limit]
            
            # Actualizar preferencias si hay cliente_id
            if cliente_id:
                categoria = productos[0]["category"] if productos else None
                self.actualizar_preferencias(cliente_id, query, categoria)
            
            # Preparar respuesta
            response = {
                "status": "success",
                "total_results": len(productos),
                "products": productos,
                "message": f"Se encontraron {len(productos)} productos relacionados con la búsqueda."
            }
            
            logger.info("===================== FIN BÚSQUEDA DE PRODUCTOS =====================")
            return response
            
        except Exception as e:
            logger.error(f"Error en búsqueda de productos: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error en la búsqueda de productos: {str(e)}"
            )

    @tool("buscar_productos", return_direct=True)
    def buscar_productos(
        self,
        query: str,
        state: Annotated[dict, InjectedState],
        cliente_id: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Interfaz de tool para buscar productos."""
        return self.buscar_productos_interno(
            query=query,
            state=state,
            cliente_id=cliente_id,
            category=category,
            min_price=min_price,
            max_price=max_price,
            limit=limit
        )

    async def procesar_mensaje(self, mensaje: str, estado: dict) -> str:
        """Procesa un mensaje del usuario usando el agente."""
        try:
            resultado = await self.agent_executor.ainvoke({
                "input": mensaje,
                "state": estado
            })
            return resultado["output"]
        except Exception as e:
            logger.error(f"Error procesando mensaje: {str(e)}", exc_info=True)
            return "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo."

# Instancia global del agente
agente_producto = AgenteProducto() 