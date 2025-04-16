import logging
from langchain.tools import tool
from supabase.client import Client, create_client
from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langchain_openai import OpenAIEmbeddings
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
from typing import Optional, List, Dict, Any
import os
import re
import json
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class QueryTagConfig:
    """Configuración para un tag de consulta específico."""
    name: str
    patterns: List[str]
    match_count: int
    priority: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

# Configuración base de tags
TAG_CONFIGS = {
    "multi_result": QueryTagConfig(
        name="multi_result",
        patterns=[
            r'lista\s+de',
            r'catalogo',
            r'catálogo',
            r'inventario',
            r'todos\s+los',
            r'todas\s+las',
            r'cualquier',
            r'varios',
            r'múltiples',
            r'muéstrame\s+(?:todos|todas|las|los)',
            r'dame\s+(?:todos|todas|las|los)',
            r'dime\s+(?:todos|todas|las|los)',
            r'busca\s+(?:todos|todas|las|los)',
            r'encuentra\s+(?:todos|todas|las|los)',
            r'comparar',
            r'comparación',
            r'diferencias',
            r'opciones',
            r'alternativas',
            r'categorías',
            r'categorias',
            r'tipos\s+de',
            r'clases\s+de',
            r'ordenados?',
            r'ordenar\s+por',
            r'clasificados?',
            r'clasificar\s+por',
        ],
        match_count=25,
        priority=1,
        metadata={"requires_broad_search": True}
    ),
    "document": QueryTagConfig(
        name="document",
        patterns=[
            r'documento',
            r'documentos',
            r'(?:busca|encuentra|muéstrame|dame|dime)\s+(?:el|los|las)\s+(?:documento|documentos)',
            r'(?:quiero|necesito|busco|deseo)\s+(?:ver|consultar|revisar|leer)\s+(?:el|los|las)\s+(?:documento|documentos)',
            r'(?:dónde|dónde\s+está|dónde\s+están)\s+(?:el|los|las)\s+(?:documento|documentos)',
            r'(?:muéstrame|dame|dime)\s+(?:el|los|las)\s+(?:contenido|contenidos)\s+(?:del|de los|de las)\s+(?:documento|documentos)',
            r'(?:archivo|archivos|texto|textos)\s+(?:que|que\s+contengan|que\s+hablen\s+de)',
            r'(?:busca|encuentra)\s+(?:en|dentro\s+de)\s+(?:el|los|las)\s+(?:documento|documentos)',
            r'(?:qué|cuál|cuáles)\s+(?:documento|documentos)\s+(?:tienen|contienen|mencionan)',
            r'(?:mostrar|visualizar|ver)\s+(?:el|los|las)\s+(?:documento|documentos)',
            r'(?:información|datos|contenido)\s+(?:del|de los|de las)\s+(?:documento|documentos)',
        ],
        match_count=10,
        priority=2,
        metadata={"requires_document_search": True}
    ),
    "store_products": QueryTagConfig(
        name="store_products",
        patterns=[
            # Patrones existentes
            r'(?:precio|precios|valor|valores|costo|costos)\s+(?:de|del|de la|de las|del|de los)',
            r'(?:cuánto|cuántos|cuánta|cuántas)\s+(?:cuesta|cuestan|vale|valen)',
            r'(?:cuanto|cuantos|cuanta|cuantas)\s+(?:cuesta|cuestan|vale|valen)',
            
            # Nuevos patrones para preguntas específicas de precios
            r'(?:cuánto|cómo)\s+(?:cuesta|vale)\s+(?:el|la|los|las)\s+([a-zA-Záéíóúñ\s]+)',
            r'(?:cuánto|cómo)\s+(?:cuesta|vale)\s+([a-zA-Záéíóúñ\s]+)',
            r'(?:precio|valor|costo)\s+(?:de|del|de la|de las|del|de los)\s+([a-zA-Záéíóúñ\s]+)',
            
            # Patrones para búsqueda directa de productos
            r'^[a-zA-Záéíóúñ\s]+$',  # Cualquier palabra o frase
            r'^[a-zA-Záéíóúñ\s]+\s+[a-zA-Záéíóúñ\s]+$',  # Dos o más palabras
            
            # Resto de patrones existentes...
            r'(?:busca|encuentra|muéstrame|dame|dime)\s+(?:todos|todas)\s+(?:los|las)\s+(?:precios|valores|costos)',
            r'(?:producto|productos)\s+(?:que|que\s+tengan|que\s+ofrezcan)',
            r'(?:artículo|artículos|item|items)\s+(?:que|que\s+tengan|que\s+ofrezcan)',
            r'(?:mercancía|mercancías)\s+(?:que|que\s+tengan|que\s+ofrezcan)',
            r'(?:rango|rangos)\s+(?:de\s+precios|de\s+valores|de\s+costos)',
            r'(?:entre|desde|hasta)\s+\d+\s+(?:y|hasta)\s+\d+',
            r'(?:menos|más)\s+de\s+\d+',
            r'(?:aproximadamente|alrededor\s+de)\s+\d+',
            r'(?:oferta|ofertas|descuento|descuentos)',
            r'(?:rebaja|rebajas|promoción|promociones)',
            r'(?:liquidación|liquidaciones)',
            r'(?:disponible|disponibles)\s+(?:en|con)\s+(?:precio|precios)',
            r'(?:en\s+stock|en\s+existencia)\s+(?:con|a)',
            r'(?:que\s+tengan|que\s+tienen)\s+(?:precio|precios)',
            r'(?:que\s+cueste|que\s+cuesten)\s+(?:entre|desde|hasta)',
            r'(?:que\s+valga|que\s+valgan)\s+(?:entre|desde|hasta)',
            r'(?:que\s+tenga|que\s+tengan)\s+(?:un|una)\s+(?:precio|valor|costo)',
            r'(?:comparar|comparación)\s+(?:de\s+precios|de\s+valores|de\s+costos)',
            r'(?:más\s+barato|más\s+caro)\s+(?:que|que\s+el)',
            r'(?:menor|mayor)\s+(?:precio|valor|costo)',
            r'(?:económico|económicos|barato|baratos)',
            r'(?:caro|caros|lujo|lujosos)',
            r'(?:premium|premiums|exclusivo|exclusivos)',
            r'(?:temporada|temporadas)\s+(?:de\s+precios|de\s+ofertas)',
            r'(?:black\s+friday|cyber\s+monday)',
            r'(?:rebajas|liquidación)\s+(?:de|del|de la)',
            r'(?:tienes|tienen)\s+(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:hay)\s+(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:venden|vende)\s+(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:puedes\s+mostrarme|pueden\s+mostrarme)\s+(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:quiero\s+comprar|quisiera\s+comprar)\s+(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:disponible|disponibles)\s+(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:cuánto\s+vale|cuánto\s+valen)\s+(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:precio\s+de|precios\s+de)\s+(?:[a-zA-Záéíóúñ\s]+)',
        ],
        match_count=25,
        priority=1,
        metadata={"requires_broad_search": True}
    ),
    "delivery": QueryTagConfig(
        name="delivery",
        patterns=[
            r'(?:entrega|envío|recogida|retiro|despacho)\s+(?:a|en)',
            r'(?:dónde|cuándo|cómo)\s+(?:puedo)?\s*(?:recibir|obtener|retirar|entregar)',
            r'(?:tiempo|duración)\s+de\s+(?:entrega|envío|despacho)',
            r'(?:costo|precio)\s+de\s+(?:envío|entrega|despacho)',
            r'(?:hacen|realizan|tienen)\s+(?:envíos|despachos|entregas)',
            r'(?:cuánto|qué)\s+(?:vale|cuesta)\s+(?:el)?\s*(?:envío|despacho|entrega)',
            r'(?:envían|despachan)\s+(?:a|hasta)\s+[\w\s]+',
            r'(?:cuál)\s+(?:es)?\s+el\s+(?:costo|precio)\s+(?:del)?\s*(?:envío|despacho|entrega)',
        ],
        match_count=5,
        priority=2,
        metadata={"requires_location_context": True}
    ),
    "faq": QueryTagConfig(
        name="faq",
        patterns=[
            r'(?:preguntas|consultas)\s+(?:frecuentes|comunes)',
            r'(?:tienen|cuentan con)\s+(?:una)?\s*(?:lista|sección)\s+de\s+(?:preguntas frecuentes|faq)',
            r'(?:dudas|inquietudes)\s+comunes',
        ],
        match_count=5,
        priority=2,
        metadata={"requires_exact_match": True}
    ),
    "payment": QueryTagConfig(
        name="payment",
        patterns=[
            r'(?:puedo|se puede|es posible)\s+(?:pagar|hacer el pago|realizar el pago)',
            r'(?:aceptan|reciben|toman)\s+(?:tarjeta|efectivo|transferencia|paypal|mercado pago)',
            r'(?:métodos|formas|opciones)\s+de\s+pago',
            r'(?:cómo|de qué forma)\s+(?:puedo)?\s*(?:pagar|realizar el pago)',
        ],
        match_count=3,
        priority=3,
        metadata={"requires_payment_info": True}
    ),
    "laundry": QueryTagConfig(
        name="laundry",
        patterns=[
            # Patrones relacionados con precios
            r'(?:precio|precios)\s+(?:de|del|de la|de las|del|de los)?\s*(?:[a-zA-Záéíóúñ\s]+)',
            r'(?:cuánto|cómo)\s+(?:cuesta|vale)\s+(?:lavar|limpiar)',
            r'(?:precio|precios)\s+(?:de|del|de la|de las|del|de los)\s+(?:lavado|limpieza|servicio)',
            r'(?:precio|precios)\s+(?:por|de)\s+(?:lavar|limpiar)',
            r'(?:tarifa|tarifas)\s+(?:de|del|de la|de las|del|de los)',
            r'(?:costo|costos)\s+(?:por|de)\s+(?:lavar|limpiar)',
            r'(?:valor|valores)\s+(?:por|de)\s+(?:lavar|limpiar)',
            
            # Patrones para lavar prendas
            r'(?:quiero|necesito|busco|deseo)\s+(?:lavar|limpieza|servicio)\s+(?:mi|mis|un|una|unos|unas)',
            r'(?:quiero|necesito|busco|deseo)\s+(?:servicio|lavado|limpieza)',
            r'(?:lavado|limpieza|servicio)\s+(?:de|del|de la|de las|del|de los)',
            r'(?:lavar|limpiar)\s+(?:varias|varios|muchos|muchas)\s+(?:prendas|artículos|cosas)',
            r'(?:lavar|limpiar)\s+(?:más de|varios|muchos)\s+(?:[a-zA-Záéíóúñ\s]+)',
            
            # Tipos de prendas, solo cuando se refiere a lavar varias
            r'(?:lavar|limpiar)\s+(?:ropa|prendas|vestimenta)',
            r'(?:lavar|limpiar)\s+(?:almohada|almohadas|cama|colchón|colchones|cortina|cortinas|edredón|edredones)',
            r'(?:lavar|limpiar)\s+(?:sábana|sábanas|toalla|toallas|manta|mantas|cobija|cobijas)',
            r'(?:lavar|limpiar)\s+(?:vestido|vestidos|pantalón|pantalones|camisa|camisas|blusa|blusas)',
            r'(?:lavar|limpiar)\s+(?:chaqueta|chaquetas|abrigo|abrigos|suéter|suéteres|jersey|jerseys)',
            
            # Múltiples precios o múltiples prendas (conceptos de cantidad)
            r'(?:todos|todas)\s+(?:los|las)\s+(?:precios|tarifas|costos)',
            r'(?:varias|varios|muchas|muchos)\s+(?:prendas|artículos|ítems)',
            r'(?:precios|tarifas|costos)\s+(?:de|para)\s+(?:diferentes|distintos|varios)',
            r'(?:más)\s+(?:prendas|artículos|ítems)',
        ],
        match_count=3,
        priority=1,
        metadata={
            "requires_service_info": True,
            "requires_broad_search": True,
            "show_all_prices": True
        }
    )
}

