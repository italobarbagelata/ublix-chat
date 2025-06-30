#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ejemplo de uso de Google Calendar LangChain Tool
================================================

Este archivo muestra cómo usar la nueva herramienta de Google Calendar
basada en LangChain CalendarToolkit en el contexto del proyecto ublix-chat.

Requisitos previos:
1. pip install langchain-google-community[calendar]
2. Configurar credentials.json en la raíz del proyecto
3. Habilitar la herramienta en enabled_tools del proyecto
"""

import asyncio
import logging
from datetime import datetime, timedelta
from app.controler.chat.core.tools.google_calendar_langchain_tool import GoogleCalendarLangChainTool

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ejemplo_completo_calendario():
    """
    Ejemplo completo que demuestra todas las funcionalidades
    de la herramienta Google Calendar LangChain
    """
    
    # Inicializar la herramienta con un project_id
    project_id = "ejemplo-project-123"
    calendar_tool = GoogleCalendarLangChainTool(project_id=project_id)
    
    print("🗓️ ===== EJEMPLO GOOGLE CALENDAR LANGCHAIN TOOL =====")
    print()
    
    # 1. Obtener fecha/hora actual
    print("1️⃣ Obteniendo fecha/hora actual...")
    resultado = calendar_tool._run(action="get_current_datetime")
    print(f"📅 Resultado: {resultado}")
    print()
    
    # 2. Obtener información de calendarios
    print("2️⃣ Obteniendo información de calendarios...")
    resultado = calendar_tool._run(action="get_calendars_info")
    print(f"📋 Resultado: {resultado}")
    print()
    
    # 3. Buscar eventos existentes
    print("3️⃣ Buscando eventos existentes...")
    hoy = datetime.now().strftime("%Y-%m-%d")
    manana = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    resultado = calendar_tool._run(
        action="search_events",
        query="reunión",
        start_date=hoy,
        end_date=manana,
        max_results=5
    )
    print(f"🔍 Eventos encontrados: {resultado}")
    print()
    
    # 4. Crear un nuevo evento
    print("4️⃣ Creando un nuevo evento...")
    
    # Calcular fechas para el evento (mañana a las 15:00)
    evento_fecha = datetime.now() + timedelta(days=1)
    inicio = evento_fecha.replace(hour=15, minute=0, second=0, microsecond=0)
    fin = inicio + timedelta(hours=1)
    
    resultado = calendar_tool._run(
        action="create_event",
        summary="🚀 Reunión Demo LangChain",
        start_datetime=inicio.isoformat(),
        end_datetime=fin.isoformat(),
        timezone="America/Santiago",
        location="Sala de Conferencias Virtual",
        description="Demostración de la nueva herramienta Google Calendar LangChain.\n\nAgenda:\n- Presentación de funcionalidades\n- Casos de uso prácticos\n- Q&A",
        attendees=["demo@ejemplo.com"],
        reminders=[
            {"method": "popup", "minutes": 30},
            {"method": "email", "minutes": 60}
        ],
        include_meet=True,
        color_id="2"  # Verde
    )
    print(f"✅ Evento creado: {resultado}")
    print()
    
    # 5. Buscar el evento recién creado
    print("5️⃣ Verificando evento creado...")
    resultado = calendar_tool._run(
        action="search_events",
        query="Demo LangChain",
        start_date=inicio.strftime("%Y-%m-%d"),
        end_date=fin.strftime("%Y-%m-%d")
    )
    print(f"🔍 Verificación: {resultado}")
    print()
    
    print("✨ ===== EJEMPLO COMPLETADO =====")

def ejemplo_casos_uso_practicos():
    """
    Ejemplos de casos de uso prácticos comunes
    """
    
    project_id = "mi-proyecto-real"
    calendar_tool = GoogleCalendarLangChainTool(project_id=project_id)
    
    print("🎯 ===== CASOS DE USO PRÁCTICOS =====")
    print()
    
    # Caso 1: Agendar reunión con cliente
    print("📞 CASO 1: Agendar reunión con cliente")
    
    # Datos del cliente (normalmente vendrían del chat)
    cliente_email = "cliente.importante@empresa.com"
    tema_reunion = "Presentación de Propuesta Comercial"
    
    # Crear evento
    manana_10am = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    fin_reunion = manana_10am + timedelta(hours=1, minutes=30)
    
    resultado = calendar_tool._run(
        action="create_event",
        summary=f"📊 {tema_reunion}",
        start_datetime=manana_10am.isoformat(),
        end_datetime=fin_reunion.isoformat(),
        timezone="America/Santiago",
        location="Sala Virtual - Google Meet",
        description=f"""
🎯 REUNIÓN: {tema_reunion}

📋 AGENDA:
• Presentación de propuesta
• Análisis de requerimientos
• Definición de próximos pasos
• Q&A

👤 ASISTENTES:
• Cliente: {cliente_email}
• Equipo comercial

