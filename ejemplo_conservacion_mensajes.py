#!/usr/bin/env python3
"""
📬 Ejemplo de Uso: Sistema de Conservación de Mensajes
==================================================

Este script demuestra cómo funciona el nuevo sistema de conservación de mensajes
en el bot de chat API REST.

Funcionalidades demostradas:
- Envío de mensajes múltiples
- Conservación automática de mensajes adicionales
- Consulta de contexto acumulado
- Procesamiento unificado con contexto
- Gestión de contexto acumulado
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class ChatConservationExample:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def send_message(self, message: str, user_id: str, project_id: str) -> Dict[str, Any]:
        """Envía un mensaje al chat"""
        url = f"{self.base_url}/api/chat/message"
        data = {
            "message": message,
            "user_id": user_id,
            "project_id": project_id,
            "name": "Usuario de Ejemplo"
        }
        
        async with self.session.post(url, json=data) as response:
            return {
                "status_code": response.status,
                "data": await response.json(),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_accumulated_context(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Consulta el contexto acumulado"""
        url = f"{self.base_url}/api/chat/context/accumulated"
        params = {"user_id": user_id, "project_id": project_id}
        
        async with self.session.get(url, params=params) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }
    
    async def clear_accumulated_context(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Limpia el contexto acumulado"""
        url = f"{self.base_url}/api/chat/context/clear"
        data = {"user_id": user_id, "project_id": project_id}
        
        async with self.session.post(url, json=data) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }
    
    def print_response(self, response: Dict[str, Any], message_label: str):
        """Imprime una respuesta de manera formateada"""
        print(f"\n{message_label}")
        print(f"Timestamp: {response.get('timestamp', 'N/A')}")
        print(f"Status Code: {response['status_code']}")
        
        data = response.get('data', {})
        if data.get('queued_message'):
            print("🔄 MENSAJE CONSERVADO EN CONTEXTO")
            print(f"📬 Respuesta: {data.get('response', 'N/A')}")
        elif response['status_code'] == 429:
            print("⚠️ RATE LIMITED (comportamiento anterior)")
            print(f"⏳ Respuesta: {data.get('response', 'N/A')}")
        else:
            print("✅ PROCESANDO MENSAJE")
            print(f"🤖 Respuesta: {data.get('response', 'N/A')}")
    
    async def demo_basic_conservation(self):
        """
        Demostración básica de conservación de mensajes
        """
        print("🚀 DEMOSTRACIÓN BÁSICA DE CONSERVACIÓN")
        print("=" * 50)
        
        # Configuración
        user_id = f"demo_user_{int(time.time())}"
        project_id = "demo_project"
        
        # Mensaje principal
        print("1️⃣ Enviando mensaje principal...")
        response1 = await self.send_message(
            "Hola, necesito información sobre sus servicios",
            user_id,
            project_id
        )
        self.print_response(response1, "MENSAJE PRINCIPAL")
        
        # Mensajes adicionales rápidos
        print("\n2️⃣ Enviando mensajes adicionales mientras se procesa el primero...")
        
        additional_messages = [
            "También quiero saber precios",
            "¿Tienen descuentos para estudiantes?",
            "Me interesa el plan premium",
            "¿Cuándo pueden empezar?"
        ]
        
        additional_responses = []
        for i, msg in enumerate(additional_messages, 1):
            response = await self.send_message(msg, user_id, project_id)
            self.print_response(response, f"MENSAJE ADICIONAL {i}")
            additional_responses.append(response)
            
            # Pequeña pausa para simular escritura humana
            await asyncio.sleep(0.5)
        
        # Consultar contexto acumulado
        print("\n3️⃣ Consultando contexto acumulado...")
        context_response = await self.get_accumulated_context(user_id, project_id)
        
        if context_response['status_code'] == 200:
            context_data = context_response['data']
            print(f"📊 Mensajes en contexto: {context_data['message_count']}")
            print("📝 Mensajes conservados:")
            
            for i, msg in enumerate(context_data['accumulated_messages'], 1):
                timestamp = msg['timestamp']
                content = msg['message']
                print(f"   {i}. [{timestamp}] {content}")
        else:
            print(f"❌ Error consultando contexto: {context_response['status_code']}")
        
        return {
            "user_id": user_id,
            "project_id": project_id,
            "messages_sent": len(additional_messages) + 1,
            "messages_conserved": len([r for r in additional_responses if r['data'].get('queued_message')])
        }
    
    async def demo_context_processing(self):
        """
        Demostración del procesamiento con contexto acumulado
        """
        print("\n🧠 DEMOSTRACIÓN DE PROCESAMIENTO CON CONTEXTO")
        print("=" * 50)
        
        # Configuración
        user_id = f"demo_context_{int(time.time())}"
        project_id = "demo_project"
        
        # Crear contexto
        print("1️⃣ Creando contexto acumulado...")
        await self.send_message("Consulta principal", user_id, project_id)
        
        messages_to_conserve = [
            "Información adicional 1",
            "Información adicional 2",
            "Información adicional 3"
        ]
        
        for msg in messages_to_conserve:
            await self.send_message(msg, user_id, project_id)
        
        # Consultar contexto antes
        print("\n2️⃣ Contexto antes del procesamiento...")
        context_before = await self.get_accumulated_context(user_id, project_id)
        
        if context_before['status_code'] == 200:
            count = context_before['data']['message_count']
            print(f"📊 Mensajes en contexto: {count}")
        
        # Esperar procesamiento
        print("\n3️⃣ Esperando procesamiento completo...")
        print("⏳ Simulando espera (15 segundos)...")
        await asyncio.sleep(15)
        
        # Consultar contexto después
        print("\n4️⃣ Contexto después del procesamiento...")
        context_after = await self.get_accumulated_context(user_id, project_id)
        
        if context_after['status_code'] == 200:
            count = context_after['data']['message_count']
            print(f"📊 Mensajes restantes: {count}")
            
            if count == 0:
                print("✅ El contexto se procesó y limpió correctamente")
            else:
                print("⚠️ Algunos mensajes permanecen en contexto")
        
        return {
            "context_processed": context_after['data']['message_count'] == 0 if context_after['status_code'] == 200 else False
        }
    
    async def demo_context_management(self):
        """
        Demostración de gestión manual del contexto
        """
        print("\n🛠️ DEMOSTRACIÓN DE GESTIÓN DE CONTEXTO")
        print("=" * 50)
        
        # Configuración
        user_id = f"demo_mgmt_{int(time.time())}"
        project_id = "demo_project"
        
        # Crear contexto
        print("1️⃣ Creando contexto acumulado...")
        await self.send_message("Consulta principal", user_id, project_id)
        
        for i in range(3):
            await self.send_message(f"Mensaje adicional {i+1}", user_id, project_id)
        
        # Consultar contexto
        print("\n2️⃣ Consultando contexto...")
        context_response = await self.get_accumulated_context(user_id, project_id)
        
        if context_response['status_code'] == 200:
            data = context_response['data']
            print(f"📊 Mensajes encontrados: {data['message_count']}")
            print(f"📝 Tiene mensajes pendientes: {data['has_pending_messages']}")
            
            print("\n📋 Detalle de mensajes:")
            for i, msg in enumerate(data['accumulated_messages'], 1):
                print(f"   {i}. [{msg['timestamp']}] {msg['message']}")
        
        # Limpiar contexto manualmente
        print("\n3️⃣ Limpiando contexto manualmente...")
        clear_response = await self.clear_accumulated_context(user_id, project_id)
        
        if clear_response['status_code'] == 200:
            cleared = clear_response['data']['messages_cleared']
            print(f"✅ Contexto limpiado: {cleared} mensajes eliminados")
        
        # Verificar limpieza
        print("\n4️⃣ Verificando limpieza...")
        context_after = await self.get_accumulated_context(user_id, project_id)
        
        if context_after['status_code'] == 200:
            remaining = context_after['data']['message_count']
            print(f"📊 Mensajes restantes: {remaining}")
            
            if remaining == 0:
                print("✅ Contexto completamente limpiado")
            else:
                print("⚠️ Algunos mensajes permanecen")
        
        return {
            "successfully_cleared": context_after['data']['message_count'] == 0 if context_after['status_code'] == 200 else False
        }
    
    async def demo_real_world_scenario(self):
        """
        Escenario del mundo real: Cliente haciendo múltiples preguntas
        """
        print("\n🌍 ESCENARIO DEL MUNDO REAL")
        print("=" * 50)
        print("Simulando un cliente que hace múltiples preguntas sobre un servicio")
        
        # Configuración
        user_id = f"cliente_{int(time.time())}"
        project_id = "empresa_servicios"
        
        # Conversación realista
        conversation = [
            "Hola, estoy interesado en sus servicios de consultoría",
            "¿Cuáles son sus precios?",
            "¿Tienen descuentos para startups?",
            "¿Cuánto tiempo toma un proyecto típico?",
            "¿Pueden trabajar remotamente?",
            "¿Ofrecen soporte post-proyecto?",
            "¿Tienen experiencia en mi industria?",
            "¿Cuándo podrían empezar?"
        ]
        
        print(f"👤 Cliente: '{conversation[0]}'")
        
        # Enviar mensaje principal
        main_response = await self.send_message(conversation[0], user_id, project_id)
        self.print_response(main_response, "RESPUESTA INICIAL")
        
        # Cliente envía preguntas adicionales rápidamente
        print("\n💭 Cliente piensa en más preguntas y las envía rápidamente...")
        
        for i, question in enumerate(conversation[1:], 1):
            print(f"\n👤 Cliente: '{question}'")
            response = await self.send_message(question, user_id, project_id)
            
            if response['data'].get('queued_message'):
                print("✅ Pregunta conservada - no se pierde información")
            elif response['status_code'] == 429:
                print("⚠️ Pregunta rechazada - información perdida")
            else:
                print("🤖 Pregunta procesándose")
            
            await asyncio.sleep(0.8)  # Simular velocidad humana de escritura
        
        # Estado del contexto
        print("\n📊 Estado del contexto acumulado:")
        context_response = await self.get_accumulated_context(user_id, project_id)
        
        if context_response['status_code'] == 200:
            data = context_response['data']
            print(f"📝 Preguntas conservadas: {data['message_count']}")
            print(f"💡 Todas las preguntas serán respondidas juntas")
        
        return {
            "scenario": "Consultoría empresarial",
            "questions_asked": len(conversation),
            "questions_conserved": data['message_count'] if context_response['status_code'] == 200 else 0
        }
    
    async def run_full_demo(self):
        """
        Ejecuta la demostración completa
        """
        print("🎯 DEMOSTRACIÓN COMPLETA: CONSERVACIÓN DE MENSAJES")
        print("=" * 60)
        print("Esta demostración muestra cómo el sistema conserva mensajes")
        print("adicionales en lugar de rechazarlos, evitando pérdida de información.")
        print("=" * 60)
        
        demos = [
            ("Conservación Básica", self.demo_basic_conservation),
            ("Procesamiento con Contexto", self.demo_context_processing),
            ("Gestión de Contexto", self.demo_context_management),
            ("Escenario Real", self.demo_real_world_scenario)
        ]
        
        results = []
        
        for demo_name, demo_func in demos:
            print(f"\n🚀 Ejecutando: {demo_name}")
            print("=" * 30)
            
            try:
                result = await demo_func()
                results.append({
                    "demo": demo_name,
                    "success": True,
                    "result": result
                })
                print(f"✅ {demo_name} completado")
            except Exception as e:
                print(f"❌ {demo_name} falló: {str(e)}")
                results.append({
                    "demo": demo_name,
                    "success": False,
                    "error": str(e)
                })
        
        # Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE LA DEMOSTRACIÓN")
        print("=" * 60)
        
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        
        print(f"✅ Demos exitosas: {successful}/{total}")
        print(f"❌ Demos fallidas: {total - successful}/{total}")
        
        if successful == total:
            print("\n🎉 ¡TODAS LAS DEMOSTRACIONES COMPLETADAS!")
            print("💡 El sistema de conservación de mensajes funciona correctamente")
            print("📝 Los usuarios ya no perderán información importante")
        else:
            print("\n⚠️ Algunas demostraciones fallaron")
            print("🔧 Revisa la configuración del sistema")
        
        print("\n📋 BENEFICIOS DEL SISTEMA:")
        print("• ✅ Cero pérdida de información")
        print("• ✅ Mejor experiencia de usuario")
        print("• ✅ Respuestas más completas")
        print("• ✅ Sistema más estable")
        
        return results

async def main():
    """
    Función principal para ejecutar la demostración
    """
    try:
        async with ChatConservationExample() as demo:
            await demo.run_full_demo()
    except KeyboardInterrupt:
        print("\n\n⏹️ Demostración interrumpida por el usuario")
    except Exception as e:
        print(f"\n❌ Error en la demostración: {str(e)}")
        print("🔧 Asegúrate de que el servidor esté ejecutándose en http://localhost:8000")

if __name__ == "__main__":
    print("🚀 Iniciando demostración de conservación de mensajes...")
    print("⚙️ Asegúrate de que el servidor esté ejecutándose")
    print("🔗 URL del servidor: http://localhost:8000")
    print()
    
    asyncio.run(main()) 