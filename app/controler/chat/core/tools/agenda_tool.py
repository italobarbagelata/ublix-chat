import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from langchain.tools import BaseTool
import pytz

from app.controler.chat.core.tools.calendar_tool import google_calendar_tool
from app.controler.chat.core.tools.email_tool import EmailTool, send_email_async
from app.controler.chat.store.supabase_client import SupabaseClient
from app.controler.chat.core.services.appointment_orchestrator import AppointmentOrchestrator

logger = logging.getLogger(__name__)

class AgendaTool(BaseTool):
    name: str = "agenda_tool"
    description: str = """
    🗓️ HERRAMIENTA PROFESIONAL DE AGENDAMIENTO Y HORARIOS (agenda_tool) 🗓️

    FUNCIONALIDAD PRINCIPAL:
    - Conexión directa y validación en tiempo real con Google Calendar.
    - Gestión completa de agendamiento: creación, actualización, cancelación y consulta de horarios.
    - Confirmaciones automáticas y notificaciones por email (cliente y dueño del proyecto).
    - Inclusión automática de Google Meet en reuniones virtuales.
    - Validación estricta de disponibilidad y detección de conflictos antes de mostrar o agendar horarios.

    🚨 REGLAS CRÍTICAS:
    - **SIEMPRE que el usuario pregunte por disponibilidad de horarios (ej. '¿y más tarde?', '¿tienes en la tarde?'), DEBES usar el workflow `BUSQUEDA_HORARIOS`. NO respondas basándote en la lista de horarios anterior.**
    - SIEMPRE verificar disponibilidad REAL contra Google Calendar antes de mostrar/agendar.
    - NUNCA mostrar horarios ocupados o inventados.
    - Si no hay horarios libres, informar claramente la falta de disponibilidad.
    - Esta es la ÚNICA fuente autorizada para mostrar horarios.

    ⚡ WORKFLOWS DISPONIBLES:
    1. BUSQUEDA_HORARIOS
       - **Uso**: Para buscar horarios disponibles. Úsalo para la pregunta inicial (ej. "quiero agendar el miércoles") y para preguntas de seguimiento (ej. "¿y por la tarde?", "¿tienes algo más temprano?", "¿y la próxima semana?").
       - **Ejemplo**: `agenda_tool(workflow_type="BUSQUEDA_HORARIOS", title="y para la tarde?")`
       - **Resultado**: Devuelve una lista de horarios 100% reales y validados en el calendario.
    2. AGENDA_COMPLETA
       agenda_tool(workflow_type="AGENDA_COMPLETA", title="reunión", start_datetime="YYYY-MM-DDTHH:MM:SS", attendee_email="cliente@email.com")
       → Agenda un evento, valida disponibilidad, envía confirmaciones y notifica.
    3. ACTUALIZACION_COMPLETA
       agenda_tool(workflow_type="ACTUALIZACION_COMPLETA", event_id="...", ...)
       → Modifica eventos existentes.
    4. CANCELACION_WORKFLOW
       agenda_tool(workflow_type="CANCELACION_WORKFLOW", event_id="...")
       → Cancela eventos y notifica.
    5. COMUNICACION_EVENTO
       agenda_tool(workflow_type="COMUNICACION_EVENTO", event_id="...")
       → Consulta detalles de un evento.

    PARÁMETROS PRINCIPALES:
    - workflow_type: str (obligatorio) — Tipo de operación.
    - title: str — Descripción o motivo de la cita.
    - start_datetime: str (ISO) — Fecha/hora de inicio (para agendar).
    - end_datetime: str (ISO) — Fecha/hora de fin (opcional).
    - attendee_email: str — Email del cliente (para agendar).
    - attendee_name: str — Nombre del cliente (opcional).
    - attendee_phone: str — Teléfono del cliente (opcional).
    - description: str — Descripción adicional (opcional).
    - event_id: str — ID del evento (para actualizar/cancelar/consultar).
    - conversation_summary: str — Resumen de la conversación (opcional, para webhooks).

    NOTAS:
    - Solo muestra y agenda horarios 100% libres y confirmados.
    - Si falta información crítica, la herramienta lo indicará claramente.
    - El comportamiento es asíncrono y seguro para producción.

    Para más detalles, consulta la documentación del proyecto.
    """
    
    def __init__(self, project_id: str = None, project=None, user_id: str = None, **kwargs):
        super().__init__(**kwargs)
        self._project_id = project_id
        self._project = project
        self._user_id = user_id
        self._email_tool = EmailTool()
        self._supabase_client = SupabaseClient()
        self._cached_project_config = None
        self._orchestrator = None  # Se inicializa cuando se carga la configuración
        
    @property
    def project_id(self):
        return getattr(self, '_project_id', None)
    
    @property 
    def project(self):
        return getattr(self, '_project', None)
    
    @property
    def user_id(self):
        return getattr(self, '_user_id', None)
    
    @property
    def email_tool(self):
        return getattr(self, '_email_tool', None)
        
    @property
    def supabase_client(self):
        return getattr(self, '_supabase_client', None)
    
    @property
    def orchestrator(self):
        """Obtiene el orchestrator, inicializándolo si es necesario"""
        if not self._orchestrator and self._cached_project_config:
            self._orchestrator = AppointmentOrchestrator(
                cached_project_config=self._cached_project_config,
                project_id=self.project_id
            )
        return self._orchestrator
        
    class Config:
        arbitrary_types_allowed = True
    
    # 🚀 MÉTODOS DELEGADOS AL ORCHESTRATOR
    
    def _validate_specific_day_request(self, day_requested: str, workflow_settings: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida si un día específico está disponible (delegado al orchestrator)"""
        if not self.orchestrator:
            return False, "❌ Error: Orchestrator no disponible"
        return self.orchestrator.validate_specific_day_availability(day_requested, workflow_settings)
    
    def _get_available_schedule_summary(self, workflow_settings: Dict[str, Any]) -> str:
        """Genera un resumen de los horarios disponibles (delegado al orchestrator)"""
        if not self.orchestrator:
            return "❌ Error: Orchestrator no disponible"
        return self.orchestrator.get_available_schedule_summary(workflow_settings)
    
    def _extract_day_from_text(self, text: str) -> Optional[str]:
        """Extrae el nombre del día del texto (delegado al orchestrator)"""
        if not self.orchestrator:
            return None
        return self.orchestrator.extract_day_from_request(text)
    
    async def _get_project_config(self) -> Dict[str, Any]:
        """Obtiene configuración completa del proyecto desde tabla agenda en Supabase"""
        try:
            if not self.project_id:
                logger.error("⚠️ No se proporcionó project_id - requerido para workflow orchestrator")
                return None
            
            # Consultar tabla agenda con project_id
            response = self.supabase_client.client.table("agenda").select("*").eq("project_id", self.project_id).execute()
            
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
                logger.info(f"✅ Configuración de agenda obtenida para project_id: {self.project_id}")
                
                # Validar campos críticos de la tabla agenda
                required_fields = ["email_templates", "workflow_settings", "general_settings"]
                missing_fields = [field for field in required_fields if not agenda_config.get(field)]
                if missing_fields:
                    logger.warning(f"⚠️ Campos faltantes en configuración de agenda: {missing_fields}")
                
                # Log de configuración obtenida para debug
                logger.info(f"📋 Email templates disponibles: {bool(agenda_config.get('email_templates'))}")
                logger.info(f"📋 Workflow settings disponibles: {bool(agenda_config.get('workflow_settings'))}")
                logger.info(f"📋 General settings disponibles: {bool(agenda_config.get('general_settings'))}")
                logger.info(f"📧 Owner email: {agenda_config.get('owner_email', 'No configurado')}")
                
                # 🚀 INICIALIZAR ORCHESTRATOR con configuración cargada
                self._cached_project_config = agenda_config
                self._orchestrator = AppointmentOrchestrator(
                    cached_project_config=agenda_config,
                    project_id=self.project_id
                )
                logger.info("✅ Orchestrator inicializado con configuración del proyecto")
                
                return agenda_config
            else:
                logger.error(f"❌ No se encontró configuración de agenda para project_id: {self.project_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo configuración de agenda: {str(e)}")
            return None
    
    async def _get_email_template_from_config(self) -> Dict[str, str]:
        """Extrae template de email desde configuración del proyecto (template único)"""
        try:
            if not self._cached_project_config:
                logger.error("❌ No hay configuración cached del proyecto")
                return None
                
            email_templates = self._cached_project_config.get("email_templates", {})
            
            # Buscar el template único (puede estar como objeto directo o con clave específica)
            if isinstance(email_templates, dict):
                # Si hay un template directo con subject y content
                if "subject" in email_templates and "content" in email_templates:
                    logger.info(f"✅ Template único encontrado para {self._cached_project_config.get('name', 'proyecto')}")
                    return {
                        "subject": email_templates.get("subject", "Confirmación de Reunión"),
                        "content": email_templates.get("content", "")
                    }
                # Si hay templates con claves, usar el primero disponible (confirmacion, etc.)
                elif email_templates:
                    template_keys = ["confirmacion", "confirmation", "default"]
                    for key in template_keys:
                        if key in email_templates:
                            template = email_templates[key]
                            logger.info(f"✅ Template '{key}' encontrado para {self._cached_project_config.get('name', 'proyecto')}")
                            return {
                                "subject": template.get("subject", f"Confirmación de Reunión"),
                                "content": template.get("content", "")
                            }
                    
                    # Si no hay claves específicas, usar el primer template disponible
                    first_key = list(email_templates.keys())[0]
                    template = email_templates[first_key]
                    logger.info(f"✅ Usando primer template disponible '{first_key}' para {self._cached_project_config.get('name', 'proyecto')}")
                    return {
                        "subject": template.get("subject", f"Confirmación de Reunión"),
                        "content": template.get("content", "")
                    }
                else:
                    logger.error(f"❌ No se encontraron templates de email en la configuración")
                    return None
            else:
                logger.error(f"❌ Formato incorrecto de email_templates en la configuración")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error extrayendo template de email: {str(e)}")
            return None
    
    async def _arun(
        self,
        workflow_type: str,
        title: Optional[str] = None,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        attendee_email: Optional[str] = None,
        attendee_name: Optional[str] = None,
        attendee_phone: Optional[str] = None,
        description: Optional[str] = None,
        event_id: Optional[str] = None,
        include_meet: Optional[bool] = None,
        conversation_summary: Optional[str] = None,
        additional_fields: Optional[Dict[str, Any]] = None
    ) -> str:
        """Ejecuta el workflow especificado con configuración optimizada"""
        try:
            logger.info(f"🚀 Iniciando workflow: {workflow_type} para proyecto: {self.project_id}")
            workflow_type = workflow_type.upper()

            # 🚨 VALIDACIONES CRÍTICAS SOLO PARA AGENDA_COMPLETA
            if workflow_type == "AGENDA_COMPLETA":
                validation_errors = []
                # Validar datos obligatorios para agendamiento
                if not start_datetime or start_datetime.strip() == "":
                    validation_errors.append("📅 Fecha y hora de la cita")
                
                # Si faltan datos críticos, devolver error específico
                if validation_errors:
                    missing_data = ", ".join(validation_errors)
                    error_message = f"❌ **No se puede agendar - Falta un dato obligatorio:**\n\n{missing_data}"
                    logger.warning(f"❌ AGENDA_COMPLETA bloqueado - Faltan datos: {missing_data}")
                    return error_message
                
                # Validar formato de email solo si se proporciona
                if attendee_email and attendee_email.strip():
                    import re
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    if not re.match(email_pattern, attendee_email.strip()):
                        logger.warning(f"❌ Email inválido detectado: {attendee_email}")
                        return f"❌ **Email inválido:** '{attendee_email}'\n\n💡 Por favor proporciona un email válido (ejemplo: nombre@dominio.com)"

                logger.info(f"✅ Validaciones AGENDA_COMPLETA pasadas - Email: {attendee_email or 'No proporcionado'}")
                return await self._agenda_completa_workflow(
                    title, start_datetime, end_datetime, attendee_email, attendee_name, attendee_phone,
                    description, include_meet, conversation_summary, additional_fields
                )
            elif workflow_type == "COMUNICACION_EVENTO":
                return await self._comunicacion_evento_workflow(event_id)
            elif workflow_type == "ACTUALIZACION_COMPLETA":
                return await self._actualizacion_completa_workflow(event_id, title, start_datetime, end_datetime)
            elif workflow_type == "CANCELACION_WORKFLOW":
                return await self._cancelacion_workflow(event_id)
            elif workflow_type == "BUSQUEDA_HORARIOS":
                # ⚠️ IMPORTANTE: NO VALIDAR DATOS PERSONALES EN BUSQUEDA_HORARIOS
                # La búsqueda de horarios debe funcionar aunque falten datos personales
                logger.info("🔍 Ejecutando BUSQUEDA_HORARIOS - No requiere validaciones de datos personales")
                return await self._busqueda_horarios_workflow(title, start_datetime, end_datetime, conversation_summary)
            else:
                available_workflows = ["AGENDA_COMPLETA", "BUSQUEDA_HORARIOS", "COMUNICACION_EVENTO", "ACTUALIZACION_COMPLETA", "CANCELACION_WORKFLOW"]
                return f"❌ Error: Workflow '{workflow_type}' no reconocido. Disponibles: {', '.join(available_workflows)}"
        except Exception as e:
            logger.error(f"❌ Error crítico en workflow orchestrator: {str(e)}")
            return f"❌ Error ejecutando workflow {workflow_type}: {str(e)}"
    
    async def _agenda_completa_workflow(
        self, title: str, start_datetime: str, end_datetime: str, 
        attendee_email: str, attendee_name: str, attendee_phone: str, description: str, include_meet: bool, 
        conversation_summary: str = None, additional_fields: Optional[Dict[str, Any]] = None
    ) -> str:
        """Workflow completo de agendamiento OPTIMIZADO con validaciones granulares"""
        try:
            logger.info("🚀 Iniciando workflow AGENDA_COMPLETA OPTIMIZADO con validaciones granulares...")
            
            # ✅ PASO 0.1: VALIDAR CONSISTENCIA DE FECHAS SI SE PROPORCIONA FECHA EN TITLE
            if title and not start_datetime:
                es_consistente, mensaje_validacion, fecha_corregida = self._validate_date_consistency(title)
                if not es_consistente:
                    logger.warning(f"❌ Inconsistencia de fecha detectada en title: {mensaje_validacion}")
                    return mensaje_validacion
                
                if fecha_corregida:
                    logger.info(f"✅ Fecha específica extraída y validada desde title: {fecha_corregida}")
                    # Convertir fecha a datetime con hora por defecto
                    start_datetime = f"{fecha_corregida}T15:00:00"  # 3 PM por defecto
            
            # PASO 0: Obtener configuración de agenda (una sola consulta)
            self._cached_project_config = await self._get_project_config()
            
            if not self._cached_project_config:
                return "❌ Error crítico: No se pudo obtener configuración de agenda. Verificar project_id en tabla agenda de Supabase."
            
            # Para logs, obtener información del proyecto desde general_settings
            general_settings = self._cached_project_config.get("general_settings", {})
            project_name = general_settings.get("company_info", {}).get("name", f"Proyecto {self.project_id}")
            logger.info(f"📋 Procesando agendamiento para: {project_name}")
            
            # PASO 0.1: VALIDACIONES GRANULARES DE HORARIOS
            workflow_settings = self._cached_project_config.get("workflow_settings", {})
            granular_schedule = self._parse_granular_schedule(workflow_settings)
            
            # Validar fecha y hora si se proporciona start_datetime
            if start_datetime:
                try:
                    # Parsear datetime con timezone
                    chile_tz = pytz.timezone("America/Santiago")
                    
                    # 1. Parsear la fecha desde el string
                    naive_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
                    
                    # 2. Asignar la zona horaria de Chile
                    target_dt = chile_tz.localize(naive_dt)

                    # Validar horarios laborales
                    is_valid, validation_message = self._is_time_in_working_hours(granular_schedule, target_dt)
                    
                    if not is_valid:
                        logger.warning(f"⚠️ Horario fuera de configuración granular: {validation_message}")
                        # En lugar de derivar, devolvemos el error directamente para mayor control
                        return validation_message
                    
                    logger.info(f"✅ Horario validado: {validation_message}")
                    
                except Exception as e:
                    logger.error(f"❌ Error validando horarios granulares: {str(e)}")
                    # Continuar sin validación granular en caso de error
            
            # PASO 0.2: Usar title_calendar_email si no se proporciona título específico
            if not title or title == "Reunión":
                title_from_config = general_settings.get("title_calendar_email", "Llamada Maricunga")
                if title_from_config:
                    title = title_from_config
                    logger.info(f"📝 Usando título desde configuración de agenda: {title}")
            
            # PASO 1: Crear evento en calendario (CRÍTICO - ESPERAR)
            logger.info("🗓️ Creando evento en Google Calendar...")
            calendar_query = self._generate_calendar_query(
                "create_event", title, start_datetime, end_datetime, 
                attendee_email, description, include_meet
            )
            
            # Pasar configuración completa para evitar consulta duplicada
            workflow_settings = self._cached_project_config.get("workflow_settings", {})
            granular_schedule = self._parse_granular_schedule(workflow_settings)
            enhanced_project_config = {
                'project_id': self.project_id,
                'workflow_settings': workflow_settings,
                'granular_schedule': granular_schedule
            }
            
            mock_state = {"project": self.project, "agenda_config": enhanced_project_config}
            calendar_result = google_calendar_tool.invoke({"query": calendar_query, "state": mock_state})
            
            # 🚨 VERIFICACIÓN MEJORADA DE ERRORES Y CONFLICTOS
            if "Error" in calendar_result or "CONFLICTO DETECTADO" in calendar_result or "⚠️" in calendar_result:
                logger.error(f"❌ Error o conflicto detectado en calendario: {calendar_result}")
                return f"❌ No se pudo crear el evento: {calendar_result}"
            
            logger.info(f"✅ Evento creado exitosamente en calendario: {title}")
            
            # PASO 1.5: Extraer URL de Google Meet de la respuesta
            meet_url = self._extract_meet_url(calendar_result)
            logger.info(f"🔗 URL de Meet extraída: {meet_url}")
            
            # PASO 2: RESPUESTA INMEDIATA AL USUARIO
            # Generar respuesta optimizada para el usuario
            import datetime as dt
            try:
                parsed_date = dt.datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
                formatted_date = parsed_date.strftime("%d de %B de %Y a las %H:%M")
                formatted_date = formatted_date.replace("January", "enero").replace("February", "febrero").replace("March", "marzo").replace("April", "abril").replace("May", "mayo").replace("June", "junio").replace("July", "julio").replace("August", "agosto").replace("September", "septiembre").replace("October", "octubre").replace("November", "noviembre").replace("December", "diciembre")
            except:
                formatted_date = start_datetime

            # 🆕 CONSTRUCCIÓN DE RESPUESTA CONDICIONAL
            # Generar sección de Meet solo si existe la URL
            meet_response_section = ""
            if meet_url:
                meet_response_section = f"\n\nLa reunión incluirá un enlace de Google Meet para que puedas unirte virtualmente."
            else:
                # Si no hay Meet, indicar que no es una reunión virtual
                meet_response_section = "\n\nEsta es una reunión presencial y no incluye un enlace de videollamada."

            # Construir respuesta final usando la sección condicional
            immediate_response = f"""✅ ¡Listo! Tu cita ha sido agendada para el **{formatted_date}**.

📧 Te enviaremos un correo de confirmación a **{attendee_email}** con todos los detalles.{meet_response_section}

¡Nos vemos pronto! 😊"""
            
            # PASO 3: EJECUTAR EN BACKGROUND (emails + webhook)
            # Lanzar task en background sin esperar
            asyncio.create_task(self._execute_background_notifications(
                title, start_datetime, end_datetime, attendee_email, attendee_name, attendee_phone, description, 
                conversation_summary, meet_url, additional_fields
            ))
            
            logger.info("🚀 Respuesta inmediata enviada - Background tasks iniciados")
            return immediate_response
            
        except Exception as e:
            logger.error(f"❌ Error crítico en agenda_completa_workflow: {str(e)}")
            return f"❌ Error en workflow de agendamiento: {str(e)}"
    
    async def _execute_background_notifications(
        self, title: str, start_datetime: str, end_datetime: str, 
        attendee_email: str, attendee_name: str, attendee_phone: str, description: str, 
        conversation_summary: str, meet_url: str = None, additional_fields: Optional[Dict[str, Any]] = None
    ):
        """Ejecuta notificaciones en segundo plano sin bloquear respuesta"""
        try:
            logger.info("📧 Iniciando notificaciones en background...")
            background_results = []
            
            # BACKGROUND TASK 1: Email al cliente
            if attendee_email:
                logger.info(f"📧 [Background] Enviando email a cliente: {attendee_email}")
                
                email_subject, email_content = await self._generate_email_content(
                    title, start_datetime, end_datetime, attendee_name, attendee_phone, description, meet_url
                )
                
                if email_subject and email_content:
                    company_info = self._cached_project_config.get("general_settings", {}).get("company_info", {})
                    company_name = company_info.get("name", "")
                    from_email_with_name = f"{company_name} <noreply@ublix.app>"
                    
                    email_result = await send_email_async(
                        from_email=from_email_with_name,
                        to=attendee_email,
                        subject=email_subject,
                        html=email_content
                    )
                    
                    if email_result.get("success"):
                        logger.info(f"✅ [Background] Email de confirmación enviado a {attendee_email}")
                    else:
                        logger.error(f"⚠️ [Background] Error enviando email: {email_result.get('error', 'Error desconocido')}")
            
            # BACKGROUND TASK 2: Email al dueño
            project_owner_email = self._get_owner_email()
            if project_owner_email:
                logger.info(f"📧 [Background] Enviando notificación a dueño: {project_owner_email}")
                
                # Construir link de conversación con verificación de seguridad
                if self.user_id:
                    link_conversation = f"https://ublix.app/projects/{self.project.id}/conversations/{self.user_id}"
                else:
                    link_conversation = f"https://ublix.app/projects/{self.project.id}"
                    logger.warning("⚠️ user_id no disponible, usando link de proyecto")
                
                owner_subject, owner_content = self._generate_owner_notification(
                    title, start_datetime, end_datetime, attendee_email, attendee_name, attendee_phone, description, link_conversation
                )
                
                owner_email_result = await send_email_async(
                    from_email="Agenda <noreply@ublix.app>",
                    to=project_owner_email,
                    subject=owner_subject,
                    html=owner_content
                )
                
                if owner_email_result.get("success"):
                    logger.info(f"✅ [Background] Notificación enviada al dueño del proyecto")
                else:
                    logger.error(f"❌ [Background] Error notificando al dueño: {owner_email_result.get('error', 'Error desconocido')}")
            
            # BACKGROUND TASK 3: Webhook
            logger.info(f"🔍 [Background] Debug conversation_summary recibido: {conversation_summary}")
            webhook_result = await self._send_webhook_notification(
                title, start_datetime, end_datetime, attendee_email, attendee_name, attendee_phone, description, 
                conversation_summary, meet_url, additional_fields
            )
            if webhook_result:
                logger.info(f"✅ [Background] {webhook_result}")
            
            logger.info("🎉 [Background] Todas las notificaciones completadas exitosamente")
            
        except Exception as e:
            logger.error(f"❌ [Background] Error en notificaciones background: {str(e)}")
    
    async def _comunicacion_evento_workflow(self, event_id: str) -> str:
        """Workflow de comunicación sobre eventos existentes"""
        try:
            # Pasar configuración básica (no requiere granular para get_event)
            basic_config = {
                'project_id': self.project_id,
                'cached_agenda_data': self._cached_project_config  # ✅ Evitar consulta duplicada
            }
            mock_state = {"project": self.project, "agenda_config": basic_config}
            
            # Obtener información del evento
            calendar_query = f"get_event|event_id={event_id}"
            event_info = google_calendar_tool.invoke({"query": calendar_query, "state": mock_state})
            
            if "Error" in event_info:
                return f"❌ Error obteniendo evento: {event_info}"
            
            return f"✅ Comunicación tipo 'comunicacion_evento' procesada para evento {event_id}"
            
        except Exception as e:
            logger.error(f"Error en comunicacion_evento_workflow: {str(e)}")
            return f"❌ Error en workflow de comunicación: {str(e)}"
    
    async def _actualizacion_completa_workflow(
        self, event_id: str, new_title: str, new_start: str, new_end: str
    ) -> str:
        """Workflow de actualización completa de eventos"""
        try:
            update_params = []
            if new_title:
                update_params.append(f"title={new_title}")
            if new_start:
                update_params.append(f"start={new_start}")
            if new_end:
                update_params.append(f"end={new_end}")
            
            if not update_params:
                return "❌ Error: No se especificaron cambios"
            
            update_query = f"update_event|event_id={event_id}|" + "|".join(update_params)
            
            # Pasar configuración básica (no requiere granular para update)
            basic_config = {
                'project_id': self.project_id,
                'cached_agenda_data': self._cached_project_config  # ✅ Evitar consulta duplicada
            }
            mock_state = {"project": self.project, "agenda_config": basic_config}
            update_result = google_calendar_tool.invoke({"query": update_query, "state": mock_state})
            
            if "Error" in update_result:
                return f"❌ Error actualizando evento: {update_result}"
            
            return f"✅ Evento {event_id} actualizado exitosamente"
            
        except Exception as e:
            logger.error(f"Error en actualizacion_completa_workflow: {str(e)}")
            return f"❌ Error en workflow de actualización: {str(e)}"
    
    async def _cancelacion_workflow(self, event_id: str) -> str:
        """Workflow de cancelación completa"""
        try:
            # Pasar configuración básica (no requiere granular para get/delete)
            basic_config = {
                'project_id': self.project_id,
                'cached_agenda_data': self._cached_project_config  # ✅ Evitar consulta duplicada
            }
            mock_state = {"project": self.project, "agenda_config": basic_config}
            
            # Obtener info del evento antes de eliminar
            event_info = google_calendar_tool.invoke({"query": f"get_event|event_id={event_id}", "state": mock_state})
            
            # Eliminar evento
            delete_result = google_calendar_tool.invoke({"query": f"delete_event|event_id={event_id}", "state": mock_state})
            
            if "Error" in delete_result:
                return f"❌ Error cancelando evento: {delete_result}"
            
            return f"✅ Evento {event_id} cancelado exitosamente"
            
        except Exception as e:
            logger.error(f"Error en cancelacion_workflow: {str(e)}")
            return f"❌ Error en workflow de cancelación: {str(e)}"
    
    async def _busqueda_horarios_workflow(
        self, title: str = None, start_datetime: str = None, end_datetime: str = None, conversation_summary: str = None
    ) -> str:
        """Workflow de búsqueda de horarios con validaciones granulares
        - Si el usuario solicita un día específico, solo se muestran los slots de ese día (hasta el límite).
        - Si el usuario cambia de día, se limpia la lista y se buscan los slots solo para ese nuevo día.
        - Si no hay día solicitado, se buscan los próximos N slots disponibles (comportamiento general).
        """
        try:
            logger.info("🔍 Iniciando búsqueda con validaciones granulares...")
            
            # PASO 0: Usar el conversation_summary para enriquecer el `title` si está disponible
            full_query_text = title
            if conversation_summary:
                logger.info(f"💬 Usando conversation_summary para enriquecer la búsqueda: '{conversation_summary}'")
                # Combinar el título actual (ej: "tarde") con el resumen
                full_query_text = f"{title or ''} {conversation_summary}"

            # 🆕 PASO 0.5: DETECTAR HORA ESPECÍFICA ANTES DE TODO
            specific_time_query = self._extract_specific_time(full_query_text)

            # PASO 1: DETECTAR FECHAS ESPECÍFICAS PRIMERO (con o sin día de semana)
            if full_query_text:
                # Primero intentar detectar fecha específica directamente
                fecha_detectada = self._detect_specific_day(full_query_text)
                if fecha_detectada:
                    logger.info(f"🗓️ Fecha específica detectada directamente: {fecha_detectada}")
                    # Validar que el día de esa fecha esté habilitado
                    try:
                        date_obj = datetime.strptime(fecha_detectada[:10], "%Y-%m-%d")
                        day_names_eng = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                        day_eng = day_names_eng[date_obj.weekday()]
                        
                        # Obtener configuración granular temporal para validación
                        temp_config = await self._get_project_config() if not self._cached_project_config else self._cached_project_config
                        temp_workflow_settings = temp_config.get("workflow_settings", {}) if temp_config else {}
                        temp_granular_schedule = self._parse_granular_schedule(temp_workflow_settings)
                        
                        if not self._is_day_enabled(temp_granular_schedule, day_eng):
                            dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                            day_name = dias_semana[date_obj.weekday()]
                            available_info = self._get_available_schedule_summary(temp_granular_schedule)
                            return f"""❌ **No trabajo los {day_name}s**\n\n📅 **Mis horarios disponibles:**\n{available_info}\n\n💡 Prueba preguntando por alguno de los días disponibles"""
                        
                        start_datetime = fecha_detectada
                        logger.info(f"✅ Fecha específica validada y habilitada: {fecha_detectada}")
                    except Exception as e:
                        logger.error(f"Error validando fecha detectada: {str(e)}")
                        # Continuar con validación de consistencia como fallback
                else:
                    # Si no hay fecha específica, validar consistencia día+fecha
                    es_consistente, mensaje_validacion, fecha_corregida = self._validate_date_consistency(full_query_text)
                    if not es_consistente:
                        logger.warning(f"❌ Inconsistencia de fecha detectada: {mensaje_validacion}")
                        return mensaje_validacion
                    if fecha_corregida:
                        logger.info(f"✅ Fecha específica validada: {fecha_corregida}")
                        start_datetime = fecha_corregida

            if not self._cached_project_config:
                self._cached_project_config = await self._get_project_config()
            
            workflow_settings = self._cached_project_config.get("workflow_settings", {}) if self._cached_project_config else {}
            granular_schedule = self._parse_granular_schedule(workflow_settings)
            busqueda_settings = workflow_settings.get("BUSQUEDA_HORARIOS", {})
            max_slots_to_show = busqueda_settings.get("max_slots_to_show", 3)  # Default 3 si no está configurado
            general_settings = self._cached_project_config.get("general_settings", {}) if self._cached_project_config else {}
            project_name = general_settings.get("company_info", {}).get("name", f"tu proyecto {self.project_id}")
            
            day_filter = None
            week_offset = 0
            
            # Extraer preferencias de hora (mañana/tarde)
            time_prefs = self._extract_time_preferences(title)

            if start_datetime:
                day_filter = start_datetime
                logger.info(f"🗓️ Fecha específica confirmada: {start_datetime}")
            elif full_query_text:
                if any(phrase in full_query_text.lower() for phrase in ["próxima semana", "proxima semana", "la próxima semana", "la proxima semana"]):
                    logger.info(f"🎯 Detectado 'próxima semana' - búsqueda general con offset")
                    week_offset = 1
                    day_filter = None
                else:
                    day_requested = self._extract_day_from_text(full_query_text)
                    if day_requested:
                        logger.info(f"🗓️ Día detectado en consulta: '{full_query_text}' → {day_requested}")
                        is_valid, validation_message = self._validate_specific_day_request(day_requested, granular_schedule)
                        if not is_valid:
                            logger.warning(f"⚠️ Día solicitado no disponible: {validation_message}")
                            available_info = self._get_available_schedule_summary(granular_schedule)
                            return f"""❌ **Día no disponible**\n\n{validation_message}\n\n📅 **Mis horarios disponibles:**\n{available_info}\n\n💡 **Sugerencia:** Prueba preguntando por alguno de los días disponibles"""
                        logger.info(f"✅ Día validado: {validation_message}")
                        day_filter = self._detect_specific_day(full_query_text)
            
            # --- Construcción de la query para calendar_tool ---
            query_parts = ["find_available_slots", "duration=1", f"limit={max_slots_to_show}"]
            
            # Si hay filtro de día específico (YYYY-MM-DD)
            if day_filter:
                try:
                    date_obj = datetime.strptime(day_filter[:10], "%Y-%m-%d")
                    dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                    day_name = dias_semana[date_obj.weekday()]
                    day_names_eng = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                    day_eng = day_names_eng[date_obj.weekday()]
                    
                    if not self._is_day_enabled(granular_schedule, day_eng):
                        available_info = self._get_available_schedule_summary(granular_schedule)
                        return f"""❌ **No trabajo los {day_name}s**\n\n📅 **Mis horarios disponibles:**\n{available_info}\n\n💡 Prueba preguntando por alguno de los días disponibles"""
                    
                    query_parts.append(f"specific_date={day_filter}")
                    logger.info(f"🎯 Búsqueda SOLO para fecha específica: {day_filter} ({day_name})")
                except Exception as e:
                    logger.error(f"Error convirtiendo fecha a día: {str(e)}")
                    return f"❌ Error procesando la fecha solicitada: {str(e)}"
            
            # Si se detectó preferencia de horario (mañana/tarde)
            if time_prefs.get('start_hour'):
                query_parts.append(f"start_hour={time_prefs['start_hour']}")
            if time_prefs.get('end_hour'):
                query_parts.append(f"end_hour={time_prefs['end_hour']}")

            # Búsqueda general con offset de semana si es necesario
            if week_offset > 0:
                query_parts.append(f"week_offset={week_offset}")
                logger.info("📅 Búsqueda general - próxima semana")

            calendar_query = "|".join(query_parts)
            logger.info(f"🔧 Query de búsqueda final: {calendar_query}")

            enhanced_project_config = {
                'project_id': self.project_id,
                'workflow_settings': workflow_settings,
                'max_slots_to_show': max_slots_to_show,
                'granular_schedule': granular_schedule,
                'cached_agenda_data': self._cached_project_config
            }
            mock_state = {"project": self.project, "agenda_config": enhanced_project_config}
            search_result = google_calendar_tool.invoke({"query": calendar_query, "state": mock_state})
            logger.info(f"📋 Resultado del calendar_tool: {search_result}")

            if not search_result or (isinstance(search_result, str) and search_result.strip() == ""):
                return "❌ No se encontraron horarios disponibles en este momento. ¿Quieres que busque en otra fecha o día? 😊"
            if "Error" in search_result:
                return f"❌ Error en búsqueda: {search_result}"

            # --- Formateo de la respuesta ---
            day_header = f"🔍 **HORARIOS DISPONIBLES - {project_name.upper()}**"
            if day_filter:
                try:
                    date_obj = datetime.strptime(day_filter[:10], "%Y-%m-%d")
                    dias_semana = {
                        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
                    }
                    meses = {
                        'January': 'enero', 'February': 'febrero', 'March': 'marzo', 'April': 'abril',
                        'May': 'mayo', 'June': 'junio', 'July': 'julio', 'August': 'agosto',
                        'September': 'septiembre', 'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
                    }
                    formatted_day = date_obj.strftime("%A %d de %B")
                    for eng, esp in dias_semana.items():
                        formatted_day = formatted_day.replace(eng, esp)
                    for eng, esp in meses.items():
                        formatted_day = formatted_day.replace(eng, esp)
                    day_header = f"📅 **HORARIOS PARA {formatted_day.upper()}**"
                except:
                    day_header = f"📅 **HORARIOS PARA FECHA ESPECÍFICA**"
            
            if not any(x in search_result for x in ["a las", "horas", "opción", "opciones", "disponibles"]):
                 return "❌ No se encontraron horarios claros para mostrar. ¿Quieres que busque en otra fecha o día? 😊"

            return f"{day_header}\n\n{search_result}"

        except Exception as e:
            logger.error(f"Error en busqueda_horarios_workflow: {str(e)}")
            return f"❌ Error en búsqueda de horarios: {str(e)}"
    
    def _detect_specific_day(self, text: str) -> str:
        """Detecta días específicos en el texto y los convierte a fechas - versión mejorada y robusta para 'próximo miércoles' y variantes"""
        try:
            from datetime import datetime, timedelta
            import pytz
            import re

            if not text:
                return None

            text_lower = text.lower()
            chile_tz = pytz.timezone("America/Santiago")
            now = datetime.now(chile_tz)
            
            logger.info(f"🔍 DETECTANDO FECHA: texto='{text}' | texto_lower='{text_lower}' | hoy={now.strftime('%Y-%m-%d %A')} | hora_actual={now.hour}")

            # 1. Detectar fechas específicas "X de mes"
            fecha_pattern = r'(\d{1,2})\s+de\s+([a-záéíóúñ]+)'
            fecha_match = re.search(fecha_pattern, text_lower)
            if fecha_match:
                try:
                    dia_numero = int(fecha_match.group(1))
                    mes_nombre = fecha_match.group(2)
                    meses_map = {
                        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 
                        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                    }
                    if mes_nombre in meses_map:
                        año_actual = now.year
                        try:
                            fecha_objetivo = datetime(año_actual, meses_map[mes_nombre], dia_numero)
                            fecha_objetivo = chile_tz.localize(fecha_objetivo)
                            if fecha_objetivo.date() < now.date():
                                fecha_objetivo = datetime(año_actual + 1, meses_map[mes_nombre], dia_numero)
                                fecha_objetivo = chile_tz.localize(fecha_objetivo)
                            resultado = fecha_objetivo.strftime("%Y-%m-%d")
                            logger.info(f"✅ Fecha específica detectada: {text} → {resultado}")
                            return resultado
                        except ValueError as ve:
                            logger.error(f"Error creando fecha: {ve}")
                            return None
                    else:
                        logger.warning(f"Mes '{mes_nombre}' no reconocido")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error procesando match: {e}")
                    pass

            # 2. Manejo de "próxima semana" + día
            semana_pattern = r'(la\s+)?pr[oó]xima\s+semana(\s+|,)?(el\s+)?([a-záéíóúñ]+)'
            semana_match = re.search(semana_pattern, text_lower)
            if semana_match:
                dia_texto = semana_match.group(4)
                dias_map = {
                    'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2, 'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
                }
                if dia_texto in dias_map:
                    # Calcular el día de la próxima semana
                    days_until_next = 7 - now.weekday() + dias_map[dia_texto]
                    target_date = now + timedelta(days=days_until_next)
                    return target_date.strftime("%Y-%m-%d")

            # 3. Manejo de "próximo X" o "el próximo X" o "el X de la otra semana"
            for day_name, weekday in {
                "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
            }.items():
                # Detectar "próximo X" o "el próximo X" (pero NO "el X" simple)
                proximo_patterns = [f"próximo {day_name}", f"proximo {day_name}", f"el próximo {day_name}", f"el proximo {day_name}"]
                tiene_proximo = any(pattern in text_lower for pattern in proximo_patterns)
                excluir_para_el = f"para el {day_name}" in text_lower
                
                logger.info(f"🔍 VERIFICANDO PRÓXIMO: day_name={day_name} | tiene_proximo={tiene_proximo} | excluir_para_el={excluir_para_el}")
                
                if tiene_proximo and not excluir_para_el:
                    # Siempre ir a la semana siguiente
                    days_ahead = (weekday - now.weekday() + 7) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_date = now + timedelta(days=days_ahead)
                    logger.info(f"✅ DETECTADO PRÓXIMO: {day_name} → {target_date.strftime('%Y-%m-%d %A')}")
                    return target_date.strftime("%Y-%m-%d")
                # Detectar "el {day_name} de la otra semana"
                if f"el {day_name} de la otra semana" in text_lower:
                    # Ir a la subsiguiente semana
                    days_ahead = (weekday - now.weekday() + 14) % 7
                    if days_ahead == 0:
                        days_ahead = 14
                    target_date = now + timedelta(days=days_ahead)
                    return target_date.strftime("%Y-%m-%d")

            # 4. Palabras especiales para fechas relativas
            if any(word in text_lower for word in ["mañana", "tomorrow"]):
                tomorrow = now + timedelta(days=1)
                return tomorrow.strftime("%Y-%m-%d")
            if any(word in text_lower for word in ["hoy", "today"]):
                return now.strftime("%Y-%m-%d")

            # 5. Detectar días de la semana (día simple)
            for day_name, weekday in {
                "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
            }.items():
                if day_name in text_lower:
                    days_ahead = (weekday - now.weekday()) % 7
                    logger.info(f"📅 ENCONTRADO DÍA: {day_name} | weekday={weekday} | now.weekday()={now.weekday()} | days_ahead_inicial={days_ahead}")
                    
                    if days_ahead == 0:
                        # Si es hoy, verificar si aún hay horarios disponibles (antes de las 15:00)
                        if now.hour >= 15:
                            # Ya es muy tarde para hoy, ir al próximo día de la semana
                            days_ahead = 7
                            logger.info(f"⏰ ES TARDE (>= 15:00): cambiando a próxima semana, days_ahead={days_ahead}")
                        else:
                            logger.info(f"⏰ ES TEMPRANO (< 15:00): manteniendo hoy, days_ahead={days_ahead}")
                        # Si es antes de las 15:00, mantener days_ahead = 0 (hoy)
                    
                    target_date = now + timedelta(days=days_ahead)
                    logger.info(f"🎯 FECHA FINAL: {target_date.strftime('%Y-%m-%d %A')} | days_ahead={days_ahead}")
                    return target_date.strftime("%Y-%m-%d")

            return None
        except Exception as e:
            logger.error(f"Error detectando día específico: {str(e)}")
            return None
    
    def _get_owner_email(self) -> str:
        """Obtiene email del dueño desde configuración cached"""
        try:
            if not self._cached_project_config:
                return None
            
            owner_email = self._cached_project_config.get('owner_email')
            contact_email = self._cached_project_config.get('contact_email')
            
            return owner_email or contact_email
                
        except Exception as e:
            logger.error(f"Error obteniendo email del dueño: {str(e)}")
            return None
    
    async def _generate_email_content(
        self, title: str, start_datetime: str, 
        end_datetime: str, attendee_name: str, attendee_phone: str, description: str, meet_url: str = None
    ) -> tuple:
        """Genera contenido de email usando configuración del proyecto (template único)"""
        try:
            template = await self._get_email_template_from_config()
            
            if not template:
                return None, None
            
            description_section = f'<p><strong>📝 Descripción:</strong> {description}</p>' if description else ''
            
            # Generar sección de Meet URL si está disponible
            meet_section = ""
            if meet_url:
                meet_section = f'<p><strong>🎥 Link de Google Meet:</strong> <a href="{meet_url}" target="_blank">{meet_url}</a></p>'
            
            # Generar subject
            subject = template.get("subject", "Confirmación de Reunión")
            if "{title}" in subject:
                subject = subject.replace("{title}", title or "Evento")
            
            # Generar contenido
            content = template.get("content", "")
            
            # Reemplazar variables en el contenido (manejar valores None)
            replacements = {
                "{attendee_name}": attendee_name or "Cliente",
                "{title}": title or "Evento",
                "{start_datetime}": start_datetime or "Por confirmar",
                "{end_datetime}": end_datetime or "Por confirmar",
                "{description_section}": description_section,
                "{description}": description or "Sin descripción",
                "{attendee_phone}": attendee_phone or "No especificado",
                "{meet_url}": meet_url or "No disponible",
                "{meet_section}": meet_section,
            }
            
            for placeholder, value in replacements.items():
                if placeholder in content:
                    content = content.replace(placeholder, str(value))
            
            return subject, content
            
        except Exception as e:
            logger.error(f"Error generando contenido de email: {str(e)}")
            return None, None
    
    def _generate_owner_notification(
        self, title: str, start_datetime: str, end_datetime: str, 
        attendee_email: str, attendee_name: str, attendee_phone: str, description: str, link_conversation: str
    ) -> tuple:
        """Genera email de notificación para el dueño del proyecto"""
        subject = f"🔔 Nueva cita agendada: {title}"
        
        content = f"""
        <html lang="en">
        <head>
            <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Email</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Mulish:ital,wght@0,200..1000;1,200..1000&display=swap" rel="stylesheet">
        </head>
        <body style="background-color: #fafafa;">
            <div style="box-sizing:border-box;margin:32px auto;font-family:'Segoe UI', Arial, sans-serif;background-color:#f5f7fa;border-radius:16px;box-shadow:0 6px 24px rgba(44, 62, 80, 0.10);max-width:540px;overflow:hidden;">
            <div style="box-sizing:border-box;margin:0px;background-color:#764ba2;padding:28px 0;text-align:center;">
                <h2 style="box-sizing:border-box;margin:0;overflow-wrap:break-word;line-height:1.35em;font-size:2rem;padding-top:0.8em;color:#fff;letter-spacing:1px;">
                <strong style="box-sizing:border-box;margin:0px;">🔔 Nueva Cita Confirmada</strong>
                </h2>
            </div>
            <div style="box-sizing:border-box;margin:0px;padding:32px 24px 18px;">
                <h3 style="box-sizing:border-box;margin:0px 0px 8px;overflow-wrap:break-word;line-height:1.35em;font-size:1.1rem;padding-top:0.8em;color:#21293c;letter-spacing:0.2px;">
                Detalles del Cliente
                </h3>
                <div style="box-sizing:border-box;margin:0px 0px 18px;background-color:#fff;border-radius:10px;border:1px solid #ececec;padding:18px 18px 10px;">
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📝 Nombre:</strong> {attendee_name or 'No especificado'}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📧 Email:</strong> {attendee_email or 'No especificado'}
                </p>
                <p style="box-sizing:border-box;margin:0;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📱 Teléfono:</strong> {attendee_phone or 'No especificado'}
                </p>
                </div>
                <h3 style="box-sizing:border-box;margin:0px 0px 8px;overflow-wrap:break-word;line-height:1.35em;font-size:1.1rem;padding-top:0.8em;color:#21293c;letter-spacing:0.2px;">
                Detalles de la Cita
                </h3>
                <div style="box-sizing:border-box;margin:0px 0px 18px;background-color:#fff;border-radius:10px;border:1px solid #ececec;padding:18px;">
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📅 Evento:</strong> {title}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">🕒 Inicio:</strong> {start_datetime}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">⏰ Fin:</strong> {end_datetime}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📝 Descripción:</strong> {description}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    💬 <strong style="box-sizing:border-box;margin:0px;">Conversación:</strong> {link_conversation}
                </p>
                </div>
                <div style="box-sizing:border-box;margin:6px 0px 0px;background-color:#e0f7ea;border-left:4px solid #13b87b;border-radius:8px;padding:15px;">
                <p style="box-sizing:border-box;margin:0;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;color:#127d56;">
                    <strong style="box-sizing:border-box;margin:0px;">✅ Estado: </strong><span style="box-sizing:border-box;margin:0px;font-weight:400;"><strong style="box-sizing:border-box;margin:0px;">Cita confirmada automáticamente</strong></span>
                </p>
                </div>
            </div>
            <div style="box-sizing:border-box;margin:0px;background-color:#263238;border-top:1px solid #313b48;color:#fff;padding:14px 0;text-align:center;">
                <p style="box-sizing:border-box;margin:0;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:13px;line-height:1.6em;letter-spacing:0.5px;">
                🚀  Ublix.app — Notificación automática
                </p>
            </div>
            </div>
        </body>
        </html>
        """
        
        return subject, content
    
    async def _send_webhook_notification(
        self, title: str, start_datetime: str, end_datetime: str, 
        attendee_email: str, attendee_name: str, attendee_phone: str, 
        description: str, conversation_summary: str = None, meet_url: str = None, additional_fields: Optional[Dict[str, Any]] = None
    ) -> str:
        """Envía datos de la conversación al webhook configurado si está habilitado, enriqueciendo con datos del contacto desde la BD."""
        try:
            if not self._cached_project_config:
                return None
            
            # Verificar si existe webhook_url en general_settings
            general_settings = self._cached_project_config.get("general_settings", {})
            webhook_url = general_settings.get("Webhook_url")
            
            if not webhook_url:
                logger.info("📡 No hay webhook configurado en general_settings")
                return None
            
            logger.info(f"📡 Enviando datos al webhook: {webhook_url}")
            
            # --- BÚSQUEDA DE CONTACTO EN SUPABASE ---
            contact_info = {}
            
            # Priorizar búsqueda por user_id si está disponible (más específico)
            if self.user_id and self.project_id:
                try:
                    logger.info(f"🔍 Buscando contacto con user_id '{self.user_id}' para proyecto '{self.project_id}'")
                    response = self.supabase_client.client.table("contacts").select("*").eq("user_id", self.user_id).eq("project_id", self.project_id).limit(1).execute()
                    if response.data:
                        contact_info = response.data[0]
                        logger.info(f"✅ Contacto encontrado por user_id: {contact_info.get('id')}")
                        logger.info(f"🔍 [DEBUG] Datos completos del contacto: {contact_info}")
                        logger.info(f"🔍 [DEBUG] Additional fields raw: {contact_info.get('additional_fields')}")
                        logger.info(f"🔍 [DEBUG] Tipo de additional_fields: {type(contact_info.get('additional_fields'))}")
                    else:
                        logger.info("ℹ️ No se encontró contacto con ese user_id, intentando con email...")
                        # Fallback: buscar por email si no se encuentra por user_id
                        if attendee_email:
                            response = self.supabase_client.client.table("contacts").select("*").eq("email", attendee_email).eq("project_id", self.project_id).limit(1).execute()
                            if response.data:
                                contact_info = response.data[0]
                                logger.info(f"✅ Contacto encontrado por email: {contact_info.get('id')}")
                            else:
                                logger.info("ℹ️ No se encontró contacto con ese email tampoco.")
                except Exception as e:
                    logger.error(f"❌ Error buscando contacto en Supabase: {str(e)}")
            elif attendee_email and self.project_id:
                # Fallback solo por email (cuando no hay user_id)
                try:
                    logger.info(f"🔍 Buscando contacto con email '{attendee_email}' para proyecto '{self.project_id}' (sin user_id)")
                    response = self.supabase_client.client.table("contacts").select("*").eq("email", attendee_email).eq("project_id", self.project_id).limit(1).execute()
                    if response.data:
                        contact_info = response.data[0]
                        logger.info(f"✅ Contacto encontrado por email: {contact_info.get('id')}")
                    else:
                        logger.info("ℹ️ No se encontró un contacto existente con ese email.")
                except Exception as e:
                    logger.error(f"❌ Error buscando contacto en Supabase: {str(e)}")

            # --- PREPARACIÓN DE DATOS PARA WEBHOOK (user_data) ---
            
            # 1. Empezar con la información del contacto si se encontró
            user_data = {}
            if contact_info:
                logger.info(f"🔍 [DEBUG] Procesando contacto para webhook...")
                
                # Aplanar el campo 'additional_fields' si existe
                additional_fields_raw = contact_info.get('additional_fields')
                logger.info(f"🔍 [DEBUG] additional_fields_raw = {additional_fields_raw} (tipo: {type(additional_fields_raw)})")
                
                if 'additional_fields' in contact_info and isinstance(contact_info.get('additional_fields'), dict):
                    user_data.update(contact_info['additional_fields'])
                    logger.info(f"📋 Additional fields agregados al webhook: {contact_info['additional_fields']}")
                elif 'additional_fields' in contact_info and contact_info.get('additional_fields'):
                    logger.warning(f"⚠️ Additional fields existe pero no es dict: {additional_fields_raw} (tipo: {type(additional_fields_raw)})")
                else:
                    logger.info(f"ℹ️ No hay additional_fields válidos en el contacto")
                
                # Copiar otros campos relevantes, excluyendo metadatos y 'additional_fields'
                for key, value in contact_info.items():
                    if key not in ['id', 'project_id', 'created_at', 'updated_at', 'additional_fields']:
                        user_data[key] = value

            # 2. Superponer datos de los argumentos (tienen precedencia si no son None)
            if attendee_name:
                user_data['name'] = attendee_name
            if attendee_email:
                user_data['email'] = attendee_email
            if attendee_phone:
                user_data['phone'] = attendee_phone
            
            # 3. Superponer campos adicionales (máxima precedencia)
            if additional_fields and isinstance(additional_fields, dict):
                user_data.update(additional_fields)
                logger.info(f"➕ Campos adicionales fusionados en user_data para el webhook")

            logger.info(f"👤 User data final para el webhook: {user_data}")
            
            # Preparar datos del evento y conversación
            webhook_data = {
                "event_type": "appointment_scheduled",
                "timestamp": datetime.now().isoformat(),
                "project_id": self.project_id,
                "project_name": self._cached_project_config.get("name", "Proyecto"),
                "appointment_data": {
                    "title": title,
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                    "attendee_email": attendee_email,
                    "description": description,
                    "meet_url": meet_url
                },
                "conversation_data": {
                    "summary": conversation_summary or "Resumen no disponible",
                    "client_email": attendee_email,
                    "scheduled_at": datetime.now().isoformat()
                },
                "user_data": user_data
            }

            # Enviar POST al webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=webhook_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Ublix-Webhook/1.0"
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Webhook enviado exitosamente a {webhook_url}")
                        return f"✅ Datos enviados al webhook externo ({webhook_url})"
                    else:
                        logger.error(f"❌ Error en webhook: HTTP {response.status}")
                        return f"⚠️ Error en webhook: HTTP {response.status}"
                        
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout al enviar webhook a {webhook_url}")
            return f"⚠️ Timeout enviando al webhook ({webhook_url})"
        except Exception as e:
            logger.error(f"❌ Error enviando webhook: {str(e)}")
            return f"⚠️ Error enviando webhook: {str(e)}"
    
    def _extract_meet_url(self, calendar_result: str) -> str:
        """Extrae la URL de Google Meet de la respuesta del calendar tool"""
        try:
            import re
            
            # Patrones para encontrar URLs de Meet
            meet_patterns = [
                r'https://meet\.google\.com/[a-z0-9-]+',
                r'Meet URL: (https://meet\.google\.com/[a-z0-9-]+)',
                r'Google Meet: (https://meet\.google\.com/[a-z0-9-]+)',
                r'meet\.google\.com/[a-z0-9-]+',
            ]
            
            for pattern in meet_patterns:
                match = re.search(pattern, calendar_result, re.IGNORECASE)
                if match:
                    url = match.group(1) if match.groups() else match.group(0)
                    # Asegurar que tenga el protocolo https://
                    if not url.startswith('https://'):
                        url = f"https://{url}"
                    logger.info(f"✅ URL de Meet encontrada: {url}")
                    return url
            
            logger.warning("⚠️ No se encontró URL de Google Meet en la respuesta del calendario")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo URL de Meet: {str(e)}")
            return None

    def _generate_calendar_query(
        self, action: str, title: str = None, start_datetime: str = None, 
        end_datetime: str = None, attendee_email: str = None, 
        description: str = None, include_meet: bool = None
    ) -> str:
        """Genera query para calendar tool"""
        try:
            query_parts = [action]
            
            if action == "create_event":
                # Usar título por defecto de configuración si no se proporciona
                if not title and self._cached_project_config:
                    general_settings = self._cached_project_config.get("general_settings", {})
                    title = general_settings.get("title_calendar_email", "Llamada Maricunga")
                    
                if title:
                    query_parts.append(f"title={title}")
                if start_datetime:
                    query_parts.append(f"start={start_datetime}")
                if end_datetime:
                    query_parts.append(f"end={end_datetime}")
                elif start_datetime:
                    # Auto-calcular duración usando configuración del proyecto
                    start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
                    
                    # Obtener duración desde workflow_settings o usar 60 minutos por defecto
                    default_duration_minutes = 60  # Valor por defecto
                    if self._cached_project_config:
                        workflow_settings = self._cached_project_config.get("workflow_settings", {})
                        agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})
                        default_duration_minutes = agenda_settings.get("default_duration_minutes", 60)
                    
                    end_dt = start_dt + timedelta(minutes=default_duration_minutes)
                    query_parts.append(f"end={end_dt.isoformat()}")
                    logger.info(f"🕒 Duración configurada: {default_duration_minutes} minutos")
                if description:
                    enhanced_description = f"{description}\n\n🤖 Evento creado por Ublix.app"
                    query_parts.append(f"description={enhanced_description}")
                if attendee_email:
                    query_parts.append(f"attendees={attendee_email}")
                
                # Decidir si incluir Meet basado en el parámetro o la configuración
                should_add_meet = False
                if include_meet is not None:
                    # El parámetro explícito tiene precedencia
                    should_add_meet = include_meet
                elif self._cached_project_config:
                    # Fallback a la configuración del proyecto
                    general_settings = self._cached_project_config.get("general_settings", {})
                    should_add_meet = general_settings.get("auto_include_meet", False)

                if should_add_meet:
                    query_parts.append("meet=true")
                    
                # 🚨 CRÍTICO: SIEMPRE verificar conflictos - NO crear si hay conflictos
                query_parts.append("force_create=false")
                logger.info("🔍 VERIFICACIÓN DE CONFLICTOS HABILITADA: force_create=false")
            
            elif action == "find_available_slots":
                if title:
                    query_parts.append(f"title={title}")
                if start_datetime:
                    query_parts.append(f"start={start_datetime}")
                if end_datetime:
                    query_parts.append(f"end={end_datetime}")
            
            return "|".join(query_parts)
            
        except Exception as e:
            logger.error(f"Error generando query: {str(e)}")
            return action
    
    def _run(
        self,
        workflow_type: str,
        title: Optional[str] = None,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        attendee_email: Optional[str] = None,
        description: Optional[str] = None,
        event_id: Optional[str] = None,
        include_meet: Optional[bool] = None,
        conversation_summary: Optional[str] = None
    ) -> str:
        """Versión síncrona simplificada"""
        try:
            logger.info(f"Iniciando workflow síncrono: {workflow_type}")
            workflow_type = workflow_type.upper()
            
            if workflow_type == "AGENDA_COMPLETA":
                return f"✅ Workflow AGENDA_COMPLETA programado para '{title}'"
            elif workflow_type == "COMUNICACION_EVENTO":
                return f"✅ Comunicación programada para evento {event_id}"
            elif workflow_type == "ACTUALIZACION_COMPLETA":
                return f"✅ Actualización programada para evento {event_id}"
            elif workflow_type == "CANCELACION_WORKFLOW":
                return f"✅ Cancelación programada para evento {event_id}"
            elif workflow_type == "BUSQUEDA_HORARIOS":
                # Ejecutar el workflow real usando asyncio para llamar al método asíncrono
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Si ya hay un loop corriendo, usar run_coroutine_threadsafe
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = asyncio.run_coroutine_threadsafe(
                                self._busqueda_horarios_workflow(title, start_datetime, end_datetime, conversation_summary),
                                loop
                            )
                            return future.result()
                    else:
                        # Si no hay loop, crear uno nuevo
                        return loop.run_until_complete(
                            self._busqueda_horarios_workflow(title, start_datetime, end_datetime, conversation_summary)
                        )
                except RuntimeError:
                    # Fallback: crear nuevo loop
                    return asyncio.run(self._busqueda_horarios_workflow(title, start_datetime, end_datetime, conversation_summary))
            else:
                return f"❌ Workflow '{workflow_type}' no reconocido"
                
        except Exception as e:
            logger.error(f"Error en workflow síncrono: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _validate_date_consistency(self, text: str) -> Tuple[bool, str, Optional[str]]:
        """
        Valida la consistencia entre día de la semana mencionado y fecha específica
        
        Args:
            text: Texto del usuario que puede contener día y fecha
            
        Returns:
            Tupla (es_consistente, mensaje_validacion, fecha_corregida)
        """
        try:
            import re
            from datetime import datetime
            import pytz
            
            if not text:
                return True, "", None
                
            text_lower = text.lower()
            logger.info(f"🔍 VALIDANDO CONSISTENCIA DE FECHA: '{text}'")
            
            # Mapeo de días en español
            dias_map = {
                'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
                'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
            }
            
            # Mapeo de meses en español
            meses_map = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
            }
            
            # Detectar si hay un día de la semana mencionado
            dia_mencionado = None
            dia_weekday = None
            for dia, weekday in dias_map.items():
                if dia in text_lower:
                    dia_mencionado = dia
                    dia_weekday = weekday
                    break
            
            # Detectar si hay una fecha específica mencionada
            # Patrón: "X de mes" o "X de mes de año"
            fecha_pattern = r'(\d{1,2})\s+de\s+([a-záéíóúñ]+)(?:\s+de\s+(\d{4}))?'
            fecha_match = re.search(fecha_pattern, text_lower)
            
            if dia_mencionado and fecha_match:
                logger.info(f"   📅 Día detectado: {dia_mencionado} (weekday {dia_weekday})")
                logger.info(f"   📅 Fecha detectada: {fecha_match.group(0)}")
                
                # Extraer componentes de la fecha
                dia_numero = int(fecha_match.group(1))
                mes_nombre = fecha_match.group(2)
                año = int(fecha_match.group(3)) if fecha_match.group(3) else datetime.now().year
                
                # Validar que el mes sea válido
                if mes_nombre not in meses_map:
                    return False, f"❌ Mes no reconocido: {mes_nombre}", None
                
                mes_numero = meses_map[mes_nombre]
                
                try:
                    # Crear el objeto datetime para la fecha específica
                    fecha_especifica = datetime(año, mes_numero, dia_numero)
                    fecha_weekday = fecha_especifica.weekday()
                    
                    logger.info(f"   📊 COMPARACIÓN:")
                    logger.info(f"      🗣️  Usuario dijo: {dia_mencionado} (weekday {dia_weekday})")
                    # Usar mapeo correcto para mostrar el día real en el log
                    dias_weekday_to_name = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                    dia_real_log = dias_weekday_to_name[fecha_weekday]
                    logger.info(f"      📅 Fecha real: {fecha_especifica.strftime('%Y-%m-%d')} es {dia_real_log} (weekday {fecha_weekday})")
                    
                    # Verificar consistencia
                    if dia_weekday == fecha_weekday:
                        logger.info(f"   ✅ CONSISTENCIA VÁLIDA: {dia_mencionado} {dia_numero} de {mes_nombre} de {año}")
                        return True, f"✅ Fecha válida", fecha_especifica.strftime('%Y-%m-%d')
                    else:
                        # Inconsistencia detectada - usar mapeo correcto de weekday a nombre
                        dias_weekday_to_name = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                        dia_real = dias_weekday_to_name[fecha_weekday]
                        
                        meses_esp = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                                   'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                        
                        fecha_legible = f"{dia_numero} de {meses_esp[mes_numero]} de {año}"
                        
                        logger.warning(f"   ❌ INCONSISTENCIA DETECTADA:")
                        logger.warning(f"      🗣️  Usuario dijo: '{dia_mencionado} {fecha_legible}'")
                        logger.warning(f"      📅 Pero el {fecha_legible} es {dia_real}, no {dia_mencionado}")
                        
                        mensaje_error = f"""❌ **Error en la fecha**: 

🗣️ **Dijiste:** "{dia_mencionado} {fecha_legible}"
📅 **Pero:** El {fecha_legible} es **{dia_real}**, no {dia_mencionado}

🤔 **¿Qué querías decir?**
1. **{dia_real} {fecha_legible}** (corregir el día)
2. **Próximo {dia_mencionado}** (buscar el siguiente {dia_mencionado})

💡 Por favor aclara cuál era tu intención."""
                        
                        return False, mensaje_error, fecha_especifica.strftime('%Y-%m-%d')
                        
                except ValueError as date_error:
                    logger.error(f"   ❌ Fecha inválida: {dia_numero}/{mes_numero}/{año} - {date_error}")
                    return False, f"❌ La fecha {dia_numero} de {mes_nombre} de {año} no es válida", None
            
            # Si no hay conflicto o solo hay una parte (día o fecha), es válido
            logger.info(f"   ✅ Sin inconsistencias detectadas")
            return True, "", None
            
        except Exception as e:
            logger.error(f"❌ Error validando consistencia de fecha: {str(e)}")
            return True, "", None  # En caso de error, permitir continuar

    # 🔧 MÉTODOS DE CONFIGURACIÓN GRANULAR (IMPLEMENTACIÓN DIRECTA)
    
    def _parse_granular_schedule(self, workflow_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae y valida la configuración granular de horarios desde workflow_settings"""
        agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})
        schedule = agenda_settings.get("schedule", {})
        
        # Configuración por defecto si no existe schedule granular
        if not schedule:
            logger.info("📋 No hay configuración granular, usando horarios estándar")
            return {
                "monday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "tuesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "wednesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "thursday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "friday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "saturday": {"enabled": False, "time_slots": []},
                "sunday": {"enabled": False, "time_slots": []}
            }
        
        logger.info("✅ Configuración granular de horarios cargada exitosamente")
        return schedule
    
    def _is_day_enabled(self, schedule: Dict[str, Any], day_name: str) -> bool:
        """Verifica si un día específico está habilitado"""
        day_config = schedule.get(day_name, {})
        return day_config.get("enabled", False)
    
    def _get_time_slots_for_day(self, schedule: Dict[str, Any], day_name: str) -> List[Dict[str, str]]:
        """Obtiene las franjas horarias para un día específico"""
        if not self._is_day_enabled(schedule, day_name):
            return []
        
        day_config = schedule.get(day_name, {})
        return day_config.get("time_slots", [])
    
    def _is_time_in_working_hours(self, schedule: Dict[str, Any], target_datetime: datetime) -> Tuple[bool, str]:
        """Verifica si una fecha/hora específica está dentro de horarios laborales"""
        # Mapeo de weekday() a nombre de día
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day_name = day_names[target_datetime.weekday()]
        
        # Verificar si el día está habilitado
        if not self._is_day_enabled(schedule, day_name):
            days_available = [day for day in day_names if self._is_day_enabled(schedule, day)]
            return False, f"❌ No trabajo los {day_name}s. Días disponibles: {', '.join(days_available)}"
        
        # Obtener franjas horarias del día
        time_slots = self._get_time_slots_for_day(schedule, day_name)
        if not time_slots:
            return False, f"❌ No hay franjas horarias configuradas para {day_name}"
        
        # Convertir hora objetivo a formato HH:MM
        target_time = target_datetime.strftime("%H:%M")
        
        # Verificar si está dentro de alguna franja horaria
        for slot in time_slots:
            start_time = slot.get("start", "00:00")
            end_time = slot.get("end", "23:59")
            
            if start_time <= target_time < end_time:
                description = slot.get("description", "Horario laboral")
                return True, f"✅ Horario válido en franja '{description}' ({start_time}-{end_time})"
        
        # No está en ninguna franja
        slot_descriptions = [f"{slot['start']}-{slot['end']} ({slot.get('description', 'Sin descripción')})" 
                            for slot in time_slots]
        return False, f"❌ Horario fuera de franjas laborales. Disponible: {', '.join(slot_descriptions)}"

    def _extract_time_preferences(self, text: str) -> Dict[str, int]:
        """Extrae preferencias de horario (mañana, tarde) del texto."""
        prefs = {}
        if not text:
            return prefs
        
        text = text.lower()
        
        # Mapeo de sinónimos y rangos de horas
        time_map = {
            "mañana": {"start": 9, "end": 12},
            "medio día": {"start": 12, "end": 14},
            "mediodia": {"start": 12, "end": 14},
            "tarde": {"start": 14, "end": 19},
            "noche": {"start": 19, "end": 22}
        }
        
        for keyword, hours in time_map.items():
            if keyword in text:
                prefs['start_hour'] = hours['start']
                prefs['end_hour'] = hours['end']
                logger.info(f"🕒 Preferencia de horario detectada: '{keyword}' -> {hours['start']}-{hours['end']}")
                return prefs  # Devolver la primera coincidencia
                
        # Búsqueda de am/pm
        if "am" in text or "a.m" in text:
            prefs['start_hour'] = 9
            prefs['end_hour'] = 12
            logger.info("🕒 Preferencia de horario detectada: 'am'")
        elif "pm" in text or "p.m" in text:
            prefs['start_hour'] = 12
            prefs['end_hour'] = 19
            logger.info("🕒 Preferencia de horario detectada: 'pm'")
            
        return prefs

    def _extract_specific_time(self, text: str) -> Optional[str]:
        """Extrae una hora específica del texto (ej: 6 de la tarde, 18:00) y la devuelve en formato HH:MM."""
        if not text:
            return None
        
        import re
        text_lower = text.lower()
        
        # Patrón para HH:MM
        match = re.search(r'(\d{1,2}):(\d{2})', text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

        # Patrón para "X de la tarde/mañana/noche" o "a las X"
        match = re.search(r'(?:a la|a las|de la|de las)\s+(\d{1,2})', text_lower)
        if match:
            hour = int(match.group(1))
            
            # Ajustar para PM
            if "tarde" in text_lower or "noche" in text_lower or "pm" in text_lower or "p.m." in text_lower:
                if 1 <= hour <= 11:
                    hour += 12
            
            if 0 <= hour <= 23:
                 return f"{hour:02d}:00"

        return None