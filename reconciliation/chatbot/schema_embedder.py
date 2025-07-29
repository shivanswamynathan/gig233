import logging
from typing import List, Dict, Any
from .models import TableSchema
from .llm_config import get_llm_config
from django.db import transaction
import numpy as np
from django.db import connection

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
        """Dynamic table selection based on question keywords"""
        try:
            question_lower = question.lower()
            
            # Dynamic keyword mapping to tables
            table_keywords = {
                'invoice_grn_reconciliation': [
                    'gst', 'vendor', 'invoice level', 'header', 'approval', 'perfect match',
                    'partial match', 'total variance', 'reconciliation status'
                ],
                'invoice_item_reconciliation': [
                    'item', 'description', 'hsn', 'quantity', 'unit price', 'line item',
                    'item level', 'matching score'
                ]
            }
            
            # Score each table based on question content
            table_scores = {}
            for table_name, keywords in table_keywords.items():
                score = 0
                for keyword in keywords:
                    if keyword in question_lower:
                        score += 1
                table_scores[table_name] = score
            
            # Get table schemas and add scores
            from .table_schemas import get_table_schemas
            all_schemas = get_table_schemas()
            
            relevant_tables = []
            for schema in all_schemas:
                table_name = schema['table_name']
                score = table_scores.get(table_name, 0)
                
                # Add base relevance if no keywords matched
                if score == 0:
                    score = 0.5
                
                relevant_tables.append({
                    'table_name': table_name,
                    'schema_description': schema['schema_description'],
                    'columns_info': schema['columns_info'],
                    'sample_questions': schema['sample_questions'],
                    'similarity_score': score
                })
            
            # Sort by score and return top_k
            relevant_tables.sort(key=lambda x: x['similarity_score'], reverse=True)
            result = relevant_tables[:top_k]
            
            logger.info(f"Dynamic table selection for '{question}':")
            for table in result:
                logger.info(f"  - {table['table_name']}: score {table['similarity_score']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in dynamic table selection: {e}")
            return self._get_fallback_tables()

    
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
                    'similarity_score': 0.8
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