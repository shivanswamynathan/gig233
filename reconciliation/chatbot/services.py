import re
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
    """Main service for processing chatbot queries with intelligent analysis"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.schema_embedder = get_schema_embedder()
    
    def process_question(self, question: str, session_id: str = None) -> Dict[str, Any]:
        """
        Process a user question and return intelligent business analysis
        
        Args:
            question: User's question
            session_id: Optional session ID for conversation context
            
        Returns:
            Dictionary with response data including intelligent insights
        """
        start_time = time.time()
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Processing intelligent reconciliation question: {question}")
            
            # Step 1: Find relevant tables using semantic search
            relevant_tables = self.schema_embedder.find_relevant_tables(question, top_k=2)
            
            if not relevant_tables:
                return self._create_error_response(
                    question, session_id, 
                    "No relevant reconciliation data found. Try asking about specific invoices, mismatches, or variances.",
                    start_time
                )
            
            # Step 2: Get conversation context (last 3 messages)
            conversation_context = self._get_conversation_context(session_id)
            
            # Step 3: Generate SQL query using intelligent prompts
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
                    "I had trouble understanding your reconciliation question. Try asking about specific issues like 'Why is invoice INV123 not matching?' or 'Show me variance analysis for last month'.",
                    start_time
                )
            
            # Step 4: Execute SQL query safely
            try:
                sql_result = self._execute_sql_safely(sql_query)
            except Exception as e:
                logger.error(f"Error executing SQL: {str(e)}")
                return self._create_error_response(
                    question, session_id,
                    f"I encountered an error while retrieving the reconciliation data. Please try a simpler query or check if the data exists.",
                    start_time, 
                    matched_tables=[t['table_name'] for t in relevant_tables],
                    generated_sql=sql_query
                )
            
            # Step 5: Generate intelligent business analysis (NOT just natural language response)
            try:
                intelligent_analysis = self.llm_config.generate_intelligent_analysis(
                    question=question,
                    sql_result=sql_result,
                    sql_query=sql_query
                )
                
                # Add business context and recommendations
                enhanced_analysis = self._add_business_context(
                    intelligent_analysis, sql_result, question
                )
                
            except Exception as e:
                logger.error(f"Error generating intelligent analysis: {str(e)}")
                enhanced_analysis = self._create_business_fallback_analysis(sql_result, question)
            
            # Step 6: Save conversation
            processing_time = int((time.time() - start_time) * 1000)

            serializable_result = []
            if sql_result:
                for row in sql_result[:50]:
                    serializable_row = {}
                    for key, value in row.items():
                        if hasattr(value, '__float__'):  # Handle Decimal/numeric types
                            serializable_row[key] = float(value) if value is not None else None
                        else:
                            serializable_row[key] = value
                    serializable_result.append(serializable_row)
            
            conversation = ChatConversation.objects.create(
                session_id=session_id,
                user_question=question,
                matched_tables=[t['table_name'] for t in relevant_tables],
                generated_sql=sql_query,
                sql_result=serializable_result,   # Limit stored results
                natural_response=enhanced_analysis,
                processing_time_ms=processing_time
            )
            
            logger.info(f"Successfully processed intelligent analysis in {processing_time}ms")
            
            return {
                'success': True,
                'response': enhanced_analysis,
                'session_id': session_id,
                'conversation_id': str(conversation.id),
                'metadata': {
                    'matched_tables': [t['table_name'] for t in relevant_tables],
                    'similarity_scores': [t['similarity_score'] for t in relevant_tables],
                    'result_count': len(sql_result) if sql_result else 0,
                    'processing_time_ms': processing_time,
                    'sql_query': sql_query if len(sql_query) < 500 else sql_query[:500] + "...",
                    'analysis_type': self._determine_analysis_type(question),
                    'business_impact': self._assess_business_impact(sql_result, question),
                    'actionable_insights': self._extract_actionable_insights(enhanced_analysis)
                }
            }
            
        except Exception as e:
            logger.error(f"Unexpected error processing intelligent question: {str(e)}")
            return self._create_error_response(
                question, session_id,
                "I encountered an unexpected error while analyzing the reconciliation data. Please try again with a more specific question.",
                start_time
            )
    
    def _execute_sql_safely(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute SQL query safely with reconciliation-specific safety checks"""

        sql_stripped = sql_query.strip()
        if not sql_stripped.upper().startswith('SELECT'):
            raise ValueError("Only SELECT queries are allowed")
        
        statements = [s.strip() for s in sql_query.split(';') if s.strip()]
        if len(statements) > 1:
            raise ValueError("Multiple SQL statements not allowed")
        
        for statement in statements:
            if not statement.upper().startswith('SELECT'):
                raise ValueError("Only SELECT statements are allowed")
        
        # Basic SQL injection prevention
        dangerous_patterns = [
            r'\bDROP\b', r'\bDELETE\b', r'\bINSERT\b', r'\bALTER\b', 
            r'\bCREATE\b', r'\bTRUNCATE\b', r'\bGRANT\b', r'\bREVOKE\b',
            r'\bEXEC\b', r'\bEXECUTE\b'
        ]
        
        sql_upper = sql_query.upper()
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                raise ValueError(f"Query contains prohibited keyword: {pattern}")
        
        if re.search(r'\bUPDATE\s+\w+\s+SET\b', sql_upper):
            raise ValueError("UPDATE statements are not allowed")
        
        # Ensure only reconciliation tables are being queried
        allowed_tables = ['invoice_grn_reconciliation', 'invoice_item_reconciliation']
        query_lower = sql_query.lower()
        
        found_table = False
        for table in allowed_tables:
            if table in query_lower:
                found_table = True
                break
        
        if not found_table:
            raise ValueError("Query must reference reconciliation tables (invoice_grn_reconciliation or invoice_item_reconciliation)")
        
        # Limit query complexity for safety
        if sql_query.count('(') > 15 or len(sql_query) > 3000:
            raise ValueError("Query is too complex - please simplify your request")
        
        # Add LIMIT if not present to prevent large result sets
        if 'LIMIT' not in sql_upper and 'TOP' not in sql_upper:
            sql_query = sql_query.rstrip(';').strip()
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
    
    def _add_business_context(self, analysis: str, sql_result: List[Dict], question: str) -> str:
        """Add minimal business context to keep responses concise"""
        if not sql_result:
            return analysis
        
        try:
            urgency_level = self._assess_urgency(sql_result, question)
            
            # Only add critical alerts, not detailed context
            if urgency_level == 'high':
                return "HIGH PRIORITY: " + analysis
            elif urgency_level == 'medium':
                return "MEDIUM PRIORITY: " + analysis
            else:
                return analysis
                
        except Exception as e:
            logger.error(f"Error adding business context: {str(e)}")
            return analysis
    
    def _create_business_fallback_analysis(self, sql_result: List[Dict], question: str) -> str:
        """Create business-focused fallback analysis when AI analysis fails"""
        try:
            result_count = len(sql_result)
            
            if result_count == 0:
                return "No reconciliation issues found. All records are properly matched within tolerance limits."
            
            # Handle specific cases concisely
            if "perfect match" in question.lower() and "partial match" in question.lower():
                return f"Header shows perfect match but {result_count} items have partial matches due to description/tax variances. Review item-level details and approve if acceptable. Update matching tolerances to reduce manual reviews."
            
            # Quick analysis for other cases
            exceptions = sum(1 for row in sql_result if row.get('is_exception', False))
            total_variance = sum(abs(row.get('total_variance', 0) or 0) for row in sql_result)
            
            if exceptions > 0:
                return f"Found {exceptions} critical exceptions in {result_count} records with ₹{total_variance:,.2f} total variance. Prioritize high-value items and contact vendors for resolution."
            else:
                return f"Identified {result_count} records requiring review with ₹{total_variance:,.2f} total variance. Focus on largest discrepancies first and update tolerances if needed."
                
        except Exception as e:
            logger.error(f"Error creating business fallback analysis: {e}")
            return f"Found {len(sql_result)} records for review. Please examine manually and take appropriate action."
    
    def _assess_urgency(self, sql_result: List[Dict], question: str) -> str:
        """Assess urgency level based on data patterns"""
        try:
            high_urgency_indicators = 0
            
            for row in sql_result:
                # High variance amounts
                variance = abs(row.get('total_variance', 0) or row.get('total_amount_variance', 0))
                if variance > 50000:  # > 50k variance
                    high_urgency_indicators += 1
                
                # Critical exceptions
                if row.get('is_exception'):
                    high_urgency_indicators += 2
                
                # Vendor/GST mismatches (compliance risk)
                if not row.get('vendor_match') or not row.get('gst_match'):
                    high_urgency_indicators += 1
            
            # Check question urgency keywords
            urgent_keywords = ['urgent', 'critical', 'immediate', 'asap', 'emergency']
            if any(keyword in question.lower() for keyword in urgent_keywords):
                high_urgency_indicators += 1
            
            if high_urgency_indicators >= 3:
                return 'high'
            elif high_urgency_indicators >= 1:
                return 'medium'
            else:
                return 'low'
                
        except Exception:
            return 'medium'
    
    def _assess_compliance_risk(self, sql_result: List[Dict]) -> str:
        """Assess compliance risk based on data"""
        try:
            gst_mismatches = 0
            vendor_mismatches = 0
            high_variances = 0
            
            for row in sql_result:
                if not row.get('gst_match', True):
                    gst_mismatches += 1
                if not row.get('vendor_match', True):
                    vendor_mismatches += 1
                
                variance_pct = row.get('total_amount_variance_percentage', 0)
                if variance_pct and abs(variance_pct) > 15:
                    high_variances += 1
            
            risks = []
            if gst_mismatches > 0:
                risks.append(f"GST number mismatches ({gst_mismatches} records) - Tax compliance risk")
            if vendor_mismatches > 0:
                risks.append(f"Vendor name mismatches ({vendor_mismatches} records) - Audit trail risk")
            if high_variances > 0:
                risks.append(f"High variances ({high_variances} records) - Financial reporting risk")
            
            return "; ".join(risks) if risks else None
            
        except Exception:
            return None
    
    def _calculate_financial_impact(self, sql_result: List[Dict]) -> str:
        """Calculate total financial impact"""
        try:
            total_impact = 0
            variance_fields = ['total_variance', 'total_amount_variance', 'subtotal_variance']
            
            for row in sql_result:
                for field in variance_fields:
                    variance = row.get(field, 0)
                    if variance:
                        total_impact += abs(variance)
                        break  # Use first available variance field
            
            if total_impact > 0:
                return f"₹{total_impact:,.2f} total variance across {len(sql_result)} records"
            
            return None
            
        except Exception:
            return None
    
    def _generate_next_steps(self, sql_result: List[Dict], question: str) -> str:
        """Generate specific next steps based on the data"""
        try:
            steps = []
            
            # Count different types of issues
            exceptions = sum(1 for row in sql_result if row.get('is_exception'))
            reviews_needed = sum(1 for row in sql_result if row.get('requires_review'))
            vendor_issues = sum(1 for row in sql_result if not row.get('vendor_match', True))
            gst_issues = sum(1 for row in sql_result if not row.get('gst_match', True))
            
            step_counter = 1
            
            if exceptions > 0:
                steps.append(f"{step_counter}. Resolve {exceptions} critical exceptions immediately")
                step_counter += 1
            
            if reviews_needed > 0:
                steps.append(f"{step_counter}. Review {reviews_needed} items requiring manual validation")
                step_counter += 1
            
            if vendor_issues > 0:
                steps.append(f"{step_counter}. Contact vendors to resolve {vendor_issues} name/data mismatches")
                step_counter += 1
            
            if gst_issues > 0:
                steps.append(f"{step_counter}. Verify GST numbers for {gst_issues} records (compliance critical)")
                step_counter += 1
            
            # Add general steps
            steps.append(f"{step_counter}. Update tolerance settings if variances are acceptable")
            steps.append(f"{step_counter + 1}. Document resolution actions for audit trail")
            
            return "\n".join(steps) if steps else "Continue monitoring reconciliation process"
            
        except Exception:
            return "Review identified records and take appropriate action"
    
    def _determine_analysis_type(self, question: str) -> str:
        """Determine the type of analysis being performed"""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['mismatch', 'not match', 'differ', 'discrepancy', 'why']):
            return 'mismatch_analysis'
        elif any(word in question_lower for word in ['variance', 'difference', 'amount diff']):
            return 'variance_analysis'
        elif any(word in question_lower for word in ['exception', 'error', 'issue', 'problem', 'critical']):
            return 'exception_analysis'
        elif any(word in question_lower for word in ['workflow', 'approval', 'pending', 'process']):
            return 'workflow_analysis'
        else:
            return 'general_inquiry'
    
    def _assess_business_impact(self, sql_result: List[Dict], question: str) -> str:
        """Assess the business impact of the results"""
        if not sql_result:
            return 'no_impact'
        
        try:
            total_variance = 0
            critical_count = 0
            
            for row in sql_result:
                # Sum variances
                variance = abs(row.get('total_variance', 0) or row.get('total_amount_variance', 0))
                total_variance += variance
                
                # Count critical items
                if row.get('is_exception') or variance > 50000:
                    critical_count += 1
            
            if critical_count > 0 or total_variance > 500000:
                return 'high_impact'
            elif total_variance > 50000:
                return 'medium_impact'
            else:
                return 'low_impact'
                
        except Exception:
            return 'unknown_impact'
    
    def _extract_actionable_insights(self, analysis: str) -> List[str]:
        """Extract actionable insights from the analysis"""
        try:
            insights = []
            
            # Look for action items in the analysis
            lines = analysis.split('\n')
            for line in lines:
                line = line.strip()
                if any(indicator in line.lower() for indicator in ['action', 'recommend', 'should', 'must', 'need to']):
                    if len(line) > 10 and len(line) < 200:  # Reasonable length
                        insights.append(line.replace('**', '').replace('*', '').strip())
            
            return insights[:5]  # Limit to top 5 insights
            
        except Exception:
            return ['Review reconciliation results and take appropriate action']
    
    def _get_conversation_context(self, session_id: str) -> str:
        """Get recent conversation context for better continuity"""
        try:
            recent_conversations = ChatConversation.objects.filter(
                session_id=session_id
            ).order_by('-created_at')[:3]
            
            if not recent_conversations:
                return ""
            
            context_parts = []
            for conv in reversed(list(recent_conversations)):
                context_parts.append(f"Q: {conv.user_question}")
                if conv.natural_response:
                    # Extract key insights from previous responses
                    response_summary = conv.natural_response[:200] + "..." if len(conv.natural_response) > 200 else conv.natural_response
                    context_parts.append(f"A: {response_summary}")
            
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
                'error': True,
                'intelligence_level': 'error_response'
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
                    'error': bool(conv.error_message),
                    'intelligence_level': 'advanced_analysis' if not conv.error_message else 'error'
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