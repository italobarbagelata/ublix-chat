import logging
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
import unicodedata
from app.resources.postgresql import SupabaseDatabase
# Configurar el logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicializar las dependencias
embeddings = OpenAIEmbeddings()
db = SupabaseDatabase()
vector_store = SupabaseVectorStore(
    client=db.supabase,
    embedding=embeddings,
    table_name="products",
    query_name="match_products_v3"
)

@tool("search_products", return_direct=True)
def search_products(
    query: str,
    state: Annotated[dict, InjectedState],
    limit: int = 3
) -> Dict[str, Any]:
    """Busca productos en la base de datos usando búsqueda semántica y filtros.

    Use esta herramienta cuando necesite buscar productos específicos. Puede buscar por texto y aplicar filtros.

    Args:
        query: El texto para buscar productos (ej: "zapatos deportivos nike")
        project_id: (Opcional) ID del proyecto para filtrar resultados
        category: (Opcional) Categoría específica (ej: "calzado", "ropa", "electrónica")
        min_price: (Opcional) Precio mínimo en CLP (ej: 10000)
        max_price: (Opcional) Precio máximo en CLP (ej: 50000)
        limit: (Opcional) Número máximo de resultados (default: 10)

    Ejemplos de uso:
        - "Busca productos de nike"
        - "Encuentra zapatos deportivos entre 20000 y 50000 pesos"
        - "Muestra productos de la categoría electrónica"
        - "Busca los últimos 5 productos agregados"
    """
    logger.info("===================== INICIO AGENTE BÚSQUEDA DE PRODUCTOS =====================")
    try:
        logger.info(f"Iniciando búsqueda de productos con query: {query}")
        
        # ================================ EMBEDDING ================================
        # Obtener embedding para la consulta
        query_embedding = embeddings.embed_query(query)
        
        # ================================ PROJECT ================================
        project_state = state.get("project")
        
        
        # ================================ MATCH PRODUCTS ================================
        # Realizar búsqueda directa usando match_products
        try:
            logger.info(f"Usando match_products con project_id: {project_state.id}")
            
            # Ejecutar la función match_products directamente
            rpc_payload = {
                "query_embedding": query_embedding,
                "match_count": limit,
                "match_threshold": 0.85  # Aumentar el umbral de similitud
            }
            
            # Solo agregar project_id si está presente
            if project_state.id:
                rpc_payload["filter_project_id"] = project_state.id
                
            results_data = db.supabase.rpc(
                "match_products_v3",  # Usar la función correcta
                rpc_payload
            ).execute()
            
            # Verificar si hay resultados
            raw_products = results_data.data
            logger.info(f"Resultados obtenidos directamente: {(raw_products)}")
            
            # Si hay resultados de match_products, procesarlos
            if raw_products:
                from langchain_core.documents import Document
                results = []
                
                for item in raw_products:
                    # Añadir la puntuación de similitud a la metadata
                    similarity_score = item.pop('similarity', 0)
                    
                    # Bajar el umbral de similitud a 0.75 para ser más flexible
                    if similarity_score >= 0.7:  # Ajustar al mismo umbral que la función SQL
                        item['score'] = similarity_score
                        
                        # Crear documento con el mismo formato que usamos para embeddings
                        title = item.get("title", "") or ""
                        description = item.get("description", "") or ""
                        category = item.get("category", "") or ""
                        tags = item.get("tags", []) or []
                        
                        # Crear contenido normalizado como en web_scraping.py
                        content = f"""
                        {title}
                        {description}
                        {category}
                        {' '.join(tags)}
                        """
                        
                        # Normalizar el texto como en web_scraping.py
                        content = ''.join(c for c in unicodedata.normalize('NFD', content.lower())
                                       if unicodedata.category(c) != 'Mn')
                        
                        doc = Document(
                            page_content=content.strip(), 
                            metadata=item
                        )
                        results.append(doc)
                    
                logger.info(f"Resultados obtenidos: {len(results)}")
            else:
                results = []
        except Exception as e:
            logger.error(f"Error usando match_products: {str(e)}")
            results = []
            
            
            
        # ================================ SQL DIRECTO ================================
        # Si no hay resultados con match_products, intentar búsqueda SQL directa
        if not results:
            logger.info("No se encontraron resultados con match_products, intentando SQL directo")
            try:
                # Consulta SQL directa con múltiples condiciones mejorada
                query_text = f"%{query}%"
                # Convertir la query a minúsculas para búsqueda case-insensitive
                query_lower = query.lower()
                
                # Normalizar acentos en la query
                query_normalized = ''.join(c for c in unicodedata.normalize('NFD', query_lower)
                                        if unicodedata.category(c) != 'Mn')
                
                # Dividir la query en palabras para búsqueda más flexible
                query_words = query_normalized.split()
                
                # Construir condiciones de búsqueda más flexibles
                conditions = []
                for word in query_words:
                    if len(word) > 2:  # Solo buscar palabras de más de 2 caracteres
                        conditions.append(f"title.ilike.%{word}%")
                        conditions.append(f"description.ilike.%{word}%")
                        conditions.append(f"category.ilike.%{word}%")
                
                # Unir todas las condiciones con OR
                if conditions:
                    sql_query = db.supabase.table("products").select(
                        "id,title,description,price,currency,sku,category,tags,images,metadata,source_url,created_at,project_id"
                    ).or_(",".join(conditions))
                else:
                    # Si no hay palabras válidas, usar la búsqueda original
                    sql_query = db.supabase.table("products").select(
                        "id,title,description,price,currency,sku,category,tags,images,metadata,source_url,created_at,project_id"
                    ).or_(
                        f"title.ilike.{query_text},description.ilike.{query_text},category.ilike.{query_text}"
                    )
                
                # Aplicar filtro de project_id si está presente
                if project_state.id:
                    sql_query = sql_query.eq("project_id", project_state.id)
                
                # Ejecutar la consulta con un límite mayor para tener más opciones
                data = sql_query.limit(limit * 2).execute()
                
                # Convertir resultados a formato esperado si hay datos
                if data.data:
                    logger.info(f"Encontrados {len(data.data)} productos mediante SQL directo")
                    from langchain_core.documents import Document
                    
                    # Calcular relevancia para cada resultado
                    for item in data.data:
                        # Convertir a minúsculas con validación de None y normalizar acentos
                        title = ''.join(c for c in unicodedata.normalize('NFD', (item.get("title", "") or "").lower())
                                     if unicodedata.category(c) != 'Mn')
                        description = ''.join(c for c in unicodedata.normalize('NFD', (item.get("description", "") or "").lower())
                                           if unicodedata.category(c) != 'Mn')
                        category = ''.join(c for c in unicodedata.normalize('NFD', (item.get("category", "") or "").lower())
                                        if unicodedata.category(c) != 'Mn')
                        
                        # Calcular puntuación de relevancia
                        score = 0
                        for word in query_words:
                            if word in title:
                                score += 1.0
                            if word in description:
                                score += 0.5
                            if word in category:
                                score += 0.8
                        
                        # Solo incluir resultados con alguna relevancia
                        if score > 0:
                            item['score'] = score
                            doc = Document(
                                page_content=f"{item.get('title', '')} {item.get('description', '')}".strip(),
                                metadata=item
                            )
                            results.append(doc)
                    
                    # Ordenar por relevancia y tomar los mejores resultados
                    results.sort(key=lambda x: x.metadata.get('score', 0), reverse=True)
                    results = results[:limit]
            except Exception as e:
                logger.error(f"Error en búsqueda SQL: {str(e)}")
        
        # ================================ FORMATEAR RESULTADOS ================================
        # Formatear resultados
        products = []
        for doc in results:
            # No incluir page_content (que podría contener HTML) en la respuesta
            product = {
                "id": doc.metadata.get("id", ""),
                "title": doc.metadata.get("title", ""),
                "description": doc.metadata.get("description", ""),
                # El campo "content" se excluye completamente
                "price": float(doc.metadata.get("price", 0)) if doc.metadata.get("price") is not None else 0,
                "currency": doc.metadata.get("currency", "CLP"),
                "sku": doc.metadata.get("sku", ""),
                "category": doc.metadata.get("category", ""),
                "tags": doc.metadata.get("tags", []),
                "images": doc.metadata.get("images", []),
                "metadata": doc.metadata.get("metadata", {}),
                "source_url": doc.metadata.get("source_url", doc.metadata.get("original_url", "")),
                "created_at": doc.metadata.get("created_at", ""),
                "project_id": doc.metadata.get("project_id", ""),
                "score": doc.metadata.get("score", 0)
            }
            products.append(product)
        
        logger.info(f"Total de productos encontrados: {len(products)}")
        
        # ================================ RESPUESTA ================================
        # Siempre devolver los productos encontrados
        response = {
            "status": "success",
            "total_results": len(products),
            "products": products,
            "message": f"Se encontraron {len(products)} productos relacionados con la búsqueda."
        }
        
        logger.info(f"Respuesta de búsqueda de productos: {response}")
        
        logger.info("===================== FIN AGENTE BÚSQUEDA DE PRODUCTOS =====================")
        return response
        
    except Exception as e:
        logger.error(f"Error en search_products: {str(e)}", exc_info=True)
        logger.info("===================== FIN AGENTE BÚSQUEDA DE PRODUCTOS (CON ERROR) =====================")
        raise HTTPException(
            status_code=500,
            detail=f"Error buscando productos: {str(e)}"
        ) 