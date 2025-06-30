-- =====================================================
-- MIGRACIÓN: Agregar soporte para campos dinámicos en contactos
-- =====================================================

-- 1. Agregar columna additional_fields a la tabla contacts
ALTER TABLE contacts 
ADD COLUMN IF NOT EXISTS additional_fields JSONB DEFAULT '{}';

-- 2. Crear índice para búsquedas eficientes en campos adicionales  
CREATE INDEX IF NOT EXISTS contacts_additional_fields_gin_idx 
ON contacts USING GIN (additional_fields);

-- 3. Agregar comentarios para documentación
COMMENT ON COLUMN contacts.additional_fields IS 'Campos adicionales personalizables por proyecto como JSON. Ejemplos: {"direccion": "Santiago", "edad": 30, "ha_invertido": true}';

-- 4. Función para validar estructura de additional_fields (opcional)
CREATE OR REPLACE FUNCTION validate_additional_fields()
RETURNS trigger AS $$
BEGIN
    -- Validar que additional_fields sea un objeto JSON válido
    IF NEW.additional_fields IS NOT NULL THEN
        -- Verificar que sea un objeto JSON válido
        IF jsonb_typeof(NEW.additional_fields) != 'object' THEN
            RAISE EXCEPTION 'additional_fields debe ser un objeto JSON válido';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. Trigger para validar additional_fields al insertar/actualizar
CREATE TRIGGER validate_additional_fields_trigger
    BEFORE INSERT OR UPDATE ON contacts
    FOR EACH ROW
    EXECUTE FUNCTION validate_additional_fields();

-- =====================================================
-- EJEMPLOS DE USO:
-- =====================================================

-- Ejemplo 1: Bot de Inversiones
-- INSERT INTO contacts (project_id, user_id, name, email, phone_number, additional_fields)
-- VALUES (
--     'proj_inversiones_123',
--     'user_456', 
--     'Juan Pérez',
--     'juan@email.com',
--     '+56912345678',
--     '{"direccion": "Santiago Centro", "edad": 35, "ha_invertido": true, "experiencia_inversion": "2 años"}'
-- );

-- Ejemplo 2: Bot de E-commerce  
-- UPDATE contacts 
-- SET additional_fields = jsonb_set(
--     COALESCE(additional_fields, '{}'),
--     '{producto_interes}', 
--     '"Laptop Gaming"'
-- )
-- WHERE user_id = 'user_456' AND project_id = 'proj_ecommerce_789';

-- Ejemplo 3: Consultar por campos adicionales
-- SELECT name, email, additional_fields->>'direccion' as direccion, 
--        (additional_fields->>'edad')::int as edad
-- FROM contacts 
-- WHERE project_id = 'proj_inversiones_123'
--   AND additional_fields->>'ha_invertido' = 'true';

-- =====================================================
-- VERIFICACIÓN DE LA MIGRACIÓN:
-- =====================================================

-- Verificar que la columna se agregó correctamente
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'contacts' 
  AND column_name = 'additional_fields';

-- Verificar que el índice se creó
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'contacts' 
  AND indexname = 'contacts_additional_fields_gin_idx'; 