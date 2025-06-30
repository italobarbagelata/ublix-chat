-- =====================================================
-- TABLA: contact_field_configs
-- Configuración dinámica de campos de contacto por proyecto
-- =====================================================

CREATE TABLE IF NOT EXISTS contact_field_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    field_name VARCHAR(255) NOT NULL,
    keywords JSONB NOT NULL DEFAULT '[]',
    field_type VARCHAR(50) NOT NULL CHECK (field_type IN ('string', 'number', 'boolean')),
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Índices para rendimiento
    CONSTRAINT unique_project_field UNIQUE (project_id, field_name)
);

-- Índices para búsquedas eficientes
CREATE INDEX IF NOT EXISTS idx_contact_field_configs_project_id ON contact_field_configs(project_id);
CREATE INDEX IF NOT EXISTS idx_contact_field_configs_enabled ON contact_field_configs(project_id, enabled);
CREATE INDEX IF NOT EXISTS idx_contact_field_configs_priority ON contact_field_configs(project_id, priority);

-- Comentarios para documentación
COMMENT ON TABLE contact_field_configs IS 'Configuración de campos dinámicos de contacto por proyecto';
COMMENT ON COLUMN contact_field_configs.project_id IS 'ID del proyecto';
COMMENT ON COLUMN contact_field_configs.field_name IS 'Nombre del campo (ej: edad, direccion, presupuesto)';
COMMENT ON COLUMN contact_field_configs.keywords IS 'Array JSON de palabras clave para detectar el campo';
COMMENT ON COLUMN contact_field_configs.field_type IS 'Tipo de dato: string, number, boolean';
COMMENT ON COLUMN contact_field_configs.description IS 'Descripción del campo para el usuario';
COMMENT ON COLUMN contact_field_configs.enabled IS 'Si está activo para captura automática';
COMMENT ON COLUMN contact_field_configs.priority IS 'Orden de procesamiento (menor = mayor prioridad)';

-- Función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_contact_field_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar updated_at automáticamente
CREATE TRIGGER update_contact_field_configs_updated_at_trigger
    BEFORE UPDATE ON contact_field_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_contact_field_configs_updated_at();

-- =====================================================
-- DATOS DE EJEMPLO
-- =====================================================

-- Ejemplo para Bot de Inversiones
INSERT INTO contact_field_configs (project_id, field_name, keywords, field_type, description, priority) VALUES
-- Campos básicos de inversiones
('example-project-inversiones', 'edad', '["tengo", "años", "mi edad", "edad es"]', 'number', 'Edad del cliente', 1),
('example-project-inversiones', 'direccion', '["vivo en", "mi dirección", "dirección es", "domicilio", "resido en"]', 'string', 'Dirección de residencia', 2),
('example-project-inversiones', 'ciudad', '["ciudad", "vivo en", "de la ciudad"]', 'string', 'Ciudad donde reside', 3),
('example-project-inversiones', 'ha_invertido', '["he invertido", "invirtiendo", "inversión", "broker", "acciones", "bolsa"]', 'boolean', 'Si ha invertido anteriormente', 4),
('example-project-inversiones', 'presupuesto', '["presupuesto", "dispongo", "capital", "puedo invertir", "millones"]', 'number', 'Capital disponible para invertir', 5),
('example-project-inversiones', 'tolerancia_riesgo', '["conservador", "agresivo", "moderado", "riesgo"]', 'string', 'Tolerancia al riesgo', 6);

-- Ejemplo para Bot de E-commerce  
INSERT INTO contact_field_configs (project_id, field_name, keywords, field_type, description, priority) VALUES
('example-project-ecommerce', 'producto_interes', '["me interesa", "quiero", "busco", "necesito", "producto"]', 'string', 'Producto de interés', 1),
('example-project-ecommerce', 'presupuesto', '["presupuesto", "dispongo", "puedo pagar", "precio máximo", "mil"]', 'number', 'Presupuesto disponible', 2),
('example-project-ecommerce', 'fecha_compra', '["cuando", "fecha", "para cuándo", "necesito para"]', 'string', 'Fecha estimada de compra', 3),
('example-project-ecommerce', 'metodo_pago', '["pago", "transferencia", "tarjeta", "efectivo", "cuotas"]', 'string', 'Método de pago preferido', 4),
('example-project-ecommerce', 'categoria_preferida', '["categoria", "tipo", "marca", "estilo"]', 'string', 'Categoría o marca preferida', 5);

