"""
===============================================================================
EJEMPLO DE USO: CONTACT TOOL CON CONFIGURACIÓN AUTOMÁTICA
===============================================================================

Este ejemplo muestra cómo usar la herramienta de contactos con la nueva
funcionalidad de configuración automática usando la tabla contact_field_configs.

PASOS PARA IMPLEMENTAR:
1. Crear la tabla contact_field_configs (ver create_contact_field_configs_table.sql)
2. Configurar los campos para tu proyecto
3. Usar auto_extract=true en la herramienta

===============================================================================
"""

import asyncio
from app.controler.chat.core.tools.contact_tool import (
    SaveContactTool, 
    auto_extract_fields_async,
    save_contact_async,
    get_contact_async
)

# ===============================================================================
# EJEMPLO 1: CONFIGURACIÓN AUTOMÁTICA POR PROYECTO
# ===============================================================================

async def ejemplo_configuracion_automatica():
    """
    Demuestra cómo la herramienta usa automáticamente la configuración
    almacenada en la tabla contact_field_configs.
    """
    
    print("=== EJEMPLO 1: CONFIGURACIÓN AUTOMÁTICA ===")
    
    # Configurar la herramienta
    project_id = "project-inversiones-abc"
    user_id = "user_12345"
    
    tool = SaveContactTool(project_id, user_id)
    
    # Texto de conversación con información del usuario
    conversation_text = """
    Hola, mi nombre es María González, mi email es maria@email.com.
    Tengo 35 años y vivo en Las Condes, Santiago.
    He invertido antes en acciones y tengo un presupuesto de 5 millones
    para nuevas inversiones. Me considero una inversionista moderada.
    """
    
    # Usar la herramienta con auto_extract=true
    # Esto buscará automáticamente la configuración del proyecto en la BD
    result = tool._run(
        conversation_text=conversation_text,
        auto_extract=True  # ¡La clave está aquí!
    )
    
    print(f"Resultado: {result}")

# ===============================================================================
# EJEMPLO 2: CONFIGURACIÓN MANUAL DE CAMPOS EN LA BASE DE DATOS
# ===============================================================================

async def ejemplo_configurar_campos_proyecto():
    """
    Muestra cómo configurar los campos para un proyecto específico
    usando las funciones SQL creadas.
    """
    
    print("\n=== EJEMPLO 2: CONFIGURAR CAMPOS EN BD ===")
    
    # Ejemplo de consultas SQL para configurar campos
    sql_ejemplos = """
    -- 1. Configurar campos para un proyecto de inversiones
    SELECT add_contact_field(
        'project-inversiones-abc'::UUID,
        'edad',
        '["tengo", "años", "mi edad es"]'::JSONB,
        'number',
        'Edad del cliente'
    );
    
    SELECT add_contact_field(
        'project-inversiones-abc'::UUID,
        'direccion',
        '["vivo en", "mi dirección", "resido en", "domicilio"]'::JSONB,
        'string',
        'Dirección de residencia'
    );
    
    SELECT add_contact_field(
        'project-inversiones-abc'::UUID,
        'ha_invertido',
        '["he invertido", "invirtiendo", "experiencia en bolsa", "broker"]'::JSONB,
        'boolean',
        'Experiencia previa en inversiones'
    );
    
    SELECT add_contact_field(
        'project-inversiones-abc'::UUID,
        'presupuesto',
        '["presupuesto", "capital", "dispongo", "millones", "puedo invertir"]'::JSONB,
        'number',
        'Capital disponible para invertir'
    );
    
    -- 2. Ver la configuración generada
    SELECT get_contact_field_config('project-inversiones-abc'::UUID);
    
    -- 3. Deshabilitar un campo si es necesario
    UPDATE contact_field_configs 
    SET enabled = false 
    WHERE project_id = 'project-inversiones-abc' AND field_name = 'direccion';
    """
    
    print("Ejecutar en la base de datos:")
    print(sql_ejemplos)

# ===============================================================================
# EJEMPLO 3: USO DIRECTO DE LAS FUNCIONES ASYNC
# ===============================================================================

async def ejemplo_funciones_directas():
    """
    Muestra cómo usar las funciones async directamente para mayor control.
    """
    
    print("\n=== EJEMPLO 3: FUNCIONES DIRECTAS ===")
    
    project_id = "project-inversiones-abc"
    user_id = "user_67890"
    
    # Texto con información del usuario
    conversation_text = """
    Soy Carlos Martínez, carlos.martinez@gmail.com, tengo 42 años.
    Vivo en Providencia y nunca he invertido en bolsa, pero tengo 
    3 millones ahorrados que me gustaría invertir de forma conservadora.
    """
    
    print("Procesando conversación con configuración automática...")
    
    # Usar la función de extracción automática
    result = await auto_extract_fields_async(
        project_id, user_id, conversation_text
    )
    
    if result:
        print("✅ Campos extraídos y guardados automáticamente:")
        print(f"- Nombre: {result.get('name')}")
        print(f"- Email: {result.get('email')}")
        print(f"- Campos adicionales: {result.get('additional_fields', {})}")
    else:
        print("❌ No se pudieron extraer campos automáticamente")
    
    # Verificar el contacto guardado
    contact = await get_contact_async(project_id, user_id)
    if contact:
        print(f"\nContacto completo guardado: {contact}")