def get_project_patterns(project: dict) -> List[QueryTagConfig]:
    try:
        if not project:
            logger.warning("No se encontró el proyecto en el estado")
            return []

        enabled_patterns = project.retriever_patterns.get('enabled_patterns', [])
        disabled_patterns = project.retriever_patterns.get('disabled_patterns', [])
        custom_patterns = project.retriever_patterns.get('custom_patterns', [])

        logger.info("***** CONFIGURACIÓN DE PATRONES DEL PROYECTO *****")
        logger.info(f"***** Patrones habilitados: {enabled_patterns}")
        logger.info(f"***** Patrones deshabilitados: {disabled_patterns}")
        logger.info(f"***** Patrones personalizados: {custom_patterns}")

        active_configs = []

        # Agregar configuraciones habilitadas
        for pattern_type in enabled_patterns:
            if pattern_type in TAG_CONFIGS:
                logger.info(f"***** Agregando configuración de tipo: {pattern_type}")
                active_configs.append(TAG_CONFIGS[pattern_type])

        # Remover configuraciones deshabilitadas
        for pattern_type in disabled_patterns:
            if pattern_type in TAG_CONFIGS:
                logger.info(f"***** Removiendo configuración de tipo: {pattern_type}")
                active_configs = [c for c in active_configs if c.name != pattern_type]

        # Agregar configuración personalizada si existe
        if custom_patterns:
            logger.info("***** Agregando configuración personalizada")
            custom_config = QueryTagConfig(
                name="custom",
                patterns=custom_patterns,
                match_count=3,  # Valor por defecto para patrones personalizados
                priority=4,  # Prioridad más baja para patrones personalizados
                metadata={"is_custom": True}
            )
            active_configs.append(custom_config)

        logger.info(f"***** Configuraciones activas finales: {[c.name for c in active_configs]}")
        logger.info("***** FIN CONFIGURACIÓN DE PATRONES *****")

        return active_configs

    except Exception as e:
        logger.error(f"Error al obtener patrones del proyecto: {str(e)}")
        return []

