-- Script para crear la función de búsqueda unificada
-- Ejecutar este script en tu base de datos PostgreSQL con pgvector

-- Habilitar la extensión vector si no está habilitada
CREATE EXTENSION IF NOT EXISTS vector;

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

-- Comentario sobre la función
COMMENT ON FUNCTION search_all_content_unified IS 'Función unificada para buscar en documentos, FAQs y productos de una sola vez. Combina búsqueda semántica y por texto para mejores resultados.';
