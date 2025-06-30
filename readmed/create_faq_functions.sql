-- Funciones para búsqueda semántica de FAQs
-- Estas funciones deben ejecutarse en la base de datos PostgreSQL con la extensión pgvector

-- Eliminar funciones existentes si existen
DROP FUNCTION IF EXISTS search_faqs_semantic(text, uuid, float, int, int);
DROP FUNCTION IF EXISTS count_faqs_semantic(text, uuid, float);
DROP FUNCTION IF EXISTS update_embedding_vector(uuid, text);

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