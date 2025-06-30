#!/usr/bin/env python3
"""
🚀 EJEMPLO: Uso de Contact Tool Dinámico
=========================================

Este archivo muestra ejemplos prácticos de cómo usar la nueva herramienta 
de contactos con campos dinámicos para diferentes tipos de bot.

Casos cubiertos:
- Bot de Inversiones
- Bot de E-commerce  
- Bot de Servicios
- Integración con otras herramientas
"""

import asyncio
import json
from typing import Dict, Any

# Importar las funciones de la herramienta
from app.controler.chat.core.tools.contact_tool import (
    get_contact_async,
    save_contact_async,
    extract_additional_fields_async,
    get_field_config_examples,
    SaveContactTool,
    format_contact_info
)

# ===========================
# CONFIGURACIONES POR TIPO DE BOT
# ===========================

def get_investment_bot_config() -> Dict[str, Any]:
    """Configuración para bot de inversiones."""
    return {
        "direccion": {
            "keywords": ["vivo en", "mi dirección", "dirección es", "domicilio", "resido en"],
            "type": "string",
            "description": "Dirección de residencia"
        },
        "ciudad": {
            "keywords": ["ciudad", "vivo en", "de la ciudad", "en"],
            "type": "string",
            "description": "Ciudad donde reside"
        },
        "edad": {
            "keywords": ["tengo", "años", "mi edad", "edad es"],
            "type": "number",
            "description": "Edad del cliente"
        },
        "ha_invertido": {
            "keywords": ["he invertido", "invirtiendo", "inversión", "broker", "acciones", "bolsa"],
            "type": "boolean",
            "description": "Experiencia previa en inversiones"
        },
        "presupuesto": {
            "keywords": ["presupuesto", "dispongo", "capital", "puedo invertir"],
            "type": "number",
            "description": "Capital disponible para invertir"
        },
        "tolerancia_riesgo": {
            "keywords": ["conservador", "agresivo", "moderado", "riesgo"],
            "type": "string",
            "description": "Tolerancia al riesgo"
        }
    }

def get_ecommerce_bot_config() -> Dict[str, Any]:
    """Configuración para bot de e-commerce."""
    return {
        "producto_interes": {
            "keywords": ["me interesa", "quiero", "busco", "necesito", "producto"],
            "type": "string",
            "description": "Producto de interés"
        },
        "presupuesto": {
            "keywords": ["presupuesto", "dispongo", "puedo pagar", "precio máximo"],
            "type": "number",
            "description": "Presupuesto disponible"
        },
        "fecha_compra": {
            "keywords": ["cuando", "fecha", "para cuándo", "necesito para"],
            "type": "string",
            "description": "Fecha estimada de compra"
        },
        "metodo_pago": {
            "keywords": ["pago", "transferencia", "tarjeta", "efectivo", "cuotas"],
            "type": "string",
            "description": "Método de pago preferido"
        },
        "categoria_preferida": {
            "keywords": ["categoria", "tipo", "marca", "estilo"],
            "type": "string",
            "description": "Categoría o marca preferida"
        }
    }

# ===========================
# EJEMPLOS PRÁCTICOS POR ESCENARIO
# ===========================

async def ejemplo_bot_inversiones():
    """Ejemplo completo para bot de inversiones."""
    print("🏦 === EJEMPLO: BOT DE INVERSIONES ===")
    
    project_id = "proj_inversiones_123"
    user_id = "user_investor_456"
    
    # Crear herramienta
    tool = SaveContactTool(project_id, user_id)
    
    # Caso 1: Usuario da información básica
    print("\n📝 Caso 1: Información básica")
    conversation1 = "Hola, soy Juan Pérez, mi email es juan@inversiones.com y mi teléfono es +56912345678"
    
    result1 = await tool._arun(
        name="Juan Pérez",
        email="juan@inversiones.com", 
        phone_number="+56912345678"
    )
    print(f"Resultado: {result1}")
    
    # Caso 2: Usuario menciona experiencia de inversión  
    print("\n📝 Caso 2: Extracción automática de campos de inversión")
    conversation2 = "Tengo 35 años, vivo en Santiago y ya he invertido en acciones por 3 años. Dispongo de 5 millones para invertir"
    
    config = get_investment_bot_config()
    result2 = await tool._arun(
        conversation_text=conversation2,
        field_config=json.dumps(config)
    )
    print(f"Resultado: {result2}")
    
    # Caso 3: Actualización manual de tolerancia al riesgo
    print("\n📝 Caso 3: Actualización manual")
    result3 = await tool._arun(
        additional_fields='{"tolerancia_riesgo": "moderado", "objetivo_inversion": "largo plazo"}'
    )
    print(f"Resultado: {result3}")
    
    # Verificar información final
    print("\n📋 Información final del contacto:")
    final_contact = await get_contact_async(project_id, user_id)
    print(format_contact_info(final_contact))

