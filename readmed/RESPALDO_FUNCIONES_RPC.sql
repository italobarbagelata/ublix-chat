-- =====================================================
-- 🗂️ RESPALDO COMPLETO DE FUNCIONES RPC UBLIX-CHAT
-- =====================================================
-- Fecha de respaldo: 2025-01-28
-- Descripción: Todas las funciones PostgreSQL/RPC del proyecto organizadas por categoría
-- Uso: Para restaurar ejecutar cada sección según sea necesario
-- =====================================================

-- =====================================================
-- 📋 ÍNDICE DE FUNCIONES
-- =====================================================
-- 1. FUNCIONES DE BÚSQUEDA Y MATCHING
--    - match_documents_v20
--    - match_documents_hybrid  
--    - search_by_title_similarity
--    - search_all_content_unified
--
-- 2. FUNCIONES DE FAQ
--    - search_faqs_semantic
--    - count_faqs_semantic
--    - update_embedding_vector
--
-- 3. FUNCIONES DE CONTACTOS
--    - get_contact_field_config
--    - add_contact_field
--    - validate_additional_fields
--    - update_contact_field_configs_updated_at
--
-- 4. EXTENSIONES Y TABLAS REQUERIDAS
--    - Extensiones necesarias
--    - Tabla search_items
--    - Tabla contact_field_configs
-- =====================================================

-- =====================================================
-- 🔧 EXTENSIONES REQUERIDAS
-- =====================================================

-- Extensión para vectores semánticos
CREATE EXTENSION IF NOT EXISTS vector;

-- Extensión para similitud de texto
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =====================================================
-- 📊 TABLAS PRINCIPALES
-- =====================================================

-- Tabla principal para elementos de búsqueda
CREATE TABLE IF NOT EXISTS public.search_items (
  id uuid primary key default extensions.uuid_generate_v4(),
  type text not null,
  title text,
  description text,
  content text,
  embedding vector(384),
  price numeric,
  currency varchar(5) default 'CLP',
  sku text,
  category text,
  tags text[],
  images jsonb,
  filename text,
  question text,
  answer text,
  source_url text,
  metadata jsonb,
  created_at timestamptz default timezone('America/Santiago', now()),
  project_id uuid,
  constraint search_items_type_check check (
    type in ('product', 'document', 'faq')
  )
);

-- Índice vectorial para búsqueda semántica
CREATE INDEX IF NOT EXISTS search_items_embedding_idx
  ON public.search_items
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);



-- =====================================================
-- 🔍 1. FUNCIONES DE BÚSQUEDA Y MATCHING
-- =====================================================

