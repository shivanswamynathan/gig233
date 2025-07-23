# reconciliation/chatbot/services.py
import logging
import time
from typing import Dict, Any, List
from django.db import connection
from .models import ChatConversation
from .llm_config import get_llm_config
from .schema_embedder import get_schema_embedder
import uuid

logger = logging.getLogger(__name__)

class ChatbotQueryService:
    """Main service for processing chatbot queries"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.schema_embedder = get_schema_embedder()
    
    def process_question(self, question: str, session_id: str = None) -> Dict[str, Any]:
        """
        Process a user question and return a natural language response
        
        Args:
            question: User's question
            session_id: Optional session ID for conversation context
            
        Returns:
            Dictionary with response data
        """
        start_time = time.time()
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Processing question: {question}")
            
            # Step 1: Find relevant tables using semantic search
            relevant_tables = self.schema_embedder.find_relevant_tables(question, top_k=2)
            
            if not relevant_tables:
                return self._create_error_response(
                    question, session_id, 
                    "I couldn't find any relevant tables for your question. Please try rephrasing it.",
                    start_time
                )
            
            # Step 2: Get conversation context (last 3 messages)
            conversation_context = self._get_conversation_context(session_id)
            
            # Step 3: Generate SQL query using LLM
            try:
                sql_query = self.llm_config.generate_sql(
                    question=question,
                    table_schemas=relevant_tables,
                    conversation_context=conversation_context
                )
            except Exception as e:
                logger.error(f"Error generating SQL: {str(e)}")
                return self._create_error_response(
                    question, session_id,
                    "I had trouble understanding your question. Could you please rephrase it?",
                    start_time
                )
            
            # Step 4: Execute SQL query
            try:
                sql_result = self._execute_sql_safely(sql_query)
            except Exception as e:
                logger.error(f"Error executing SQL: {str(e)}")
                return self._create_error_response(
                    question, session_id,
                    f"I encountered an error while retrieving the data: {str(e)}",
                    start_time, 
                    matched_tables=[t['table_name'] for t in relevant_tables],
                    generated_sql=sql_query
                )
            
            # Step 5: Generate natural language response
            try:
                natural_response = self.llm_config.generate_natural_response(
                    question=question,
                    sql_result=sql_result,
                    sql_query=sql_query
                )
            except Exception as e:
                logger.error(f"Error generating natural response: {str(e)}")
                natural_response = f"I found {len(sql_result)} results, but couldn't format them properly. Here's a summary of the data found."
            
            # Step 6: Save conversation
            processing_time = int((time.time() - start_time) * 1000)
            
            conversation = ChatConversation.objects.create(
                session_id=session_id,
                user_question=question,
                matched_tables=[t['table_name'] for t in relevant_tables],
                generated_sql=sql_query,
                sql_result=sql_result[:100] if sql_result else [],  # Limit stored results
                natural_response=natural_response,
                processing_time_ms=processing_time
            )
            
            logger.info(f"Successfully processed question in {processing_time}ms")
            
            return {
                'success': True,
                'response': natural_response,
                'session_id': session_id,
                'conversation_id': str(conversation.id),
                'metadata': {
                    'matched_tables': [t['table_name'] for t in relevant_tables],
                    'similarity_scores': [t['similarity_score'] for t in relevant_tables],
                    'result_count': len(sql_result) if sql_result else 0,
                    'processing_time_ms': processing_time,
                    'sql_query': sql_query if len(sql_query) < 500 else sql_query[:500] + "..."
                }
            }
            
        except Exception as e:
            logger.error(f"Unexpected error processing question: {str(e)}")
            return self._create_error_response(
                question, session_id,
                "I encountered an unexpected error. Please try again.",
                start_time
            )
    
    def _execute_sql_safely(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute SQL query safely with proper error handling"""
        
        # Basic SQL injection prevention
        dangerous_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE'
        ]
        
        sql_upper = sql_query.upper()
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                raise ValueError(f"Query contains potentially dangerous keyword: {keyword}")
        
        # Limit query complexity
        if sql_query.count('(') > 10 or len(sql_query) > 2000:
            raise ValueError("Query is too complex")
        
        # Add LIMIT if not present
        if 'LIMIT' not in sql_upper and 'TOP' not in sql_upper:
            sql_query += ' LIMIT 100'
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql_query)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))
                
                logger.info(f"SQL query executed successfully, returned {len(result)} rows")
                return result
                
        except Exception as e:
            logger.error(f"SQL execution error: {str(e)}")
            logger.error(f"Query: {sql_query}")
            raise
    
    def _get_conversation_context(self, session_id: str) -> str:
        """Get recent conversation context for better continuity"""
        try:
            recent_conversations = ChatConversation.objects.filter(
                session_id=session_id
            ).order_by('-created_at')[:3]
            
            if not recent_conversations:
                return ""
            
            context_parts = []
            for conv in reversed(list(recent_conversations)):  # Reverse to get chronological order
                context_parts.append(f"Q: {conv.user_question}")
                if conv.natural_response:
                    context_parts.append(f"A: {conv.natural_response[:200]}...")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return ""
    
    def _create_error_response(self, question: str, session_id: str, error_message: str, 
                             start_time: float, matched_tables: List[str] = None, 
                             generated_sql: str = None) -> Dict[str, Any]:
        """Create standardized error response"""
        processing_time = int((time.time() - start_time) * 1000)
        
        # Save error conversation
        try:
            ChatConversation.objects.create(
                session_id=session_id,
                user_question=question,
                matched_tables=matched_tables or [],
                generated_sql=generated_sql,
                natural_response=error_message,
                processing_time_ms=processing_time,
                error_message=error_message
            )
        except Exception as e:
            logger.error(f"Error saving error conversation: {str(e)}")
        
        return {
            'success': False,
            'response': error_message,
            'session_id': session_id,
            'metadata': {
                'matched_tables': matched_tables or [],
                'processing_time_ms': processing_time,
                'error': True
            }
        }
    
    def get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history for a session"""
        try:
            conversations = ChatConversation.objects.filter(
                session_id=session_id
            ).order_by('-created_at')[:limit]
            
            history = []
            for conv in reversed(list(conversations)):  # Reverse to get chronological order
                history.append({
                    'id': str(conv.id),
                    'question': conv.user_question,
                    'response': conv.natural_response,
                    'timestamp': conv.created_at.isoformat(),
                    'processing_time_ms': conv.processing_time_ms,
                    'matched_tables': conv.matched_tables,
                    'error': bool(conv.error_message)
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []


# Global service instance
chatbot_service = None

def get_chatbot_service():
    """Get or create global chatbot service instance"""
    global chatbot_service
    if chatbot_service is None:
        chatbot_service = ChatbotQueryService()
    return chatbot_service