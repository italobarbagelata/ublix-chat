#!/usr/bin/env python3
"""
Script para probar la función RPC de búsqueda
"""

import os
from supabase import create_client
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

# Cargar variables de entorno
load_dotenv()

# Configurar cliente de Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    print("Error: No se encontraron las credenciales de Supabase")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

print("=== PRUEBA DE FUNCIÓN RPC search_all_content_unified ===\n")

# Inicializar embeddings
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    dimensions=384
)

# Generar embedding para la consulta
query = "colaless negros talla m"
print(f"Generando embedding para: '{query}'")
query_embedding = embeddings.embed_query(query)
print(f"✓ Embedding generado (dimensiones: {len(query_embedding)})")

# Parámetros RPC
project_id = "ee315050-6e60-43ee-8f05-aaf9c097a1e9"
rpc_params = {
    'query_embedding': query_embedding,
    'query_text': query,
    'project_id_filter': project_id,
    'content_types': ['product'],
    'match_count': 15,
    'similarity_threshold': 0.3,
    'category_filter': None,
    'min_price': None,
    'max_price': None
}

print(f"\nEjecutando RPC con:")
print(f"- Project ID: {project_id}")
print(f"- Query: {query}")
print(f"- Similarity threshold: 0.3")

try:
    # Ejecutar la función RPC
    response = supabase.rpc('search_all_content_unified', rpc_params).execute()
    
    if response.data:
        print(f"\n✓ Resultados encontrados: {len(response.data)}")
        print("\nPrimeros 5 resultados:")
        for i, item in enumerate(response.data[:5]):
            print(f"\n{i+1}. {item.get('title', 'Sin título')}")
            print(f"   - Tipo: {item.get('type')}")
            print(f"   - Precio: ${item.get('price', 0)}")
            print(f"   - Similitud: {item.get('similarity', 0):.2%}")
            print(f"   - Stock: {item.get('stock', 'N/A')}")
    else:
        print("\n✗ No se encontraron resultados")
        
except Exception as e:
    print(f"\n✗ Error al ejecutar RPC: {str(e)}")

# Probar búsqueda por texto puro (sin embedding)
print("\n\n=== BÚSQUEDA DIRECTA POR TEXTO ===")
try:
    response = supabase.table('search_items').select('*').eq('type', 'product').eq('project_id', project_id).ilike('title', '%colaless%').execute()
    
    if response.data:
        print(f"✓ Productos con 'colaless' en el título: {len(response.data)}")
        for item in response.data[:3]:
            print(f"- {item.get('title')} (${item.get('price', 0)})")
    else:
        print("✗ No se encontraron productos con 'colaless'")
        
except Exception as e:
    print(f"✗ Error en búsqueda directa: {str(e)}")