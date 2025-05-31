-- Función para búsqueda semántica en search_items
-- Versión 20: Optimizada para la nueva estructura de tabla

CREATE OR REPLACE FUNCTION match_documents_v20(
  query_embedding vector(1536),
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

-- Crear índice si no existe para optimizar la búsqueda
CREATE INDEX IF NOT EXISTS search_items_embedding_cosine_idx 
ON search_items 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);