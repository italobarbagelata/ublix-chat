#!/usr/bin/env python3
"""
Script de prueba directa de la API de Instagram
"""
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_instagram_api():
    """Prueba directa de la API de Instagram Graph"""
    
    # Solicitar datos de prueba
    print("🔧 Prueba directa de Instagram Graph API")
    print("-" * 50)
    
    user_id = input("ID de usuario de Instagram: ").strip()
    access_token = input("Access Token de Instagram: ").strip()
    
    if not user_id or not access_token:
        print("❌ Se requieren ambos valores")
        return
    
    # URL de la API
    api_version = "v23.0"
    base_url = f"https://graph.instagram.com/{api_version}"
    
    # Campos a solicitar
    fields = "id,username,name"
    
    # Construir URL completa
    url = f"{base_url}/{user_id}?fields={fields}&access_token={access_token}"
    
    print(f"\n📡 Llamando a: {base_url}/{user_id}")
    print(f"📋 Campos solicitados: {fields}")
    print("-" * 50)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            
            print(f"📊 Estado de respuesta: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ Datos obtenidos exitosamente:")
                print("-" * 30)
                for key, value in data.items():
                    print(f"  {key}: {value}")
            else:
                print(f"\n❌ Error en la respuesta:")
                print(f"  Código: {response.status_code}")
                print(f"  Respuesta: {response.text}")
                
                # Intentar parsear error
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        print(f"\n  Mensaje de error: {error_data['error'].get('message', 'Sin mensaje')}")
                        print(f"  Tipo de error: {error_data['error'].get('type', 'Sin tipo')}")
                        print(f"  Código de error: {error_data['error'].get('code', 'Sin código')}")
                except:
                    pass
                    
    except Exception as e:
        print(f"\n❌ Error en la conexión: {str(e)}")

async def test_me_endpoint():
    """Prueba el endpoint /me para obtener información del propietario del token"""
    
    print("\n🔧 Prueba del endpoint /me")
    print("-" * 50)
    
    access_token = input("Access Token de Instagram: ").strip()
    
    if not access_token:
        print("❌ Se requiere el access token")
        return
    
    api_version = "v23.0"
    url = f"https://graph.instagram.com/{api_version}/me?fields=id,username,name,account_type&access_token={access_token}"
    
    print(f"\n📡 Llamando a: /me")
    print("-" * 50)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            
            print(f"📊 Estado de respuesta: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ Información del propietario del token:")
                print("-" * 30)
                for key, value in data.items():
                    print(f"  {key}: {value}")
            else:
                print(f"\n❌ Error: {response.status_code}")
                print(f"  Respuesta: {response.text}")
                
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

async def main():
    print("=" * 50)
    print("🧪 PRUEBA DIRECTA DE API DE INSTAGRAM")
    print("=" * 50)
    
    print("\nSelecciona una opción:")
    print("1. Probar obtener información de un usuario específico")
    print("2. Probar endpoint /me (información del token)")
    print("3. Probar ambos")
    
    opcion = input("\nOpción (1-3): ").strip()
    
    if opcion == "1":
        await test_instagram_api()
    elif opcion == "2":
        await test_me_endpoint()
    elif opcion == "3":
        await test_instagram_api()
        await test_me_endpoint()
    else:
        print("❌ Opción inválida")

if __name__ == "__main__":
    asyncio.run(main())