-- Función principal de matching de documentos v20
CREATE OR REPLACE FUNCTION match_documents_v20(
  query_embedding vector(384),
  match_count int DEFAULT 5,
  project_id_filter uuid DEFAULT NULL,
  type_filter text DEFAULT NULL,
  category_filter text DEFAULT NULL,
  min_price numeric DEFAULT NULL,
  max_price numeric DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  type text,
  title text,
  description text,
  content text,
  price numeric,
  currency varchar(5),
  sku text,
  stock numeric,
  category text,
  tags text[],
  images jsonb,
  filename text,
  question text,
  answer text,
  source_url text,
  metadata jsonb,
  created_at timestamptz,
  project_id uuid,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    si.id,
    si.type,
    si.title,
    si.description,
    si.content,
    si.price,
    si.currency,
    si.sku,
    si.stock,
    si.category,
    si.tags,
    si.images,
    si.filename,
    si.question,
    si.answer,
    si.source_url,
    si.metadata,
    si.created_at,
    si.project_id,
    1 - (si.embedding <=> query_embedding) as similarity
  FROM search_items si
  WHERE 
    si.embedding IS NOT NULL
    AND (project_id_filter IS NULL OR si.project_id = project_id_filter)
    AND (type_filter IS NULL OR si.type = type_filter)
    AND (category_filter IS NULL OR si.category = category_filter)
    AND (min_price IS NULL OR si.price >= min_price)
    AND (max_price IS NULL OR si.price <= max_price)
  ORDER BY si.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Función híbrida de matching (vectorial + texto)
CREATE OR REPLACE FUNCTION match_documents_hybrid(
    query_embedding vector(384),
    query_text text,
    match_count int,
    project_id_filter uuid,
    type_filter text,
    category_filter text,
    similarity_threshold double precision
)
RETURNS TABLE (
    id uuid,
    title text,
    description text,
    price double precision,
    currency text,
    stock integer,
    source_url text,
    images text[],
    similarity double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH search_results AS (
        SELECT 
            si.id,
            si.title,
            si.description,
            si.price::double precision,
            si.currency::text,
            si.stock::integer,
            si.source_url,
            CASE 
                WHEN jsonb_typeof(si.images) = 'array' THEN 
                    (SELECT array_agg(value::text) FROM jsonb_array_elements_text(si.images))
                ELSE 
                    ARRAY[]::text[]
            END as images,
            GREATEST(
                (si.embedding <=> query_embedding) * -1 + 1,
                CASE 
                    WHEN si.title ILIKE '%' || query_text || '%' THEN 0.9
                    WHEN si.description ILIKE '%' || query_text || '%' THEN 0.8
                    ELSE 0
                END
            )::double precision as similarity
        FROM search_items si
        WHERE si.project_id = project_id_filter
            AND si.type = type_filter
            AND (category_filter IS NULL OR si.category = category_filter)
            AND (
                si.title ILIKE '%' || query_text || '%'
                OR si.description ILIKE '%' || query_text || '%'
                OR (si.embedding <=> query_embedding) * -1 + 1 > similarity_threshold
            )
    )
    SELECT * FROM search_results
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Función de búsqueda por similitud de título
CREATE OR REPLACE FUNCTION search_by_title_similarity(
    search_query text,
    query_embedding vector(384),
    project_id_filter uuid,
    similarity_threshold float DEFAULT 0.3,
    result_limit int DEFAULT 15,
    text_weight float DEFAULT 1.0,
    vector_weight float DEFAULT 1.0,
    rrf_k int DEFAULT 50
)
RETURNS TABLE (
    id uuid,
    title text,
    description text,
    price numeric,
    currency varchar(5),
    stock numeric,
    images jsonb,
    source_url text,
    similarity_score double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH text_search AS (
        SELECT 
            si.id,
            si.title,
            si.description,
            si.price,
            si.currency,
            si.stock,
            si.images,
            si.source_url,
            similarity(si.title, search_query) as text_score,
            row_number() OVER (ORDER BY similarity(si.title, search_query) DESC) as text_rank
        FROM search_items si
        WHERE 
            si.type = 'product'
            AND si.project_id = project_id_filter
            AND similarity(si.title, search_query) > similarity_threshold
    ),
    vector_search AS (
        SELECT 
            si.id,
            si.title,
            si.description,
            si.price,
            si.currency,
            si.stock,
            si.images,
            si.source_url,
            1 - (si.embedding <=> query_embedding) as vector_score,
            row_number() OVER (ORDER BY si.embedding <=> query_embedding) as vector_rank
        FROM search_items si
        WHERE 
            si.type = 'product'
            AND si.project_id = project_id_filter
            AND si.embedding IS NOT NULL
    )
    SELECT 
        COALESCE(ts.id, vs.id) as id,
        COALESCE(ts.title, vs.title) as title,
        COALESCE(ts.description, vs.description) as description,
        COALESCE(ts.price, vs.price) as price,
        COALESCE(ts.currency, vs.currency) as currency,
        COALESCE(ts.stock, vs.stock) as stock,
        COALESCE(ts.images, vs.images) as images,
        COALESCE(ts.source_url, vs.source_url) as source_url,
        (
            COALESCE(1.0 / (rrf_k + ts.text_rank), 0.0) * text_weight +
            COALESCE(1.0 / (rrf_k + vs.vector_rank), 0.0) * vector_weight
        )::double precision as similarity_score
    FROM text_search ts
    FULL OUTER JOIN vector_search vs ON ts.id = vs.id
    ORDER BY similarity_score DESC
    LIMIT result_limit;
END;
$$;

-- Función unificada para buscar en todos los tipos de contenido
CREATE OR REPLACE FUNCTION search_all_content_unified(
  query_embedding vector(384),
  query_text text,
  project_id_filter uuid,
  content_types text[] DEFAULT ARRAY['document', 'faq', 'product'],
  match_count int DEFAULT 15,
  similarity_threshold float DEFAULT 0.3,
  category_filter text DEFAULT NULL,
  min_price numeric DEFAULT NULL,
  max_price numeric DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  type text,
  title text,
  description text,
  content text,
  price numeric,
  currency varchar(5),
  sku text,
  stock numeric,
  category text,
  tags text[],
  images jsonb,
  filename text,
  question text,
  answer text,
  source_url text,
  metadata jsonb,
  created_at timestamptz,
  project_id uuid,
  similarity float,
  content_preview text
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    si.id,
    si.type,
    si.title,
    si.description,
    si.content,
    si.price,
    si.currency,
    si.sku,
    si.stock,
    si.category,
    si.tags,
    si.images,
    si.filename,
    si.question,
    si.answer,
    si.source_url,
    si.metadata,
    si.created_at,
    si.project_id,
    1 - (si.embedding <=> query_embedding) as similarity,
    CASE 
      WHEN si.type = 'faq' AND si.question IS NOT NULL AND si.answer IS NOT NULL THEN
        'Pregunta: ' || si.question || ' | Respuesta: ' || LEFT(si.answer, 200)
      WHEN si.type = 'document' AND si.content IS NOT NULL THEN
        LEFT(si.content, 200)
      WHEN si.type = 'product' AND si.description IS NOT NULL THEN
        si.description
      ELSE
        COALESCE(si.title, 'Sin contenido')
    END as content_preview
  FROM search_items si
  WHERE 
    si.embedding IS NOT NULL
    AND si.project_id = project_id_filter
    AND si.type = ANY(content_types)
    AND (category_filter IS NULL OR si.category = category_filter)
    AND (min_price IS NULL OR si.price >= min_price)
    AND (max_price IS NULL OR si.price <= max_price)
    AND (
      -- Búsqueda semántica
      (1 - (si.embedding <=> query_embedding)) >= similarity_threshold
      OR
      -- Búsqueda por texto en título y descripción
      si.title ILIKE '%' || query_text || '%'
      OR si.description ILIKE '%' || query_text || '%'
      OR (si.type = 'faq' AND si.question ILIKE '%' || query_text || '%')
      OR (si.type = 'faq' AND si.answer ILIKE '%' || query_text || '%')
      OR (si.type = 'document' AND si.content ILIKE '%' || query_text || '%')
    )
  ORDER BY 
    -- Priorizar por tipo: FAQ primero, luego documentos, luego productos
    CASE si.type 
      WHEN 'faq' THEN 1
      WHEN 'document' THEN 2
      WHEN 'product' THEN 3
      ELSE 4
    END,
    -- Luego por similitud
    si.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- =====================================================
-- ❓ 2. FUNCIONES DE FAQ
-- =====================================================

-- Función para buscar FAQs por similitud semántica
CREATE OR REPLACE FUNCTION search_faqs_semantic(
    query_embedding text,
    project_id_param uuid,
    similarity_threshold float DEFAULT 0.7,
    limit_param int DEFAULT 10,
    offset_param int DEFAULT 0
)
RETURNS TABLE(
    id uuid,
    question text,
    answer text,
    title text,
    description text,
    content text,
    metadata jsonb,
    created_at timestamptz,
    project_id uuid,
    similarity_score float
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        si.id,
        si.question,
        si.answer,
        si.title,
        si.description,
        si.content,
        si.metadata,
        si.created_at,
        si.project_id,
        1 - (si.embedding <=> query_embedding::vector) as similarity_score
    FROM search_items si
    WHERE si.type = 'faq'
        AND si.project_id = project_id_param
        AND si.embedding IS NOT NULL
        AND 1 - (si.embedding <=> query_embedding::vector) >= similarity_threshold
    ORDER BY si.embedding <=> query_embedding::vector
    LIMIT limit_param
    OFFSET offset_param;
END;
$$ LANGUAGE plpgsql;

-- Función para contar FAQs por similitud semántica
CREATE OR REPLACE FUNCTION count_faqs_semantic(
    query_embedding text,
    project_id_param uuid,
    similarity_threshold float DEFAULT 0.7
)
RETURNS TABLE(count bigint) AS $$
BEGIN
    RETURN QUERY
    SELECT COUNT(*)::bigint
    FROM search_items si
    WHERE si.type = 'faq'
        AND si.project_id = project_id_param
        AND si.embedding IS NOT NULL
        AND 1 - (si.embedding <=> query_embedding::vector) >= similarity_threshold;
END;
$$ LANGUAGE plpgsql;

-- Función para actualizar el embedding como vector
CREATE OR REPLACE FUNCTION update_embedding_vector(
    product_id uuid,
    vector_data text
)
RETURNS void AS $$
BEGIN
    UPDATE search_items 
    SET embedding = vector_data::vector 
    WHERE id = product_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 👤 3. FUNCIONES DE CONTACTOS
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

-- Función para validar campos adicionales
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

-- Función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_contact_field_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 🔧 4. TRIGGERS NECESARIOS
-- =====================================================

-- Trigger para validar additional_fields al insertar/actualizar
DROP TRIGGER IF EXISTS validate_additional_fields_trigger ON contacts;
CREATE TRIGGER validate_additional_fields_trigger
    BEFORE INSERT OR UPDATE ON contacts
    FOR EACH ROW
    EXECUTE FUNCTION validate_additional_fields();

-- Trigger para actualizar updated_at automáticamente
DROP TRIGGER IF EXISTS update_contact_field_configs_updated_at_trigger ON contact_field_configs;
CREATE TRIGGER update_contact_field_configs_updated_at_trigger
    BEFORE UPDATE ON contact_field_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_contact_field_configs_updated_at();

-- =====================================================
-- ✅ 5. VERIFICACIONES
-- =====================================================

-- Verificar funciones de búsqueda
SELECT 'search_all_content_unified' as function_name, 
       proname as exists FROM pg_proc WHERE proname = 'search_all_content_unified'
UNION ALL
SELECT 'match_documents_v20' as function_name,
       proname as exists FROM pg_proc WHERE proname = 'match_documents_v20'
UNION ALL  
SELECT 'get_contact_field_config' as function_name,
       proname as exists FROM pg_proc WHERE proname = 'get_contact_field_config';

-- Verificar tablas principales
SELECT 'search_items' as table_name, 
       CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'search_items') 
            THEN 'EXISTS' ELSE 'MISSING' END as status
UNION ALL
SELECT 'contact_field_configs' as table_name,
       CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'contact_field_configs')
            THEN 'EXISTS' ELSE 'MISSING' END as status;

-- =====================================================
-- 📖 6. EJEMPLOS DE USO
-- =====================================================

/*
-- Ejemplo: Búsqueda unificada
SELECT * FROM search_all_content_unified(
    '[0.1,0.2,...]'::vector(384),
    'productos tecnológicos',
    'project-id'::uuid
);

-- Ejemplo: Configuración de contactos  
SELECT get_contact_field_config('project-id'::uuid);

-- Ejemplo: Agregar campo personalizado
SELECT add_contact_field(
    'project-id'::uuid,
    'hobby',
    '["me gusta", "disfruto", "hobby"]'::jsonb,
    'string',
    'Hobby favorito del usuario'
);
*/

-- =====================================================
-- 🏁 FIN DEL RESPALDO
-- =====================================================
-- Total de funciones respaldadas: 11
-- Fecha: 2025-01-28
-- ===================================================== 