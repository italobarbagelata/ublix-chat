import os
from openai import OpenAI
from typing import List
import logging
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from supabase import create_client, Client
from uuid import uuid4

class VectorStoreRetriever:
    """Class to manage the vector store retriever using Supabase."""

    def __init__(self, table_name: str):
        load_dotenv()

        # Initialize environment variables
        self.model = os.getenv("MODEL_ENCODING")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.table_name = table_name
        
        # Initialize OpenAI and embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=384,
            chunk_size=25
        )
        self.client_openai = OpenAI()
        
        # Initialize Supabase client
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Ensure the table exists with proper structure
        self._init_table()
        
    def _init_table(self):
        """Initialize the vector table if it doesn't exist"""
        # Note: You need to create the table manually in Supabase with:
        # CREATE TABLE IF NOT EXISTS documents (
        #     id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        #     content TEXT,
        #     content_vector vector(1536),
        #     filename TEXT,
        #     title TEXT,
        #     keywords TEXT,
        #     description TEXT,
        #     question TEXT,
        #     answer TEXT,
        #     metadata JSONB,
        #     project_id TEXT,
        #     created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
        # );
        # CREATE INDEX ON documents USING ivfflat (content_vector vector_cosine_ops) WITH (lists = 100);
        # CREATE INDEX idx_documents_project_id ON documents(project_id);
        pass

    def delete_documents(self, filename: str) -> None:
        """Delete documents from Supabase by filename."""
        try:
            self.supabase.table(self.table_name)\
                .delete()\
                .eq('filename', filename)\
                .execute()
            logging.info(f"Documents with filename {filename} deleted successfully")
        except Exception as e:
            logging.error(f"Error deleting documents: {str(e)}")

    def _process_embedding(self, query: str):
        """Get metadata of query embedded"""
        return self.client_openai.embeddings.create(
            input=[query], 
            model="text-embedding-3-small",
            dimensions=384
        )

    def retrieve(self, query: str, active_datasources: List[dict]) -> tuple[str, List[int]]:
        """Apply vector similarity search and retrieve relevant documents.

        Args:
            query (str): user question
            active_datasources (List[dict]): list of active data sources to filter by

        Returns:
            tuple[str, List[int]]: processed text and embedding result
        """
        logging.info("Init retrieve")
        
        # Get query embedding
        self.embedding_result = self._process_embedding(query)
        query_embedding = self.embedding_result.data[0].embedding

        # Prepare filename filter
        filenames = [str(ds.get("filename", "")).strip() for ds in active_datasources]
        
        try:
            # Perform vector similarity search
            rpc_response = self.supabase.rpc(
                'match_documents',
                {
                    'query_embedding': query_embedding,
                    'match_count': 8,
                    'file_names': filenames
                }
            ).execute()

            if rpc_response.data:
                contents = [item['content'] for item in rpc_response.data]
                response = "\n###\n".join(contents)
                logging.info("End retrieve process.")
            else:
                response = ""
                logging.info("No matching documents found.")

            return response, self.embedding_result

        except Exception as e:
            logging.error(f"Error in vector search: {str(e)}")
            return "", self.embedding_result

    def add_documents(self, documents: List[dict]) -> None:
        """Add documents to the vector store.
        
        Args:
            documents (List[dict]): List of documents with content and metadata
        """
        try:
            for doc in documents:
                # Generate embedding for the content
                embedding = self.embeddings.embed_query(doc['content'])
                
                # Prepare document for insertion
                document_data = {
                    'id': str(uuid4()),
                    'content': doc['content'],
                    'content_vector': embedding,
                    'filename': doc.get('filename', ''),
                    'title': doc.get('title', ''),
                    'keywords': doc.get('keywords', ''),
                    'description': doc.get('description', ''),
                    'question': doc.get('question', ''),
                    'answer': doc.get('answer', ''),
                    'metadata': doc.get('metadata', {}),
                    'project_id': doc.get('project_id')
                }
                
                # Insert document into Supabase
                self.supabase.table(self.table_name)\
                    .insert(document_data)\
                    .execute()
                
            logging.info(f"Successfully added {len(documents)} documents to the vector store")
        except Exception as e:
            logging.error(f"Error adding documents: {str(e)}")
            raise Exception(f"Error adding documents to vector store: {str(e)}")
