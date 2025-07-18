-- Función optimizada para búsqueda híbrida de productos
-- Combina la potencia de búsqueda semántica con filtros SQL eficientes

CREATE OR REPLACE FUNCTION search_products_hybrid(
  project_id_filter uuid,  -- Parámetro requerido primero
  -- Parámetros opcionales después
  query_embedding vector(384) DEFAULT NULL,
  query_text text DEFAULT NULL,
  -- Filtros exactos SQL
  category_filter text DEFAULT NULL,
  min_price numeric DEFAULT NULL,
  max_price numeric DEFAULT NULL,
  in_stock_only boolean DEFAULT false,
  tags_filter text[] DEFAULT NULL,
  sku_filter text DEFAULT NULL,
  -- Control de búsqueda
  use_semantic_search boolean DEFAULT true,
  match_count int DEFAULT 20,
  similarity_threshold float DEFAULT 0.3
)
RETURNS TABLE (
  id uuid,
  title text,
  description text,
  price numeric,
  currency varchar(5),
  sku text,
  stock numeric,
  category text,
  tags text[],
  images jsonb,
  metadata jsonb,
  similarity float,
  relevance_score float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH filtered_products AS (
    -- Primero aplicar todos los filtros SQL (muy eficiente)
    SELECT 
      p.*,
      CASE 
        WHEN use_semantic_search AND query_embedding IS NOT NULL THEN
          1 - (p.embedding <=> query_embedding)
        ELSE 
          1.0
      END as semantic_similarity
    FROM search_items p
    WHERE 
      p.type = 'product'
      AND p.project_id = project_id_filter
      -- Filtros exactos eficientes
      AND (category_filter IS NULL OR p.category = category_filter)
      AND (min_price IS NULL OR p.price >= min_price)
      AND (max_price IS NULL OR p.price <= max_price)
      AND (NOT in_stock_only OR p.stock > 0)
      AND (tags_filter IS NULL OR p.tags && tags_filter)
      AND (sku_filter IS NULL OR p.sku = sku_filter)
  ),
  scored_products AS (
    SELECT 
      fp.*,
      -- Calcular score de relevancia combinado
      CASE
        WHEN query_text IS NOT NULL THEN
          (
            -- Score por coincidencia de texto
            (CASE WHEN fp.title ILIKE '%' || query_text || '%' THEN 0.5 ELSE 0 END) +
            (CASE WHEN fp.description ILIKE '%' || query_text || '%' THEN 0.3 ELSE 0 END) +
            (CASE WHEN fp.sku = query_text THEN 1.0 ELSE 0 END) +
            -- Score semántico si está habilitado
            (CASE WHEN use_semantic_search THEN fp.semantic_similarity * 0.7 ELSE 0 END)
          )
        ELSE
          fp.semantic_similarity
      END as total_relevance
    FROM filtered_products fp
    WHERE 
      -- Solo incluir si cumple el umbral de similitud semántica
      (NOT use_semantic_search OR fp.semantic_similarity >= similarity_threshold)
      -- O si hay coincidencia de texto
      OR (query_text IS NOT NULL AND (
        fp.title ILIKE '%' || query_text || '%' OR
        fp.description ILIKE '%' || query_text || '%' OR
        fp.sku = query_text
      ))
  )
  SELECT 
    sp.id,
    sp.title,
    sp.description,
    sp.price,
    sp.currency,
    sp.sku,
    sp.stock,
    sp.category,
    sp.tags,
    sp.images,
    sp.metadata,
    sp.semantic_similarity as similarity,
    sp.total_relevance as relevance_score
  FROM scored_products sp
  ORDER BY 
    sp.total_relevance DESC,
    sp.price ASC
  LIMIT match_count;
END;
$$;

-- Índices para optimizar rendimiento
CREATE INDEX IF NOT EXISTS idx_products_category ON search_items(category) WHERE type = 'product';
CREATE INDEX IF NOT EXISTS idx_products_price ON search_items(price) WHERE type = 'product';
CREATE INDEX IF NOT EXISTS idx_products_stock ON search_items(stock) WHERE type = 'product';
CREATE INDEX IF NOT EXISTS idx_products_sku ON search_items(sku) WHERE type = 'product';
CREATE INDEX IF NOT EXISTS idx_products_tags ON search_items USING GIN(tags) WHERE type = 'product';

-- Función SQL pura para búsquedas exactas (más rápida para filtros simples)
CREATE OR REPLACE FUNCTION search_products_exact(
  project_id_filter uuid,
  category_filter text DEFAULT NULL,
  min_price numeric DEFAULT NULL,
  max_price numeric DEFAULT NULL,
  in_stock_only boolean DEFAULT false,
  order_by text DEFAULT 'price_asc',
  match_count int DEFAULT 50
)
RETURNS TABLE (
  id uuid,
  title text,
  description text,
  price numeric,
  currency varchar(5),
  sku text,
  stock numeric,
  category text,
  tags text[],
  images jsonb,
  metadata jsonb
)
LANGUAGE sql
STABLE
AS $$
  SELECT 
    id,
    title,
    description,
    price,
    currency,
    sku,
    stock,
    category,
    tags,
    images,
    metadata
  FROM search_items
  WHERE 
    type = 'product'
    AND project_id = project_id_filter
    AND (category_filter IS NULL OR category = category_filter)
    AND (min_price IS NULL OR price >= min_price)
    AND (max_price IS NULL OR price <= max_price)
    AND (NOT in_stock_only OR stock > 0)
  ORDER BY 
    CASE order_by
      WHEN 'price_asc' THEN price
      WHEN 'price_desc' THEN -price
      WHEN 'stock_asc' THEN stock
      WHEN 'stock_desc' THEN -stock
      ELSE price
    END
  LIMIT match_count;
$$;

-- Ejemplo de uso para búsqueda semántica + filtros
/*
SELECT * FROM search_products_hybrid(
  project_id_filter := '123e4567-e89b-12d3-a456-426614174000',
  query_embedding := (SELECT embedding FROM get_embedding('laptop gaming')),
  query_text := 'laptop gaming',
  category_filter := 'Electronics',
  min_price := 500,
  max_price := 2000,
  in_stock_only := true
);
*/

-- Ejemplo de uso para búsqueda exacta (más rápida)
/*
SELECT * FROM search_products_exact(
  project_id_filter := '123e4567-e89b-12d3-a456-426614174000',
  category_filter := 'Electronics',
  min_price := 500,
  max_price := 2000,
  in_stock_only := true,
  order_by := 'price_asc'
);
*/