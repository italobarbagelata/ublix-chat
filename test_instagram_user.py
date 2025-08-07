#!/usr/bin/env python3
"""
Script de prueba para obtener información de usuario de Instagram
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Cargar variables de entorno
load_dotenv()

async def test_get_user_info():
    """Prueba la función get_instagram_user_info"""
    
    # Importar después de configurar el path
    from app.controler.webhook.instagram_webhook import get_instagram_user_info
    
    # Configuración de prueba - REEMPLAZA ESTOS VALORES
    test_user_id = input("Ingresa el ID de usuario de Instagram a probar: ").strip()
    test_project_id = input("Ingresa el project_id: ").strip()
    
    if not test_user_id or not test_project_id:
        print("❌ Debes proporcionar tanto el user_id como el project_id")
        return
    
    print(f"\n🔍 Obteniendo información del usuario: {test_user_id}")
    print(f"📁 Project ID: {test_project_id}")
    print("-" * 50)
    
    try:
        # Llamar a la función
        user_info = await get_instagram_user_info(
            user_id=test_user_id,
            project_id=test_project_id
        )
        
        # Mostrar resultados
        print("\n✅ Información obtenida exitosamente:")
        print("-" * 50)
        print(f"ID: {user_info.get('id', 'No disponible')}")
        print(f"Nombre: {user_info.get('name', 'No disponible')}")
        print(f"Username: {user_info.get('username', 'No disponible')}")
        
        # Si hay campos adicionales
        for key, value in user_info.items():
            if key not in ['id', 'name', 'username']:
                print(f"{key}: {value}")
                
    except Exception as e:
        print(f"\n❌ Error al obtener información del usuario: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 PRUEBA DE OBTENCIÓN DE USUARIO DE INSTAGRAM")
    print("=" * 50)
    
    # Verificar configuración
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("❌ Error: Variables de entorno SUPABASE_URL y SUPABASE_KEY no configuradas")
        sys.exit(1)
    
    # Ejecutar prueba
    asyncio.run(test_get_user_info())
    
    print("\n" + "=" * 50)
    print("✅ Prueba completada")
    print("=" * 50)