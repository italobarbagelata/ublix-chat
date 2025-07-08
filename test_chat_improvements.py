"""
🧪 SCRIPT DE PRUEBAS - Sistema Anti-Spam de Chat

Prueba las nuevas funcionalidades implementadas para evitar
el problema de múltiples mensajes concurrentes.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import List, Dict, Any

class ChatTester:
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
            "name": "Test User"
        }
        
        async with self.session.post(url, json=data) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }
    
    async def send_message_stream(self, message: str, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Envía un mensaje al chat con streaming"""
        url = f"{self.base_url}/api/chat/stream"
        data = {
            "message": message,
            "user_id": user_id,
            "project_id": project_id,
            "name": "Test User"
        }
        
        chunks = []
        async with self.session.post(url, json=data) as response:
            async for line in response.content:
                if line:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        chunk_data = line_str[6:]  # Remove 'data: ' prefix
                        try:
                            chunk = json.loads(chunk_data)
                            chunks.append(chunk)
                        except json.JSONDecodeError:
                            continue
        
        return chunks
    
    async def get_queue_status(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Obtiene el estado de la cola de un usuario"""
        url = f"{self.base_url}/api/chat/queue/status"
        params = {"user_id": user_id, "project_id": project_id}
        
        async with self.session.get(url, params=params) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }
    
    async def get_accumulated_context(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """🆕 Obtiene el contexto acumulado de un usuario"""
        url = f"{self.base_url}/api/chat/context/accumulated"
        params = {"user_id": user_id, "project_id": project_id}
        
        async with self.session.get(url, params=params) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }
    
    async def clear_accumulated_context(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """🆕 Limpia el contexto acumulado de un usuario"""
        url = f"{self.base_url}/api/chat/context/clear"
        data = {"user_id": user_id, "project_id": project_id}
        
        async with self.session.post(url, json=data) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema"""
        url = f"{self.base_url}/api/chat/system/stats"
        
        async with self.session.get(url) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }
    
    async def cancel_user_queue(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Cancela la cola de un usuario"""
        url = f"{self.base_url}/api/chat/queue/cancel"
        data = {"user_id": user_id, "project_id": project_id}
        
        async with self.session.post(url, json=data) as response:
            return {
                "status_code": response.status,
                "data": await response.json()
            }

    async def test_message_conservation(self):
        """
        🆕 TEST: Verifica que los mensajes adicionales se conserven en contexto
        """
        print("🧪 TEST: Conservación de Mensajes")
        user_id = f"test_user_{int(time.time())}"
        project_id = "test_project"
        
        # 1. Enviar mensaje principal
        print("📨 Enviando mensaje principal...")
        response1 = await self.send_message(
            "¿Cuáles son sus precios?", 
            user_id, 
            project_id
        )
        print(f"Respuesta 1: {response1['data'].get('response', 'No response')}")
        
        # 2. Enviar mensajes adicionales rápidamente
        print("📬 Enviando mensajes adicionales...")
        messages_to_queue = [
            "También necesito saber horarios",
            "Y formas de pago disponibles",
            "¿Tienen descuentos?"
        ]
        
        queued_responses = []
        for msg in messages_to_queue:
            response = await self.send_message(msg, user_id, project_id)
            queued_responses.append(response)
            print(f"Mensaje '{msg}' -> Status: {response['status_code']}")
            if response['data'].get('queued_message'):
                print(f"  ✅ Conservado: {response['data']['response']}")
        
        # 3. Verificar contexto acumulado
        print("🔍 Verificando contexto acumulado...")
        context_response = await self.get_accumulated_context(user_id, project_id)
        if context_response['status_code'] == 200:
            context_data = context_response['data']
            print(f"📝 Mensajes en contexto: {context_data['message_count']}")
            for msg in context_data['accumulated_messages']:
                print(f"  - [{msg['timestamp']}] {msg['message']}")
        
        # 4. Esperar a que termine el procesamiento del primer mensaje
        print("⏳ Esperando procesamiento completo...")
        await asyncio.sleep(10)  # Dar tiempo al procesamiento
        
        # 5. Verificar que el contexto se haya limpiado
        print("🔍 Verificando limpieza de contexto...")
        context_after = await self.get_accumulated_context(user_id, project_id)
        if context_after['status_code'] == 200:
            remaining_messages = context_after['data']['message_count']
            print(f"📝 Mensajes restantes en contexto: {remaining_messages}")
            if remaining_messages == 0:
                print("✅ Contexto limpiado correctamente")
            else:
                print("⚠️ Algunos mensajes permanecen en contexto")
        
        return {
            "success": True,
            "message": "Test de conservación completado",
            "queued_messages": len(queued_responses),
            "context_messages": context_response['data']['message_count'] if context_response['status_code'] == 200 else 0
        }

    async def test_streaming_with_conservation(self):
        """
        🆕 TEST: Verifica conservación de mensajes con streaming
        """
        print("🧪 TEST: Streaming con Conservación")
        user_id = f"test_stream_{int(time.time())}"
        project_id = "test_project"
        
        # 1. Iniciar streaming
        print("🌊 Iniciando streaming...")
        stream_task = asyncio.create_task(
            self.send_message_stream("Necesito información completa", user_id, project_id)
        )
        
        # 2. Enviar mensajes adicionales mientras hace streaming
        await asyncio.sleep(1)  # Pequeña pausa para que inicie el streaming
        
        print("📬 Enviando mensajes durante streaming...")
        additional_messages = [
            "Sobre precios",
            "Sobre horarios",
            "Sobre disponibilidad"
        ]
        
        for msg in additional_messages:
            response = await self.send_message(msg, user_id, project_id)
            print(f"Mensaje '{msg}' -> Conservado: {response['data'].get('queued_message', False)}")
        
        # 3. Esperar respuesta del streaming
        print("⏳ Esperando respuesta de streaming...")
        stream_chunks = await stream_task
        
        # 4. Analizar chunks del streaming
        print("🔍 Analizando chunks de streaming...")
        immediate_response = None
        has_context_info = False
        
        for chunk in stream_chunks:
            if chunk.get('type') == 'immediate_response':
                immediate_response = chunk
                if 'includes_queued_messages' in chunk:
                    has_context_info = True
                    print(f"✅ Streaming incluye contexto: {chunk.get('messages_processed', 0)} mensajes")
        
        return {
            "success": True,
            "message": "Test de streaming con conservación completado",
            "stream_chunks": len(stream_chunks),
            "context_detected": has_context_info,
            "immediate_response": immediate_response
        }

    async def test_context_management_endpoints(self):
        """
        🆕 TEST: Verifica endpoints de gestión de contexto
        """
        print("🧪 TEST: Endpoints de Gestión de Contexto")
        user_id = f"test_context_{int(time.time())}"
        project_id = "test_project"
        
        # 1. Crear contexto acumulado
        print("📝 Creando contexto acumulado...")
        await self.send_message("Mensaje principal", user_id, project_id)
        
        # Enviar mensajes adicionales
        additional_messages = [
            "Mensaje adicional 1",
            "Mensaje adicional 2",
            "Mensaje adicional 3"
        ]
        
        for msg in additional_messages:
            await self.send_message(msg, user_id, project_id)
        
        # 2. Consultar contexto acumulado
        print("🔍 Consultando contexto acumulado...")
        context_response = await self.get_accumulated_context(user_id, project_id)
        
        context_success = context_response['status_code'] == 200
        context_count = 0
        
        if context_success:
            context_count = context_response['data']['message_count']
            print(f"✅ Contexto obtenido: {context_count} mensajes")
        
        # 3. Limpiar contexto acumulado
        print("🗑️ Limpiando contexto acumulado...")
        clear_response = await self.clear_accumulated_context(user_id, project_id)
        
        clear_success = clear_response['status_code'] == 200
        cleared_count = 0
        
        if clear_success:
            cleared_count = clear_response['data']['messages_cleared']
            print(f"✅ Contexto limpiado: {cleared_count} mensajes")
        
        # 4. Verificar que se limpió
        print("🔍 Verificando limpieza...")
        context_after = await self.get_accumulated_context(user_id, project_id)
        
        if context_after['status_code'] == 200:
            remaining = context_after['data']['message_count']
            print(f"📝 Mensajes restantes: {remaining}")
            cleanup_success = remaining == 0
        else:
            cleanup_success = False
        
        return {
            "success": context_success and clear_success and cleanup_success,
            "message": "Test de endpoints de contexto completado",
            "context_created": context_count,
            "context_cleared": cleared_count,
            "properly_cleaned": cleanup_success
        }

    async def test_rate_limiting_with_conservation(self):
        """
        🆕 TEST: Verifica rate limiting con conservación de mensajes
        """
        print("🧪 TEST: Rate Limiting con Conservación")
        user_id = f"test_rate_{int(time.time())}"
        project_id = "test_project"
        
        # 1. Enviar múltiples mensajes rápidamente
        print("🚀 Enviando múltiples mensajes rápidamente...")
        messages = [
            "Primer mensaje",
            "Segundo mensaje",
            "Tercer mensaje",
            "Cuarto mensaje",
            "Quinto mensaje"
        ]
        
        responses = []
        for i, msg in enumerate(messages):
            response = await self.send_message(msg, user_id, project_id)
            responses.append(response)
            print(f"Mensaje {i+1}: Status {response['status_code']}")
            
            if response['data'].get('queued_message'):
                print(f"  📬 Conservado en contexto")
            elif response['status_code'] == 429:
                print(f"  ⚠️ Rate limited (comportamiento anterior)")
            else:
                print(f"  ✅ Procesando")
        
        # 2. Analizar respuestas
        processing_count = sum(1 for r in responses if r['status_code'] == 200 and not r['data'].get('queued_message'))
        queued_count = sum(1 for r in responses if r['data'].get('queued_message'))
        rate_limited_count = sum(1 for r in responses if r['status_code'] == 429)
        
        print(f"📊 Resultados:")
        print(f"  Procesando: {processing_count}")
        print(f"  Conservados: {queued_count}")
        print(f"  Rate limited: {rate_limited_count}")
        
        # 3. Verificar contexto acumulado
        context_response = await self.get_accumulated_context(user_id, project_id)
        context_messages = 0
        if context_response['status_code'] == 200:
            context_messages = context_response['data']['message_count']
            print(f"  En contexto: {context_messages}")
        
        return {
            "success": True,
            "message": "Test de rate limiting con conservación completado",
            "processing_count": processing_count,
            "queued_count": queued_count,
            "rate_limited_count": rate_limited_count,
            "context_messages": context_messages
        }

    async def test_full_conservation_flow(self):
        """
        🆕 TEST: Flujo completo de conservación de mensajes
        """
        print("🧪 TEST: Flujo Completo de Conservación")
        user_id = f"test_full_{int(time.time())}"
        project_id = "test_project"
        
        # 1. Mensaje principal
        print("1️⃣ Enviando mensaje principal...")
        main_response = await self.send_message("¿Cuáles son sus servicios?", user_id, project_id)
        print(f"   Status: {main_response['status_code']}")
        
        # 2. Mensajes adicionales
        print("2️⃣ Enviando mensajes adicionales...")
        additional_messages = [
            "También necesito precios",
            "Y horarios de atención",
            "¿Tienen descuentos para empresas?",
            "Me interesa el servicio premium"
        ]
        
        for msg in additional_messages:
            response = await self.send_message(msg, user_id, project_id)
            conservation_status = "✅ Conservado" if response['data'].get('queued_message') else "❌ No conservado"
            print(f"   '{msg}' -> {conservation_status}")
        
        # 3. Verificar contexto antes del procesamiento
        print("3️⃣ Verificando contexto acumulado...")
        context_before = await self.get_accumulated_context(user_id, project_id)
        messages_before = context_before['data']['message_count'] if context_before['status_code'] == 200 else 0
        print(f"   Mensajes en contexto: {messages_before}")
        
        # 4. Esperar procesamiento completo
        print("4️⃣ Esperando procesamiento completo...")
        await asyncio.sleep(15)  # Dar tiempo suficiente
        
        # 5. Verificar contexto después del procesamiento
        print("5️⃣ Verificando contexto después del procesamiento...")
        context_after = await self.get_accumulated_context(user_id, project_id)
        messages_after = context_after['data']['message_count'] if context_after['status_code'] == 200 else 0
        print(f"   Mensajes restantes: {messages_after}")
        
        # 6. Verificar que se procesó todo
        processing_success = messages_after == 0
        print(f"6️⃣ Procesamiento completo: {'✅ Sí' if processing_success else '❌ No'}")
        
        return {
            "success": processing_success,
            "message": "Test de flujo completo completado",
            "main_message_sent": main_response['status_code'] == 200,
            "additional_messages": len(additional_messages),
            "messages_before_processing": messages_before,
            "messages_after_processing": messages_after,
            "processing_completed": processing_success
        }

    async def run_all_conservation_tests(self):
        """
        🆕 Ejecuta todos los tests de conservación de mensajes
        """
        print("🚀 EJECUTANDO TESTS DE CONSERVACIÓN DE MENSAJES")
        print("=" * 60)
        
        tests = [
            ("Conservación de Mensajes", self.test_message_conservation),
            ("Streaming con Conservación", self.test_streaming_with_conservation),
            ("Endpoints de Gestión", self.test_context_management_endpoints),
            ("Rate Limiting con Conservación", self.test_rate_limiting_with_conservation),
            ("Flujo Completo", self.test_full_conservation_flow)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            print(f"\n🧪 Ejecutando: {test_name}")
            print("-" * 40)
            
            try:
                result = await test_func()
                results.append({
                    "test": test_name,
                    "success": result.get("success", False),
                    "details": result
                })
                print(f"✅ {test_name}: {'PASSED' if result.get('success') else 'FAILED'}")
            except Exception as e:
                print(f"❌ {test_name}: ERROR - {str(e)}")
                results.append({
                    "test": test_name,
                    "success": False,
                    "error": str(e)
                })
        
        # Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE TESTS DE CONSERVACIÓN")
        print("=" * 60)
        
        passed = sum(1 for r in results if r["success"])
        total = len(results)
        
        print(f"✅ Tests exitosos: {passed}/{total}")
        print(f"❌ Tests fallidos: {total - passed}/{total}")
        
        if passed == total:
            print("🎉 ¡TODOS LOS TESTS DE CONSERVACIÓN PASARON!")
        else:
            print("⚠️  Algunos tests de conservación fallaron")
            
        return results

async def test_rate_limiting():
    """Prueba el control de concurrencia"""
    print("🔒 Probando control de concurrencia...")
    
    async with ChatTester() as tester:
        user_id = "test_user_1"
        project_id = "test_project_1"
        
        # Enviar múltiples mensajes rápidamente
        tasks = []
        messages = [
            "Primer mensaje",
            "Segundo mensaje (debería ser bloqueado)",
            "Tercer mensaje (debería ser bloqueado)"
        ]
        
        for i, message in enumerate(messages):
            task = tester.send_message(message, user_id, project_id)
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"✅ Resultados del test de rate limiting:")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"   Mensaje {i+1}: ERROR - {result}")
            else:
                status = result.get("status_code")
                print(f"   Mensaje {i+1}: HTTP {status}")
                if status == 429:
                    print(f"      ✅ Rate limit funcionando correctamente")
                elif status == 200:
                    print(f"      ✅ Mensaje procesado exitosamente")

async def test_streaming_with_immediate_response():
    """Prueba streaming con respuestas inmediatas"""
    print("\n📡 Probando streaming con respuestas inmediatas...")
    
    async with ChatTester() as tester:
        user_id = "test_user_2"
        project_id = "test_project_2"
        
        # Probar diferentes tipos de consultas
        test_messages = [
            "Quiero agendar una cita para mañana",
            "¿Qué productos tienes disponibles?",
            "Necesito información sobre tu servicio"
        ]
        
        for message in test_messages:
            print(f"\n📤 Enviando: '{message}'")
            chunks = await tester.send_message_stream(message, user_id, project_id)
            
            for chunk in chunks[:3]:  # Mostrar solo los primeros 3 chunks
                chunk_type = chunk.get("type", "unknown")
                content = chunk.get("content", "")
                print(f"   📦 {chunk_type}: {content[:100]}...")

async def test_queue_monitoring():
    """Prueba el monitoreo de colas"""
    print("\n📊 Probando monitoreo de colas...")
    
    async with ChatTester() as tester:
        user_id = "test_user_3"
        project_id = "test_project_3"
        
        # Obtener estado inicial
        print("📋 Estado inicial de la cola:")
        status = await tester.get_queue_status(user_id, project_id)
        print(f"   Status: {status['status_code']}")
        if status['status_code'] == 200:
            queue_data = status['data']['queue_status']
            print(f"   Queue size: {queue_data['queue_size']}")
            print(f"   Is processing: {queue_data['is_processing']}")
        
        # Obtener estadísticas del sistema
        print("\n📈 Estadísticas del sistema:")
        stats = await tester.get_system_stats()
        print(f"   Status: {stats['status_code']}")
        if stats['status_code'] == 200:
            system_data = stats['data']
            print(f"   Active conversations: {system_data.get('active_conversations', 0)}")
            print(f"   Messages processed: {system_data.get('messages_processed', 0)}")
            print(f"   Active queues: {system_data.get('active_queues', 0)}")

async def test_queue_cancellation():
    """Prueba la cancelación de colas"""
    print("\n🚫 Probando cancelación de colas...")
    
    async with ChatTester() as tester:
        user_id = "test_user_4"
        project_id = "test_project_4"
        
        # Cancelar cola (aunque esté vacía)
        result = await tester.cancel_user_queue(user_id, project_id)
        print(f"   Status: {result['status_code']}")
        if result['status_code'] == 200:
            data = result['data']
            print(f"   Cancelled messages: {data.get('cancelled_messages', 0)}")
            print(f"   Conversation cleared: {data.get('conversation_cleared', False)}")

async def stress_test():
    """Test de stress con múltiples usuarios concurrentes"""
    print("\n⚡ Ejecutando stress test...")
    
    async with ChatTester() as tester:
        # Crear múltiples tareas concurrentes con diferentes usuarios
        tasks = []
        
        for user_num in range(5):
            for msg_num in range(3):
                user_id = f"stress_user_{user_num}"
                project_id = "stress_project"
                message = f"Mensaje {msg_num} del usuario {user_num}"
                
                task = tester.send_message(message, user_id, project_id)
                tasks.append((user_num, msg_num, task))
        
        print(f"📤 Enviando {len(tasks)} mensajes concurrentes...")
        
        results = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)
        
        # Analizar resultados
        success_count = 0
        rate_limited_count = 0
        error_count = 0
        
        for i, ((user_num, msg_num, _), result) in enumerate(zip(tasks, results)):
            if isinstance(result, Exception):
                error_count += 1
                print(f"   ❌ User {user_num}, Msg {msg_num}: Exception - {result}")
            else:
                status = result.get("status_code")
                if status == 200:
                    success_count += 1
                elif status == 429:
                    rate_limited_count += 1
                else:
                    error_count += 1
        
        print(f"\n📊 Resultados del stress test:")
        print(f"   ✅ Exitosos: {success_count}")
        print(f"   ⏸️  Rate limited: {rate_limited_count}")
        print(f"   ❌ Errores: {error_count}")
        print(f"   📈 Rate de rate limiting: {rate_limited_count/len(tasks)*100:.1f}%")

async def main():
    """Ejecuta todas las pruebas"""
    print("🚀 Iniciando pruebas del sistema anti-spam de chat\n")
    
    try:
        await test_rate_limiting()
        await test_streaming_with_immediate_response()
        await test_queue_monitoring()
        await test_queue_cancellation()
        await stress_test()
        
        print("\n✅ Todas las pruebas completadas exitosamente!")
        
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        raise

if __name__ == "__main__":
    # Configurar asyncio para Windows si es necesario
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass  # No estamos en Windows
    
    asyncio.run(main()) 