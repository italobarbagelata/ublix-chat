create extension if not exists vector;

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



-- Habilitar la extensión pg_trgm para similitud de texto
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Función para búsqueda por similitud de título
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