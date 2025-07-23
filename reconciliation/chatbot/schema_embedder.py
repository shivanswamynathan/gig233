# reconciliation/chatbot/schema_embedder.py
import logging
from typing import List, Dict, Any
from .models import TableSchema
from .llm_config import get_llm_config
from django.db import transaction
import numpy as np

logger = logging.getLogger(__name__)

class SchemaEmbedder:
    """Service to embed and store table schemas"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
    
    def initialize_schemas(self):
        """Initialize embeddings for all predefined schemas"""
        logger.info("Initializing schema embeddings...")
        
        # Import schemas from separate file
        from .table_schemas import get_table_schemas
        schemas = get_table_schemas()
        
        # Process each schema
        with transaction.atomic():
            for schema_data in schemas:
                try:
                    # Create embedding text from description and sample questions
                    embedding_text = f"{schema_data['schema_description']} {' '.join(schema_data['sample_questions'])}"
                    embedding = self.llm_config.get_embedding(embedding_text)
                    
                    # Create or update schema record
                    schema, created = TableSchema.objects.update_or_create(
                        table_name=schema_data['table_name'],
                        defaults={
                            'schema_description': schema_data['schema_description'].strip(),
                            'columns_info': schema_data['columns_info'],
                            'sample_questions': schema_data['sample_questions'],
                            'embedding': embedding
                        }
                    )
                    
                    action = "Created" if created else "Updated"
                    logger.info(f"{action} schema embedding for table: {schema_data['table_name']}")
                    
                except Exception as e:
                    logger.error(f"Error processing schema for {schema_data['table_name']}: {str(e)}")
                    raise
        
        logger.info("Schema embedding initialization completed")
    
    def find_relevant_tables(self, question: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Find the most relevant tables for a given question using pgvector similarity"""
        try:
            # Generate embedding for the question
            question_embedding = self.llm_config.get_embedding(question)
            
            # Use pgvector for efficient similarity search
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Use pgvector's cosine distance for similarity search
                cursor.execute("""
                    SELECT 
                        table_name,
                        schema_description,
                        columns_info,
                        sample_questions,
                        1 - (embedding <=> %s) as similarity_score
                    FROM chatbot_table_schema 
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, [question_embedding, question_embedding, top_k])
                
                results = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                
                relevant_tables = []
                for row in results:
                    row_dict = dict(zip(columns, row))
                    relevant_tables.append({
                        'table_name': row_dict['table_name'],
                        'schema_description': row_dict['schema_description'],
                        'columns_info': row_dict['columns_info'],
                        'sample_questions': row_dict['sample_questions'],
                        'similarity_score': float(row_dict['similarity_score'])
                    })
            
            logger.info(f"Found {len(relevant_tables)} relevant tables for question: {question}")
            for table in relevant_tables:
                logger.info(f"  - {table['table_name']}: {table['similarity_score']:.3f}")
            
            return relevant_tables
            
        except Exception as e:
            logger.error(f"Error finding relevant tables: {str(e)}")
            # Fallback to manual calculation if pgvector query fails
            return self._fallback_similarity_search(question, top_k)
    
    def _fallback_similarity_search(self, question: str, top_k: int) -> List[Dict[str, Any]]:
        """Fallback similarity search using numpy when pgvector fails"""
        try:
            import numpy as np
            
            # Generate embedding for the question
            question_embedding = self.llm_config.get_embedding(question)
            
            # Get all schemas
            schemas = TableSchema.objects.all()
            
            if not schemas:
                logger.warning("No schemas found in database")
                return []
            
            # Calculate similarities using numpy
            similarities = []
            for schema in schemas:
                # Convert VectorField to numpy array
                schema_embedding = np.array(schema.embedding)
                question_embedding_np = np.array(question_embedding)
                
                similarity = np.dot(schema_embedding, question_embedding_np) / (
                    np.linalg.norm(schema_embedding) * np.linalg.norm(question_embedding_np)
                )
                
                similarities.append({
                    'table_name': schema.table_name,
                    'schema_description': schema.schema_description,
                    'columns_info': schema.columns_info,
                    'sample_questions': schema.sample_questions,
                    'similarity_score': float(similarity)
                })
            
            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Fallback similarity search also failed: {str(e)}")
            return []


# Global schema embedder instance
schema_embedder = None

def get_schema_embedder():
    """Get or create global schema embedder instance"""
    global schema_embedder
    if schema_embedder is None:
        schema_embedder = SchemaEmbedder()
    return schema_embedder