async def ejemplo_bot_ecommerce():
    """Ejemplo completo para bot de e-commerce."""
    print("\n🛒 === EJEMPLO: BOT DE E-COMMERCE ===")
    
    project_id = "proj_ecommerce_789"
    user_id = "user_shopper_123"
    
    tool = SaveContactTool(project_id, user_id)
    
    # Caso 1: Usuario busca producto específico
    print("\n📝 Caso 1: Búsqueda de producto")
    conversation1 = "Hola, busco una laptop gaming, mi presupuesto es 800mil y la necesito para febrero"
    
    config = get_ecommerce_bot_config()
    result1 = await tool._arun(
        conversation_text=conversation1,
        field_config=json.dumps(config)
    )
    print(f"Resultado: {result1}")
    
    # Caso 2: Agregar información de contacto
    print("\n📝 Caso 2: Información de contacto")
    result2 = await tool._arun(
        name="María González",
        email="maria@email.com",
        phone_number="+56987654321"
    )
    print(f"Resultado: {result2}")
    
    # Caso 3: Preferencias adicionales
    print("\n📝 Caso 3: Preferencias adicionales")
    result3 = await tool._arun(
        additional_fields='{"categoria_preferida": "gaming", "metodo_pago": "transferencia", "envio_express": true}'
    )
    print(f"Resultado: {result3}")

async def ejemplo_integracion_con_otras_herramientas():
    """Ejemplo de integración con otras herramientas."""
    print("\n🔗 === EJEMPLO: INTEGRACIÓN CON OTRAS HERRAMIENTAS ===")
    
    project_id = "proj_servicios_456"
    user_id = "user_client_789"
    
    # 1. Simular captura de información
    contact_data = {
        "name": "Carlos Ramírez",
        "email": "carlos@empresa.com",
        "phone_number": "+56911111111"
    }
    
    additional_data = {
        "tipo_servicio": "consultoría",
        "urgencia": "alta",
        "presupuesto": 2000000,
        "disponibilidad": "mañanas"
    }
    
    # Guardar información
    contact = await save_contact_async(
        project_id, user_id, 
        **contact_data,
        additional_fields=additional_data
    )
    
    print("✅ Contacto guardado exitosamente")
    
    # 2. Usar información para personalizar email
    print("\n📧 Simulación de envío de email personalizado:")
    if contact:
        additional = contact.get('additional_fields', {})
        if isinstance(additional, str):
            additional = json.loads(additional)
        
        email_content = f"""
        Hola {contact['name']},
        
        Gracias por contactarnos para el servicio de {additional.get('tipo_servicio', 'consultoría')}.
        
        Entendemos que es de urgencia {additional.get('urgencia', 'normal')} y que tu disponibilidad 
        es en las {additional.get('disponibilidad', 'tardes')}.
        
        Basado en tu presupuesto de ${additional.get('presupuesto', 0):,}, podemos ofrecerte...
        
        Saludos,
        El equipo
        """
        
        print(email_content)
    
    # 3. Lead scoring automático
    print("\n📊 Lead scoring automático:")
    score = calculate_lead_score(contact)
    print(f"Puntuación del lead: {score}/100")
    
    # 4. Segmentación
    print("\n🎯 Segmentación automática:")
    segment = segment_contact(contact)
    print(f"Segmento: {segment}")

