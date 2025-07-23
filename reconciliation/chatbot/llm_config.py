# reconciliation/chatbot/llm_config.py
import os
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class LLMConfig:
    """Central configuration for all LLM operations"""
    
    def __init__(self):
        # Gemini configuration
        self.api_key = getattr(settings, 'GOOGLE_API_KEY', None) or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be set in Django settings or environment variables")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Embedding model for semantic search
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        logger.info("LLM configuration initialized successfully")
    
    def get_embedding(self, text: str) -> list:
        """Generate embedding for given text"""
        try:
            embedding = self.embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def generate_sql(self, question: str, table_schemas: list, conversation_context: str = None) -> str:
        """Generate SQL query using Gemini"""
        try:
            schema_info = "\n\n".join([
                f"Table: {schema['table_name']}\n"
                f"Description: {schema['schema_description']}\n"
                f"Columns: {schema['columns_info']}\n"
                f"Sample Questions: {schema['sample_questions']}"
                for schema in table_schemas
            ])
            
            context_section = f"\n\nConversation Context:\n{conversation_context}" if conversation_context else ""
            
            prompt = f"""
You are an expert SQL query generator for an invoice reconciliation system.

AVAILABLE TABLES AND SCHEMAS:
{schema_info}

USER QUESTION: {question}{context_section}

INSTRUCTIONS:
1. Generate a PostgreSQL query that answers the user's question
2. Use ONLY the tables and columns provided above
3. Use proper PostgreSQL syntax and functions
4. Include appropriate WHERE clauses, JOINs, and aggregations as needed
5. Limit results to reasonable amounts (e.g., TOP 50 for lists)
6. Use table aliases for readability
7. Handle NULL values appropriately
8. Return ONLY the SQL query, no explanations or markdown

IMPORTANT FIELD MAPPINGS:
- For ItemWiseGrn: use 'grn_no', 'po_no', 'supplier', 'item_name', 'received_qty', 'price', 'total'
- For InvoiceData: use 'invoice_number', 'po_number', 'vendor_name', 'invoice_total_post_gst'
- For InvoiceItemData: use 'invoice_data_id', 'item_description', 'quantity', 'unit_price', 'item_total_amount'

SQL Query:
"""
            
            response = self.gemini_model.generate_content(prompt)
            sql_query = response.text.strip()
            
            # Clean up the SQL query
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
            logger.info(f"Generated SQL: {sql_query}")
            return sql_query
            
        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            raise
    
    def generate_natural_response(self, question: str, sql_result: list, sql_query: str) -> str:
        """Convert SQL results to natural language response"""
        try:
            if not sql_result:
                return "I couldn't find any data matching your query. Please try rephrasing your question or check if the data exists."
            
            # Prepare result summary
            result_count = len(sql_result)
            sample_data = sql_result[:3] if len(sql_result) > 3 else sql_result
            
            prompt = f"""
Convert the following SQL query result into a natural, conversational response.

USER QUESTION: {question}
SQL QUERY EXECUTED: {sql_query}
RESULT COUNT: {result_count} records
SAMPLE DATA: {sample_data}

INSTRUCTIONS:
1. Provide a clear, conversational answer to the user's question
2. Include key insights from the data
3. Mention the total count if relevant
4. Use bullet points or tables if helpful for readability
5. Be concise but informative
6. If showing monetary amounts, format them nicely (e.g., ₹1,23,456)
7. Round numbers appropriately for readability

Natural Response:
"""
            
            response = self.gemini_model.generate_content(prompt)
            natural_response = response.text.strip()
            
            logger.info(f"Generated natural response for {result_count} records")
            return natural_response
            
        except Exception as e:
            logger.error(f"Error generating natural response: {str(e)}")
            return f"I found {len(sql_result)} results for your question, but couldn't format the response properly. Here's the raw data: {sql_result[:3]}"


# Global LLM instance
llm_config = None

def get_llm_config():
    """Get or create global LLM configuration instance"""
    global llm_config
    if llm_config is None:
        llm_config = LLMConfig()
    return llm_config