-- 📋 INSERT OPTIMIZADO CON CONFIGURACIÓN DE HORARIOS LABORALES
-- ✅ Incluye días habilitados y horarios de trabajo

INSERT INTO "public"."agenda" (
    "id", 
    "project_id", 
    "email_templates", 
    "workflow_settings", 
    "general_settings", 
    "owner_email", 
    "contact_email", 
    "created_at", 
    "updated_at"
) VALUES (
    'ecb77b5f-6576-473a-870e-a285907def93', 
    '29ab2dc1-8790-4ef1-a9d4-f6d684b00572',
    
    -- ✅ email_templates: Templates de confirmación
    '{
        "email_template": {
            "subject": "✅ Confirmación de Reunión - {title}",
            "content": "<html lang=\"es\"><head><meta charset=\"UTF-8\"><title>Confirmación de Reunión</title></head><body style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa;\"><div style=\"background: #4CAF50; color: white; padding: 20px; text-align: center;\"><h2 style=\"margin: 0;\">🎉 ¡Tu reunión ha sido confirmada!</h2></div><div style=\"padding: 20px; background: white; margin: 20px 0;\"><p><strong>Hola {attendee_name},</strong></p><p>Te confirmamos que tu reunión ha sido agendada exitosamente:</p><div style=\"background: #f1f8e9; padding: 15px; border-radius: 8px; margin: 15px 0;\"><p><strong>📅 Evento:</strong> {title}</p><p><strong>🕒 Inicio:</strong> {start_datetime}</p><p><strong>⏰ Fin:</strong> {end_datetime}</p>{description_section}{meet_section}</div><p>Si necesitas hacer algún cambio o tienes alguna consulta, no dudes en contactarnos.</p><p style=\"color: #4CAF50; font-weight: bold;\">¡Esperamos verte pronto! 🌟</p></div><div style=\"background: #263238; color: white; padding: 15px; text-align: center; font-size: 12px;\">🚀 Maricunga Investment Group - Agendado automáticamente por Ublix.app</div></body></html>"
        }
    }',
    
    -- ✅ workflow_settings: Configuración completa con horarios laborales
    '{
        "AGENDA_COMPLETA": {
            "default_duration_minutes": 60,
            "start_hour": 9,
            "end_hour": 18,
            "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "buffer_minutes": 15,
            "auto_include_holidays_validation": true
        },
        "BUSQUEDA_HORARIOS": {
            "max_slots_to_show": 3,
            "search_weeks_ahead": 4,
            "exclude_weekends": true,
            "exclude_holidays": true
        }
    }',
    
    -- ✅ general_settings: Configuración general con timezone
    '{
        "company_info": {
            "name": "Maricunga Investment Group"
        },
        "title_calendar_email": "Llamada Maricunga",
        "timezone": "America/Santiago",
        "Webhook_url": "https://n8n-pirata-brccexcfffhzejat.eastus2-01.azurewebsites.net/webhook/475ec48c-dbe3-4873-825f-1f6ecaa92356"
    }',
    
    -- ✅ owner_email: Para notificaciones al dueño
    'idbarbagelata@gmail.com',
    
    -- ✅ contact_email: Email de backup
    'contacto@maricunga.com',
    
    '2025-06-26 09:09:04.65745+00', 
    '2025-06-26 09:09:04.65745+00'
);

-- 📝 CONFIGURACIÓN DE HORARIOS EXPLICADA:

-- 🕒 HORARIOS LABORALES:
-- "start_hour": 9           → Empieza a las 9:00 AM
-- "end_hour": 18            → Termina a las 6:00 PM  
-- "buffer_minutes": 15      → 15 minutos entre citas

-- 📅 DÍAS LABORALES:
-- "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
-- → Solo de lunes a viernes (excluye fines de semana)

-- ⏰ DURACIÓN:
-- "default_duration_minutes": 60  → 1 hora por defecto

-- 🚫 VALIDACIONES:
-- "exclude_weekends": true         → No mostrar sábados/domingos
-- "exclude_holidays": true         → No mostrar feriados chilenos
-- "auto_include_holidays_validation": true → Validar automáticamente

-- 🔍 BÚSQUEDA:
-- "max_slots_to_show": 3          → Máximo 3 opciones
-- "search_weeks_ahead": 4         → Buscar hasta 4 semanas adelante

-- 📋 EJEMPLOS DE CONFIGURACIÓN PERSONALIZADA:

-- Para horarios ejecutivos (7am-7pm):
-- UPDATE agenda SET workflow_settings = jsonb_set(workflow_settings, '{AGENDA_COMPLETA,start_hour}', '7')
-- UPDATE agenda SET workflow_settings = jsonb_set(workflow_settings, '{AGENDA_COMPLETA,end_hour}', '19')

-- Para incluir sábados:
-- UPDATE agenda SET workflow_settings = jsonb_set(
--   workflow_settings, 
--   '{AGENDA_COMPLETA,working_days}', 
--   '["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]'::jsonb
-- )

-- Para reuniones de 30 minutos:
-- UPDATE agenda SET workflow_settings = jsonb_set(
--   workflow_settings, 
--   '{AGENDA_COMPLETA,default_duration_minutes}', 
--   '30'::jsonb
-- ) 