def calculate_lead_score(contact: Dict[str, Any]) -> int:
    """Calcula puntuación de lead basada en información del contacto."""
    if not contact:
        return 0
    
    score = 0
    additional = contact.get('additional_fields', {})
    if isinstance(additional, str):
        additional = json.loads(additional)
    
    # Puntuación por completitud de datos
    if contact.get('name'): score += 15
    if contact.get('email'): score += 20
    if contact.get('phone_number'): score += 15
    
    # Puntuación por campos específicos
    if additional.get('presupuesto', 0) > 1000000: score += 25
    if additional.get('urgencia') == 'alta': score += 15
    if additional.get('tipo_servicio'): score += 10
    
    return min(score, 100)  # Máximo 100

def segment_contact(contact: Dict[str, Any]) -> str:
    """Segmenta contacto según sus características."""
    additional = contact.get('additional_fields', {})
    if isinstance(additional, str):
        additional = json.loads(additional)
    
    presupuesto = additional.get('presupuesto', 0)
    urgencia = additional.get('urgencia', 'normal')
    
    if presupuesto > 3000000 and urgencia == 'alta':
        return "CLIENTE_VIP"
    elif presupuesto > 1000000:
        return "CLIENTE_PREMIUM"
    elif urgencia == 'alta':
        return "URGENTE"
    else:
        return "ESTÁNDAR"

async def ejemplo_configuraciones_predefinidas():
    """Muestra las configuraciones predefinidas disponibles."""
    print("\n⚙️ === CONFIGURACIONES PREDEFINIDAS ===")
    
    examples = get_field_config_examples()
    
    for bot_type, config in examples.items():
        print(f"\n🤖 {bot_type.upper()}:")
        for field, settings in config.items():
            print(f"  • {field}: {settings['description']}")
            print(f"    Keywords: {settings['keywords']}")
            print(f"    Tipo: {settings['type']}")

# ===========================
# FUNCIÓN PRINCIPAL
# ===========================

async def main():
    """Función principal que ejecuta todos los ejemplos."""
    print("🚀 DEMOSTRACIONES DE CONTACT TOOL DINÁMICO")
    print("=" * 50)
    
    try:
        # Mostrar configuraciones disponibles
        await ejemplo_configuraciones_predefinidas()
        
        # Ejemplos por tipo de bot
        await ejemplo_bot_inversiones()
        await ejemplo_bot_ecommerce()
        
        # Ejemplo de integración
        await ejemplo_integracion_con_otras_herramientas()
        
        print("\n✅ ¡Todos los ejemplos ejecutados exitosamente!")
        
    except Exception as e:
        print(f"❌ Error en la demostración: {str(e)}")

# ===========================
# UTILIDADES ADICIONALES
# ===========================

def validate_field_config(config: Dict[str, Any]) -> bool:
    """Valida que la configuración de campos tenga la estructura correcta."""
    required_keys = ['keywords', 'type']
    valid_types = ['string', 'number', 'boolean']
    
    for field_name, field_config in config.items():
        # Verificar claves requeridas
        for key in required_keys:
            if key not in field_config:
                print(f"❌ Campo '{field_name}' falta clave '{key}'")
                return False
        
        # Verificar tipo válido
        if field_config['type'] not in valid_types:
            print(f"❌ Campo '{field_name}' tiene tipo inválido: {field_config['type']}")
            return False
        
        # Verificar que keywords sea una lista
        if not isinstance(field_config['keywords'], list):
            print(f"❌ Campo '{field_name}' keywords debe ser una lista")
            return False
    
    return True

def create_custom_config(fields: Dict[str, Dict]) -> str:
    """Crea una configuración personalizada y la valida."""
    if validate_field_config(fields):
        return json.dumps(fields)
    else:
        raise ValueError("Configuración de campos inválida")

# Ejecutar si se llama directamente
if __name__ == "__main__":
    # Ejemplo de configuración personalizada
    custom_config = {
        "area_interes": {
            "keywords": ["me interesa", "área", "especialidad"],
            "type": "string",
            "description": "Área de interés específica"
        },
        "experiencia_anos": {
            "keywords": ["años de experiencia", "experiencia", "trabajando"],
            "type": "number",
            "description": "Años de experiencia"
        }
    }
    
    # Validar configuración personalizada
    if validate_field_config(custom_config):
        print("✅ Configuración personalizada válida")
    
    # Ejecutar ejemplos
    asyncio.run(main()) 