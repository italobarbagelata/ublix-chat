#!/usr/bin/env python3
"""
Script para verificar si hay productos en la base de datos
y diagnosticar problemas con la búsqueda
"""

import os
from supabase import create_client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar cliente de Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    print("Error: No se encontraron las credenciales de Supabase")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

print("=== DIAGNÓSTICO DE BÚSQUEDA DE PRODUCTOS ===\n")

# 1. Verificar cuántos productos hay en total
try:
    response = supabase.table('search_items').select('*').eq('type', 'product').execute()
    total_products = len(response.data) if response.data else 0
    print(f"✓ Total de productos en la BD: {total_products}")
    
    if total_products > 0:
        # Mostrar algunos ejemplos
        print("\nEjemplos de productos:")
        for i, product in enumerate(response.data[:3]):
            print(f"\n{i+1}. {product.get('title', 'Sin título')}")
            print(f"   - ID: {product.get('id')}")
            print(f"   - SKU: {product.get('sku', 'N/A')}")
            print(f"   - Precio: ${product.get('price', 0)}")
            print(f"   - Stock: {product.get('stock', 'N/A')}")
            print(f"   - Tiene embedding: {'Sí' if product.get('embedding') else 'No'}")
            
except Exception as e:
    print(f"✗ Error al consultar productos: {str(e)}")

# 2. Verificar productos para un proyecto específico
project_id = "ee315050-6e60-43ee-8f05-aaf9c097a1e9"  # Full Figure
print(f"\n=== PRODUCTOS DEL PROYECTO {project_id} ===")

try:
    response = supabase.table('search_items').select('*').eq('type', 'product').eq('project_id', project_id).execute()
    project_products = len(response.data) if response.data else 0
    print(f"✓ Productos del proyecto: {project_products}")
    
    if project_products > 0:
        # Contar productos con embeddings
        with_embeddings = sum(1 for p in response.data if p.get('embedding'))
        print(f"✓ Productos con embeddings: {with_embeddings}/{project_products}")
        
        # Buscar productos que contengan "colaless" o "calzón"
        colaless_products = []
        calzon_products = []
        
        for p in response.data:
            title = (p.get('title') or '').lower()
            desc = (p.get('description') or '').lower()
            combined = title + ' ' + desc
            
            if 'colaless' in combined:
                colaless_products.append(p)
            if 'calzón' in combined or 'calzon' in combined:
                calzon_products.append(p)
        
        print(f"\n✓ Productos con 'colaless': {len(colaless_products)}")
        print(f"✓ Productos con 'calzón': {len(calzon_products)}")
        
        if colaless_products:
            print("\nEjemplos de productos colaless:")
            for p in colaless_products[:3]:
                print(f"- {p.get('title')} (${p.get('price', 0)})")
                
except Exception as e:
    print(f"✗ Error al consultar productos del proyecto: {str(e)}")

# 3. Verificar la estructura de la columna stock
print("\n=== VERIFICACIÓN DE COLUMNA STOCK ===")
try:
    # Intentar consultar con el campo stock
    response = supabase.table('search_items').select('id,title,stock').eq('type', 'product').limit(1).execute()
    if response.data:
        print("✓ La columna 'stock' existe y es accesible")
        print(f"  Ejemplo: {response.data[0]}")
    else:
        print("? No se pudo verificar la columna stock (no hay productos)")
except Exception as e:
    if "column" in str(e).lower() and "stock" in str(e).lower():
        print("✗ La columna 'stock' NO existe en la tabla")
    else:
        print(f"✗ Error al verificar columna stock: {str(e)}")

print("\n=== FIN DEL DIAGNÓSTICO ===")