-- Ejemplo para Bot de Servicios
INSERT INTO contact_field_configs (project_id, field_name, keywords, field_type, description, priority) VALUES
('example-project-servicios', 'tipo_servicio', '["necesito", "servicio", "requiero", "busco"]', 'string', 'Tipo de servicio requerido', 1),
('example-project-servicios', 'urgencia', '["urgente", "pronto", "rápido", "cuando"]', 'string', 'Nivel de urgencia', 2),
('example-project-servicios', 'disponibilidad', '["disponible", "horario", "puede", "prefiero", "mañana", "tarde"]', 'string', 'Disponibilidad horaria', 3),
('example-project-servicios', 'presupuesto', '["presupuesto", "cuesta", "precio", "dispongo"]', 'number', 'Presupuesto para el servicio', 4);

-- =====================================================
-- FUNCIONES UTILITARIAS
-- =====================================================

-- Función para obtener configuración de campos por proyecto
CREATE OR REPLACE FUNCTION get_contact_field_config(project_uuid UUID)
RETURNS JSONB AS $$
DECLARE
    config JSONB := '{}';
    field_record RECORD;
BEGIN
    FOR field_record IN 
        SELECT field_name, keywords, field_type, description
        FROM contact_field_configs 
        WHERE project_id = project_uuid AND enabled = true
        ORDER BY priority ASC
    LOOP
        config := config || jsonb_build_object(
            field_record.field_name,
            jsonb_build_object(
                'keywords', field_record.keywords,
                'type', field_record.field_type,
                'description', field_record.description
            )
        );
    END LOOP;
    
    RETURN config;
END;
$$ LANGUAGE plpgsql;

-- Función para agregar campo a un proyecto
CREATE OR REPLACE FUNCTION add_contact_field(
    project_uuid UUID,
    field_name_param VARCHAR(255),
    keywords_param JSONB,
    field_type_param VARCHAR(50),
    description_param TEXT DEFAULT NULL,
    priority_param INTEGER DEFAULT 1
)
RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO contact_field_configs (
        project_id, field_name, keywords, field_type, description, priority
    ) VALUES (
        project_uuid, field_name_param, keywords_param, field_type_param, description_param, priority_param
    )
    ON CONFLICT (project_id, field_name) 
    DO UPDATE SET
        keywords = EXCLUDED.keywords,
        field_type = EXCLUDED.field_type,
        description = EXCLUDED.description,
        priority = EXCLUDED.priority,
        updated_at = NOW();
    
    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VERIFICACIÓN
-- =====================================================

-- Verificar que la tabla se creó correctamente
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'contact_field_configs'
ORDER BY ordinal_position;

-- Ejemplo de uso de la función
SELECT get_contact_field_config('example-project-inversiones');

-- =====================================================
-- EJEMPLOS DE CONSULTAS ÚTILES
-- =====================================================

-- Ver todos los campos configurados para un proyecto
-- SELECT * FROM contact_field_configs WHERE project_id = 'tu-project-id' ORDER BY priority;

-- Obtener configuración como JSON para usar en código
-- SELECT get_contact_field_config('tu-project-id');

-- Agregar nuevo campo
-- SELECT add_contact_field(
--     'tu-project-id'::UUID,
--     'nuevo_campo',
--     '["palabra1", "palabra2"]'::JSONB,
--     'string',
--     'Descripción del campo'
-- );

-- Deshabilitar un campo
-- UPDATE contact_field_configs SET enabled = false WHERE project_id = 'tu-project-id' AND field_name = 'campo_a_deshabilitar'; 