# ===============================================================================
# EJEMPLO 4: CONFIGURACIONES PREDEFINIDAS POR TIPO DE BOT
# ===============================================================================

def ejemplos_configuraciones_predefinidas():
    """
    Muestra configuraciones típicas para diferentes tipos de bots.
    """
    
    print("\n=== EJEMPLO 4: CONFIGURACIONES PREDEFINIDAS ===")
    
    configuraciones = {
        "bot_inversiones": {
            "edad": {"keywords": ["tengo", "años"], "type": "number"},
            "direccion": {"keywords": ["vivo en", "mi dirección"], "type": "string"},
            "ha_invertido": {"keywords": ["he invertido", "experiencia"], "type": "boolean"},
            "presupuesto": {"keywords": ["capital", "presupuesto", "millones"], "type": "number"},
            "tolerancia_riesgo": {"keywords": ["conservador", "agresivo", "moderado"], "type": "string"}
        },
        
        "bot_ecommerce": {
            "producto_interes": {"keywords": ["me interesa", "quiero", "busco"], "type": "string"},
            "presupuesto": {"keywords": ["presupuesto", "puedo pagar"], "type": "number"},
            "fecha_compra": {"keywords": ["para cuándo", "necesito"], "type": "string"},
            "metodo_pago": {"keywords": ["pago", "cuotas", "contado"], "type": "string"}
        },
        
        "bot_servicios": {
            "tipo_servicio": {"keywords": ["necesito", "servicio", "requiero"], "type": "string"},
            "urgencia": {"keywords": ["urgente", "pronto", "rápido"], "type": "string"},
            "presupuesto": {"keywords": ["presupuesto", "cuesta"], "type": "number"},
            "disponibilidad": {"keywords": ["disponible", "horario"], "type": "string"}
        }
    }
    
    for tipo_bot, config in configuraciones.items():
        print(f"\n--- Configuración para {tipo_bot.upper().replace('_', ' ')} ---")
        for campo, info in config.items():
            print(f"• {campo}: {info['keywords']} ({info['type']})")

# ===============================================================================
# EJEMPLO 5: COMPARACIÓN ANTES Y DESPUÉS
# ===============================================================================

async def ejemplo_comparacion():
    """
    Muestra la diferencia entre el método anterior y el nuevo método automático.
    """
    
    print("\n=== EJEMPLO 5: ANTES vs DESPUÉS ===")
    
    project_id = "project-test"
    user_id = "user_test"
    conversation_text = "Hola, tengo 28 años y vivo en Valparaíso"
    
    tool = SaveContactTool(project_id, user_id)
    
    print("❌ ANTES (método manual):")
    manual_config = """
    save_contact_tool(
        conversation_text="Hola, tengo 28 años y vivo en Valparaíso",
        field_config='{"edad": {"keywords": ["tengo", "años"], "type": "number"}, "ciudad": {"keywords": ["vivo en"], "type": "string"}}'
    )
    """
    print(manual_config)
    
    print("\n✅ DESPUÉS (método automático):")
    auto_config = """
    save_contact_tool(
        conversation_text="Hola, tengo 28 años y vivo en Valparaíso",
        auto_extract=true
    )
    """
    print(auto_config)
    
    print("\n📋 Beneficios del nuevo método:")
    print("• No necesitas especificar field_config manualmente")
    print("• La configuración se almacena en la BD por proyecto")  
    print("• Se puede modificar sin cambiar código")
    print("• Reutilizable para todas las conversaciones del proyecto")
    print("• Interfaz más simple para el LLM")

# ===============================================================================
# FUNCIÓN PRINCIPAL PARA EJECUTAR TODOS LOS EJEMPLOS
# ===============================================================================

async def main():
    """Ejecuta todos los ejemplos."""
    
    print("🤖 HERRAMIENTA DE CONTACTOS CON CONFIGURACIÓN AUTOMÁTICA")
    print("=" * 60)
    
    # Solo ejecutar ejemplos que no requieren BD real
    # await ejemplo_configuracion_automatica()  # Requiere BD
    await ejemplo_configurar_campos_proyecto()
    # await ejemplo_funciones_directas()  # Requiere BD
    ejemplos_configuraciones_predefinidas()
    await ejemplo_comparacion()
    
    print("\n" + "=" * 60)
    print("✅ Todos los ejemplos completados.")
    print("\n📝 PASOS SIGUIENTES:")
    print("1. Ejecutar create_contact_field_configs_table.sql en tu BD")
    print("2. Configurar campos para tu proyecto específico")
    print("3. Usar auto_extract=true en las conversaciones")
    print("4. ¡Disfrutar de la extracción automática! 🎉")

if __name__ == "__main__":
    asyncio.run(main()) 