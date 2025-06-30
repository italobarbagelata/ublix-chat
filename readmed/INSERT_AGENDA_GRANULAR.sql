-- 📋 INSERT OPTIMIZADO CON CONFIGURACIÓN GRANULAR DE HORARIOS
-- ✅ Configuración específica por día con múltiples franjas horarias

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
    
    -- ✅ workflow_settings: CONFIGURACIÓN GRANULAR CON HORARIOS ESPECÍFICOS POR DÍA
    '{
        "AGENDA_COMPLETA": {
            "default_duration_minutes": 60,
            "buffer_minutes": 15,
            "auto_include_holidays_validation": true,
            "schedule": {
                "monday": {
                    "enabled": true,
                    "time_slots": [
                        {"start": "08:00", "end": "12:00", "description": "Mañana"},
                        {"start": "13:00", "end": "19:00", "description": "Tarde"}
                    ]
                },
                "tuesday": {
                    "enabled": true,
                    "time_slots": [
                        {"start": "09:00", "end": "17:00", "description": "Jornada continua"}
                    ]
                },
                "wednesday": {
                    "enabled": true,
                    "time_slots": [
                        {"start": "08:00", "end": "12:00", "description": "Solo mañana"},
                        {"start": "14:00", "end": "18:00", "description": "Tarde"}
                    ]
                },
                "thursday": {
                    "enabled": true,
                    "time_slots": [
                        {"start": "09:00", "end": "13:00", "description": "Mañana"},
                        {"start": "15:00", "end": "19:00", "description": "Tarde"}
                    ]
                },
                "friday": {
                    "enabled": true,
                    "time_slots": [
                        {"start": "08:00", "end": "16:00", "description": "Viernes corto"}
                    ]
                },
                "saturday": {
                    "enabled": false,
                    "time_slots": []
                },
                "sunday": {
                    "enabled": false,
                    "time_slots": []
                }
            }
        },
        "BUSQUEDA_HORARIOS": {
            "max_slots_to_show": 3,
            "search_weeks_ahead": 4,
            "exclude_holidays": true,
            "slot_spacing_minutes": 60
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

-- 📝 EXPLICACIÓN DE LA CONFIGURACIÓN GRANULAR:

-- 🗓️ ESTRUCTURA POR DÍA:
-- {
--   "monday": {
--     "enabled": true/false,           // ¿Está activo este día?
--     "time_slots": [                  // Array de franjas horarias
--       {
--         "start": "08:00",            // Hora inicio (HH:MM)
--         "end": "12:00",              // Hora fin (HH:MM)
--         "description": "Mañana"      // Descripción opcional
--       }
--     ]
--   }
-- }

-- 💼 EJEMPLOS DE CONFIGURACIÓN:

-- 🏢 HORARIO EMPRESARIAL ESTÁNDAR:
-- Lunes a viernes: 9:00-17:00 (jornada continua)

-- 🏥 HORARIO CON DESCANSO DE ALMUERZO:
-- Lunes a viernes: 8:00-12:00 y 13:00-19:00

-- 👔 HORARIO EJECUTIVO FLEXIBLE:
-- Lunes: 8:00-20:00, Martes: 9:00-17:00, Miércoles: Solo tarde, etc.

-- 🛍️ HORARIO COMERCIAL:
-- Lunes-Viernes: 10:00-22:00, Sábados: 10:00-20:00

-- 📋 VENTAJAS DE ESTA CONFIGURACIÓN:

-- ✅ Horarios específicos por día
-- ✅ Múltiples franjas por día (descansos)
-- ✅ Control granular de disponibilidad
-- ✅ Fácil activar/desactivar días
-- ✅ Descripciones para cada franja
-- ✅ Escalable a cualquier tipo de negocio 