def detect_query_tags(query: str, enabled_pattern_types: List[str]) -> List[QueryTagConfig]:
    """
    Detecta los tags (intenciones) en una consulta basándose en los patrones habilitados.
    
    Args:
        query: La consulta del usuario
        enabled_pattern_types: Lista de tipos de patrones habilitados
        
    Returns:
        Lista de configuraciones de tags detectados, ordenados por prioridad
    """
    detected_configs = []
    query_lower = query.lower()
    
    # Obtener todas las configuraciones activas
    active_configs = [TAG_CONFIGS[tag] for tag in enabled_pattern_types if tag in TAG_CONFIGS]
    
    # Detectar coincidencias para cada configuración
    for config in active_configs:
        logger.info(f"Evaluando patrones para tag: {config.name}")
        for pattern in config.patterns:
            match = re.search(pattern, query_lower)
            if match:
                logger.info(f"Patrón encontrado para {config.name}: {pattern}")
                logger.info(f"Coincidencia: {match.group(0)}")
                detected_configs.append(config)
                break
    
    # Ordenar por prioridad (menor número = mayor prioridad)
    detected_configs.sort(key=lambda x: x.priority)
    
    logger.info(f"Tags detectados: {[c.name for c in detected_configs]}")
    return detected_configs

@tool(parse_docstring=False)
def retriever(query: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Herramienta para buscar información relevante en la base de conocimiento usando búsqueda semántica.
    
    Esta herramienta:
    1. Detecta la intención de la consulta usando patrones predefinidos
    2. Ajusta dinámicamente el número de resultados según el tipo de consulta
    3. Realiza una búsqueda de similitud semántica en la base de conocimiento
    4. Procesa y formatea los resultados para su presentación
    
    Args:
        query (str): La consulta del usuario
        state (dict): Estado del sistema que incluye la configuración del proyecto
        
    Returns:
        str: Contenido relevante encontrado, formateado y combinado
        
    Raises:
        ValueError: Si no se encuentra el proyecto o las credenciales de Supabase
    """
    try:
        logger.info(f"=== INICIO DE RETRIEVER ===")
        logger.info(f"Query recibida: {query}")

        project = state.get("project")
        if not project:
            logger.error("No se encontró el proyecto en el estado")
            raise ValueError("Project not found in state")

        logger.info(f"Proyecto encontrado: {project.id}")

        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            logger.error("No se encontraron las credenciales de Supabase en las variables de entorno")
            raise ValueError("Supabase credentials not found in environment variables")

        supabase_client = create_client(supabase_url, supabase_key)

        logger.info("Cliente de Supabase inicializado correctamente")
        logger.info("Inicializando embeddings de OpenAI")
        embeddings = OpenAIEmbeddings()

        # Obtener configuraciones de patrones del proyecto
        project_patterns = get_project_patterns(project)
        
        # Detectar tags en la consulta
        enabled_pattern_types = project.retriever_patterns.get('enabled_patterns', [])
        detected_tags = detect_query_tags(query, enabled_pattern_types)
        
        if not detected_tags:
            logger.info("No se detectaron tags específicos - Usando configuración por defecto")
            match_count = 1
        else:
            # Usar el match_count del tag con mayor prioridad
            highest_priority_tag = detected_tags[0]
            match_count = highest_priority_tag.match_count
            logger.info(f"Tag detectado con mayor prioridad: {highest_priority_tag.name}")
            logger.info(f"Usando match_count: {match_count}")
            
            # Loggear metadata relevante
            for tag in detected_tags:
                logger.info(f"Metadata para tag {tag.name}: {tag.metadata}")

        logger.info("***************************")
        logger.info(f"Realizando búsqueda de similitud para query: {query}")
        logger.info(f"Número de resultados a buscar: {match_count}")
        logger.info(f"Project ID: {project}")
        logger.info("***************************")

        response = supabase_client.rpc(
            'match_documents_cosine_v2',
            {
                'query_embedding': embeddings.embed_query(query),
                'match_count': match_count,
                'project': project.id
            }
        ).execute()
        
        
        # Si no hay resultados, hacer una búsqueda textual directa:
        if not response.data:
            logger.info("Usando búsqueda textual por falta de resultados semánticos.")
            # Mejorar la búsqueda textual para incluir más campos
            textual_response = supabase_client.table('documents') \
                .select("*") \
                .or_(f"title.ilike.%{query}%,content.ilike.%{query}%,description.ilike.%{query}%") \
                .limit(match_count).execute()
            
            response.data = textual_response.data

        logger.info(f"Respuesta recibida de Supabase. Número de documentos encontrados: {len(response.data) if response.data else 0}")

        if not response.data:
            logger.warning("No se encontraron documentos relevantes para la query")
            return "No se encontró información relevante."

        all_content = []
        seen_content = set()

        logger.info(f"Procesando {len(response.data)} documentos")
        
        # Agregar log de diagnóstico para ver los primeros documentos
        logger.info("Primeros 3 documentos encontrados:")
        for i, doc in enumerate(response.data[:3]):
            logger.info(f"Documento {i+1}: {json.dumps(doc, ensure_ascii=False, indent=2)}")
        
        for doc in response.data:
            content_parts = []

            # Verificar cada campo y agregar solo si tiene contenido
            for field in ['content', 'title', 'description', 'question', 'answer', 'metadata']:
                value = doc.get(field)
                if value and str(value).strip():
                    content_parts.append(f"{field.capitalize()}: {value}")

            if not content_parts:
                continue

            formatted_content = "\n".join(content_parts)

            if formatted_content not in seen_content:
                all_content.append(formatted_content)
                seen_content.add(formatted_content)

        if not all_content:
            return "No se encontró contenido relevante."

        combined_content = "\n\n---\n\n".join(all_content)
        logger.info(f"Se recuperaron {len(all_content)} documentos únicos")

        if not combined_content.strip():
            return "No se encontró contenido relevante."

        return combined_content

    except Exception as e:
        logger.error(f"Error en retriever tool: {str(e)}")
        return f"Error al buscar información: {str(e)}"