📞 CONTACTO:
Para cualquier consulta, contactar al equipo de ventas.
        """.strip(),
        attendees=[cliente_email],
        reminders=[
            {"method": "popup", "minutes": 15},
            {"method": "email", "minutes": 60}
        ],
        include_meet=True,
        color_id="3"  # Púrpura para reuniones comerciales
    )
    print(f"✅ Reunión agendada: {resultado}")
    print()
    
    # Caso 2: Buscar disponibilidad para la próxima semana
    print("📅 CASO 2: Consultar disponibilidad próxima semana")
    
    proxima_semana_inicio = datetime.now() + timedelta(days=7)
    proxima_semana_fin = proxima_semana_inicio + timedelta(days=7)
    
    resultado = calendar_tool._run(
        action="search_events",
        start_date=proxima_semana_inicio.strftime("%Y-%m-%d"),
        end_date=proxima_semana_fin.strftime("%Y-%m-%d"),
        max_results=20
    )
    print(f"📊 Eventos próxima semana: {resultado}")
    print()
    
    # Caso 3: Crear recordatorio personal
    print("⏰ CASO 3: Crear recordatorio personal")
    
    recordatorio_fecha = datetime.now() + timedelta(days=3)
    recordatorio_fecha = recordatorio_fecha.replace(hour=9, minute=0, second=0, microsecond=0)
    recordatorio_fin = recordatorio_fecha + timedelta(minutes=30)
    
    resultado = calendar_tool._run(
        action="create_event",
        summary="🔔 Revisar métricas semanales",
        start_datetime=recordatorio_fecha.isoformat(),
        end_datetime=recordatorio_fin.isoformat(),
        timezone="America/Santiago",
        description="""
📊 REVISIÓN SEMANAL DE MÉTRICAS

✅ TAREAS:
• Analizar KPIs de la semana
• Revisar engagement del bot
• Generar reporte para equipo
• Planificar mejoras

📈 MÉTRICAS A REVISAR:
• Conversaciones completadas
• Satisfacción del usuario
• Tiempo de respuesta
• Casos escalados
        """.strip(),
        reminders=[
            {"method": "popup", "minutes": 10}
        ],
        include_meet=False,
        color_id="5"  # Amarillo para recordatorios
    )
    print(f"⏰ Recordatorio creado: {resultado}")
    print()
    
    print("✨ ===== CASOS DE USO COMPLETADOS =====")

def ejemplo_integracion_con_chat():
    """
    Ejemplo de cómo la herramienta se integraría en un flujo de chat real
    """
    
    print("💬 ===== INTEGRACIÓN CON CHAT =====")
    print()
    
    # Simular contexto de chat
    project_id = "chat-bot-project"
    user_message = "Quiero agendar una reunión para mañana a las 2 PM"
    contact_email = "usuario@ejemplo.com"
    
    calendar_tool = GoogleCalendarLangChainTool(project_id=project_id)
    
    # 1. Extraer información del mensaje (esto normalmente lo haría el LLM)
    print("1️⃣ Procesando solicitud del usuario...")
    print(f"💬 Usuario dice: '{user_message}'")
    print(f"📧 Email del contacto: {contact_email}")
    print()
    
    # 2. Verificar disponibilidad
    print("2️⃣ Verificando disponibilidad...")
    manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    resultado = calendar_tool._run(
        action="search_events",
        start_date=manana,
        end_date=manana,
        max_results=10
    )
    print(f"📅 Eventos del día: {resultado}")
    print()
    
    # 3. Crear el evento
    print("3️⃣ Creando evento solicitado...")
    
    evento_inicio = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    evento_fin = evento_inicio + timedelta(hours=1)
    
    resultado = calendar_tool._run(
        action="create_event",
        summary="🤝 Reunión solicitada por chat",
        start_datetime=evento_inicio.isoformat(),
        end_datetime=evento_fin.isoformat(),
        timezone="America/Santiago",
        description=f"""
📞 REUNIÓN AGENDADA VÍA CHATBOT

👤 SOLICITANTE: {contact_email}
💬 SOLICITUD ORIGINAL: "{user_message}"
🕐 HORARIO: {evento_inicio.strftime('%d/%m/%Y a las %H:%M')}

📋 DETALLES:
• Reunión agendada automáticamente
• Confirmación enviada al email del contacto
• Google Meet incluido automáticamente
        """.strip(),
        attendees=[contact_email],
        reminders=[{"method": "popup", "minutes": 30}],
        include_meet=True,
        color_id="4"  # Rosa para reuniones desde chat
    )
    
    print(f"✅ Evento creado exitosamente: {resultado}")
    print()
    
    # 4. Respuesta al usuario
    respuesta_chat = f"""
🎉 ¡Perfecto! He agendado tu reunión para mañana {evento_inicio.strftime('%d/%m/%Y a las %H:%M')}.

📧 Recibirás una invitación de calendario en {contact_email}
📞 La reunión incluye Google Meet automáticamente
⏰ Te recordaré 30 minutos antes

¿Hay algo más en lo que pueda ayudarte?
    """.strip()
    
    print("4️⃣ Respuesta al usuario:")
    print(respuesta_chat)
    print()
    
    print("✨ ===== INTEGRACIÓN COMPLETADA =====")

if __name__ == "__main__":
    """
    Ejecutar ejemplos
    """
    
    print("🚀 INICIANDO EJEMPLOS DE GOOGLE CALENDAR LANGCHAIN TOOL")
    print("=" * 60)
    print()
    
    try:
        # Ejecutar ejemplo completo
        asyncio.run(ejemplo_completo_calendario())
        print("\n" + "=" * 60 + "\n")
        
        # Ejecutar casos de uso prácticos
        ejemplo_casos_uso_practicos()
        print("\n" + "=" * 60 + "\n")
        
        # Ejecutar ejemplo de integración con chat
        ejemplo_integracion_con_chat()
        
    except Exception as e:
        logger.error(f"❌ Error en ejemplos: {str(e)}")
        print("\n🔧 NOTAS PARA SOLUCIÓN DE PROBLEMAS:")
        print("1. Verificar que langchain-google-community[calendar] esté instalado")
        print("2. Verificar que credentials.json esté configurado")
        print("3. Verificar que la herramienta esté habilitada en enabled_tools")
        print("4. Verificar conectividad a internet")
    
    print("\n🎯 EJEMPLOS COMPLETADOS") 