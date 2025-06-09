-- Función para búsqueda semántica en search_items
-- Versión 20: Optimizada para la nueva estructura de tabla

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







create extension if not exists vector;

-- 2. Crear la tabla principal
create table if not exists public.search_items (
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
create index if not exists search_items_embedding_idx
  on public.search_items
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);