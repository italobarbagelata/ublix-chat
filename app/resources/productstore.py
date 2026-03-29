import os
from openai import OpenAI
from typing import List
import logging
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from app.database import SyncDatabase
from uuid import uuid4

class ProductStoreRetriever:
    """Class to manage the product store retriever using direct PostgreSQL."""

    def __init__(self, table_name: str = "products"):
        load_dotenv()

        # Initialize environment variables
        self.model = os.getenv("MODEL_ENCODING")
        self.table_name = table_name

        # Initialize OpenAI and embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=384,
            chunk_size=25
        )
        # Inicializar cliente OpenAI
        self.client_openai = OpenAI()

        # Initialize database client
        self.db = SyncDatabase()

    def delete_products(self, source_url: str) -> None:
        """Delete products from database by source_url."""
        try:
            self.db.table(self.table_name)\
                .delete()\
                .eq('source_url', source_url)\
                .execute()
            logging.info(f"Products with source_url {source_url} deleted successfully")
        except Exception as e:
            logging.error(f"Error deleting products: {str(e)}")

    def _process_embedding(self, query: str):
        """Get metadata of query embedded"""
        return self.client_openai.embeddings.create(
            input=[query],
            model="text-embedding-3-small",
            dimensions=384
        )

    def retrieve(self, query: str, filters: dict = None) -> tuple[List[dict], List[int]]:
        """Apply vector similarity search and retrieve relevant products.

        Args:
            query (str): user search query
            filters (dict): optional filters for the search (category, price range, etc.)

        Returns:
            tuple[List[dict], List[int]]: matched products and embedding result
        """
        logging.info("Init product retrieve")

        # Get query embedding
        self.embedding_result = self._process_embedding(query)
        query_embedding = self.embedding_result.data[0].embedding

        try:
            # Base RPC parameters
            rpc_params = {
                'query_embedding': query_embedding,
                'match_count': 8
            }

            # Add category filter if provided
            if filters and 'category' in filters:
                rpc_params['category_filter'] = filters['category']

            # Add price range if provided
            if filters and 'min_price' in filters and 'max_price' in filters:
                rpc_params['min_price'] = filters['min_price']
                rpc_params['max_price'] = filters['max_price']

            # Perform vector similarity search
            rpc_response = self.db.rpc(
                'match_products',
                rpc_params
            ).execute()

            if rpc_response.data:
                products = rpc_response.data
                logging.info(f"Found {len(products)} matching products.")
                return products, self.embedding_result
            else:
                logging.info("No matching products found.")
                return [], self.embedding_result

        except Exception as e:
            logging.error(f"Error in product vector search: {str(e)}")
            return [], self.embedding_result

    def add_products(self, products: List[dict]) -> None:
        """Add products to the vector store."""
        try:
            for product in products:
                # Generate embedding for the content (description + content)
                content_to_embed = f"{product.get('title', '')} {product.get('description', '')} {product.get('content', '')}"
                embedding = self.embeddings.embed_query(content_to_embed)

                # Prepare product for insertion
                product_data = {
                    'id': str(uuid4()),
                    'title': product.get('title', ''),
                    'description': product.get('description', ''),
                    'content': product.get('content', ''),
                    'content_vector': embedding,
                    'price': product.get('price'),
                    'currency': product.get('currency', 'CLP'),
                    'sku': product.get('sku', ''),
                    'category': product.get('category', ''),
                    'tags': product.get('tags', []),
                    'images': product.get('images', {}),
                    'metadata': product.get('metadata', {}),
                    'source_url': product.get('source_url', ''),
                    'project_id': product.get('project_id')
                }

                # Insert product into database
                self.db.table(self.table_name)\
                    .insert(product_data)\
                    .execute()

            logging.info(f"Successfully added {len(products)} products to the product store")
        except Exception as e:
            logging.error(f"Error adding products: {str(e)}")
            raise Exception(f"Error adding products to product store: {str(e)}")

    def search_by_category(self, category: str, limit: int = 20) -> List[dict]:
        """Search products by category."""
        try:
            response = self.db.table(self.table_name)\
                .select('*')\
                .eq('category', category)\
                .limit(limit)\
                .execute()

            return response.data
        except Exception as e:
            logging.error(f"Error searching products by category: {str(e)}")
            return []

    def search_by_price_range(self, min_price: float, max_price: float, limit: int = 20) -> List[dict]:
        """Search products by price range."""
        try:
            response = self.db.table(self.table_name)\
                .select('*')\
                .gte('price', min_price)\
                .lte('price', max_price)\
                .limit(limit)\
                .execute()

            return response.data
        except Exception as e:
            logging.error(f"Error searching products by price range: {str(e)}")
            return []
