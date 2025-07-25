import os
import decimal
import json
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import logging
from django.conf import settings
from .prompts import SQLGenerationPrompts, AnalysisGenerationPrompts, PromptLoader

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal objects"""
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

class LLMConfig:
    """Central configuration for all LLM operations with modular prompts"""
    
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
        
        # Initialize prompt handlers
        self.sql_prompts = SQLGenerationPrompts()
        self.analysis_prompts = AnalysisGenerationPrompts()
        self.prompt_loader = PromptLoader()
        
        logger.info("LLM configuration initialized successfully with modular prompts")
    
    def get_embedding(self, text: str) -> list:
        """Generate embedding for given text"""
        try:
            embedding = self.embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def _serialize_data(self, data):
        """Convert data to JSON-serializable format"""
        return json.loads(json.dumps(data, cls=DecimalEncoder, default=str))
    
    def _determine_analysis_type(self, question: str) -> str:
        """Determine the type of analysis based on the question"""
        question_lower = question.lower()
        
        # Define keywords for each analysis type
        analysis_keywords = {
        'mismatch_analysis': [
            'mismatch', 'not match', 'differ', 'discrepancy', 'why not matching',
            'description does not match', 'vendor mismatch', 'hsn mismatch'
        ],
        'variance_analysis': [
            'variance', 'difference', 'amount diff', 'price diff', 'quantity diff',
            'above', 'below', 'greater than', 'less than', 'variances'
        ],
        'exception_analysis': [
            'exception', 'error', 'issue', 'problem', 'critical', 'urgent',
            'review', 'manual review', 'requires review'
        ],
        'workflow_analysis': [
            'workflow', 'approval', 'pending', 'process', 'efficiency', 'bottleneck',
            'approved', 'rejected', 'status'
        ],
        'trend_analysis': [
            'trend', 'over time', 'monthly', 'weekly', 'pattern', 'growth',
            'history', 'timeline'
        ]
    }
        
        # Score each analysis type based on keyword matches
        scores = {}
        for analysis_type, keywords in analysis_keywords.items():
            score = sum(2 if keyword in question_lower else 0 for keyword in keywords)
            if score > 0:
                scores[analysis_type] = score
        
        # Return the analysis type with highest score, default to general
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return 'general'
    
    def generate_sql(self, question: str, table_schemas: list, conversation_context: str = None) -> str:
        """Generate SQL query using appropriate prompt based on question type"""
        try:
            # Determine analysis type
            analysis_type = self._determine_analysis_type(question)
            logger.info(f"Determined analysis type: {analysis_type}")
            
            # Prepare template variables
            schema_info = "\n\n".join([
                f"Table: {schema['table_name']}\n"
                f"Description: {schema['schema_description']}\n"
                f"Columns: {schema['columns_info']}\n"
                f"Sample Questions: {schema['sample_questions']}"
                for schema in table_schemas
            ])
            
            context_section = f"\n\nConversation Context:\n{conversation_context}" if conversation_context else ""
            table_names = [schema['table_name'] for schema in table_schemas]
            
            # Get appropriate prompt for analysis type
            prompt_template = self.sql_prompts.get_prompt_for_analysis_type(analysis_type)
            
            # Prepare template variables
            template_vars = {
                'question': question,
                'schema_info': schema_info,
                'context_section': context_section,
                'table_names': ', '.join(table_names)
            }
            
            # Load and format prompt with fallback
            try:
                prompt = self.prompt_loader.load_template(prompt_template, **template_vars)
            except Exception as e:
                logger.warning(f"Error with specific prompt, using simple fallback: {e}")
                prompt = self.prompt_loader.load_template(
                    self.sql_prompts.SIMPLE_SQL_PROMPT,
                    question=question,
                    table_names=', '.join(table_names)
                )
            
            # Generate SQL using Gemini
            response = self.gemini_model.generate_content(prompt)
            sql_query = response.text.strip()
            
            # Clean up the SQL query
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
            
            logger.info(f"Generated SQL for {analysis_type}: {sql_query[:100]}...")
            return sql_query
            
        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            raise
    
    def generate_intelligent_analysis(self, question: str, sql_result: list, sql_query: str) -> str:
        """Generate intelligent business analysis with root cause insights"""
        try:
            if not sql_result:
                return "No data found for analysis. This could indicate perfect reconciliation or overly restrictive criteria."
            
            # Determine analysis type
            analysis_type = self._determine_analysis_type(question)
            logger.info(f"Generating {analysis_type} analysis")
            
            # Prepare data summary for analysis
            result_count = len(sql_result)
            sample_data = self._serialize_data(sql_result[:3] if len(sql_result) > 3 else sql_result)
            
            # Generate comprehensive data summary
            data_summary = self._generate_data_summary(sql_result, analysis_type)
            
            # Get appropriate analysis prompt
            analysis_prompt = self.analysis_prompts.get_analysis_prompt_for_type(analysis_type)
            
            # Prepare template variables
            template_vars = {
                'question': question,
                'sql_query': sql_query,
                'result_count': result_count,
                'sample_data': sample_data,
                'data_summary': data_summary
            }
            
            # Load and format analysis prompt with fallback
            try:
                prompt = self.prompt_loader.load_template(analysis_prompt, **template_vars)
            except Exception as e:
                logger.warning(f"Error with specific analysis prompt, using simple fallback: {e}")
                prompt = self.prompt_loader.load_template(
                    self.analysis_prompts.SIMPLE_ANALYSIS_RESPONSE,
                    question=question,
                    result_count=result_count,
                    sample_data=sample_data
                )
            
            # Generate analysis using Gemini
            response = self.gemini_model.generate_content(prompt)
            analysis_result = response.text.strip()
            
            logger.info(f"Generated {analysis_type} analysis successfully")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error generating intelligent analysis: {str(e)}")
            return self._create_fallback_analysis(question, sql_result)
    
    def _generate_data_summary(self, sql_result: list, analysis_type: str) -> str:
        """Generate a comprehensive summary of the data for analysis"""
        try:
            if not sql_result:
                return "No data available"
            
            summary_parts = []
            
            # Basic statistics
            summary_parts.append(f"Total records: {len(sql_result)}")
            
            # Type-specific summaries
            if analysis_type == 'mismatch_analysis':
                summary_parts.extend(self._summarize_mismatch_data(sql_result))
            elif analysis_type == 'variance_analysis':
                summary_parts.extend(self._summarize_variance_data(sql_result))
            elif analysis_type == 'exception_analysis':
                summary_parts.extend(self._summarize_exception_data(sql_result))
            elif analysis_type == 'workflow_analysis':
                summary_parts.extend(self._summarize_workflow_data(sql_result))
            
            return "; ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating data summary: {e}")
            return f"Data summary unavailable: {len(sql_result)} records found"
    
    def _summarize_mismatch_data(self, sql_result: list) -> list:
        """Summarize mismatch-specific data patterns"""
        summary = []
        
        try:
            # Match status distribution
            if 'match_status' in sql_result[0]:
                statuses = {}
                for row in sql_result:
                    status = row.get('match_status', 'unknown')
                    statuses[status] = statuses.get(status, 0) + 1
                
                most_common = max(statuses.items(), key=lambda x: x[1])
                summary.append(f"Most common mismatch: {most_common[0]} ({most_common[1]} records)")
            
            # Vendor match issues
            if 'vendor_match' in sql_result[0]:
                vendor_mismatches = sum(1 for row in sql_result if not row.get('vendor_match', True))
                if vendor_mismatches > 0:
                    summary.append(f"Vendor mismatches: {vendor_mismatches} records")
            
            # GST match issues
            if 'gst_match' in sql_result[0]:
                gst_mismatches = sum(1 for row in sql_result if not row.get('gst_match', True))
                if gst_mismatches > 0:
                    summary.append(f"GST mismatches: {gst_mismatches} records")
            
        except Exception as e:
            logger.error(f"Error summarizing mismatch data: {e}")
        
        return summary
    
    def _summarize_variance_data(self, sql_result: list) -> list:
        """Summarize variance-specific data patterns"""
        summary = []
        
        try:
            # Total variance analysis
            variance_fields = ['total_variance', 'total_amount_variance', 'subtotal_variance']
            for field in variance_fields:
                if field in sql_result[0]:
                    variances = [row.get(field, 0) for row in sql_result if row.get(field) is not None]
                    if variances:
                        total_var = sum(abs(v) for v in variances)
                        avg_var = total_var / len(variances)
                        summary.append(f"Total {field.replace('_', ' ')}: ₹{total_var:,.2f} (Avg: ₹{avg_var:,.2f})")
                        break
            
            # High variance count
            high_variance_count = 0
            for row in sql_result:
                variance_pct = row.get('total_amount_variance_percentage', 0)
                if variance_pct and abs(variance_pct) > 10:
                    high_variance_count += 1
            
            if high_variance_count > 0:
                summary.append(f"High variances (>10%): {high_variance_count} records")
            
        except Exception as e:
            logger.error(f"Error summarizing variance data: {e}")
        
        return summary
    
    def _summarize_exception_data(self, sql_result: list) -> list:
        """Summarize exception-specific data patterns"""
        summary = []
        
        try:
            # Exception counts
            if 'is_exception' in sql_result[0]:
                exception_count = sum(1 for row in sql_result if row.get('is_exception'))
                summary.append(f"Critical exceptions: {exception_count} records")
            
            # Review requirements
            if 'requires_review' in sql_result[0]:
                review_count = sum(1 for row in sql_result if row.get('requires_review'))
                summary.append(f"Require manual review: {review_count} records")
            
            # Approval status distribution
            if 'approval_status' in sql_result[0]:
                statuses = {}
                for row in sql_result:
                    status = row.get('approval_status', 'unknown')
                    statuses[status] = statuses.get(status, 0) + 1
                
                pending_count = statuses.get('pending', 0)
                if pending_count > 0:
                    summary.append(f"Pending approvals: {pending_count} records")
            
        except Exception as e:
            logger.error(f"Error summarizing exception data: {e}")
        
        return summary
    
    def _summarize_workflow_data(self, sql_result: list) -> list:
        """Summarize workflow-specific data patterns"""
        summary = []
        
        try:
            # Auto vs manual matching
            if 'is_auto_matched' in sql_result[0]:
                auto_count = sum(1 for row in sql_result if row.get('is_auto_matched'))
                auto_rate = (auto_count / len(sql_result)) * 100
                summary.append(f"Automation rate: {auto_rate:.1f}% ({auto_count}/{len(sql_result)})")
            
            # Processing times
            if 'processing_time_ms' in sql_result[0]:
                times = [row.get('processing_time_ms', 0) for row in sql_result if row.get('processing_time_ms')]
                if times:
                    avg_time = sum(times) / len(times)
                    summary.append(f"Avg processing time: {avg_time:.0f}ms")
            
        except Exception as e:
            logger.error(f"Error summarizing workflow data: {e}")
        
        return summary
    
    def _create_fallback_analysis(self, question: str, sql_result: list) -> str:
        """Create a simple fallback analysis when advanced analysis fails"""
        try:
            result_count = len(sql_result)
            
            if result_count == 0:
                return """
**No Data Found**

I couldn't find any records matching your query. This could mean:
- All reconciliations are perfect matches
- The search criteria were too specific
- There might be a data availability issue

**Recommended Actions:**
- Try broadening your search criteria
- Check if the data exists for the specified time period
- Verify table names and field references
"""
            
            # Basic analysis
            sample = sql_result[0] if sql_result else {}
            
            analysis = f"""
**Query Results Summary**

Found {result_count} records for your question: "{question}"

**Key Findings:**
"""
            
            # Try to identify key fields and provide basic insights
            key_fields = ['match_status', 'total_variance', 'vendor_match', 'requires_review', 'is_exception']
            insights = []
            
            for field in key_fields:
                if field in sample:
                    if field == 'match_status':
                        statuses = {}
                        for row in sql_result:
                            status = row.get(field, 'unknown')
                            statuses[status] = statuses.get(status, 0) + 1
                        insights.append(f"• Match Status Distribution: {dict(list(statuses.items())[:3])}")
                    
                    elif field == 'total_variance':
                        variances = [abs(row.get(field, 0)) for row in sql_result if row.get(field) is not None]
                        if variances:
                            total_var = sum(variances)
                            insights.append(f"• Total Variance Impact: ₹{total_var:,.2f}")
                    
                    elif field in ['vendor_match', 'requires_review', 'is_exception']:
                        count = sum(1 for row in sql_result if row.get(field))
                        insights.append(f"• {field.replace('_', ' ').title()}: {count} records")
            
            if insights:
                analysis += "\n" + "\n".join(insights)
            
            analysis += f"""

**Recommended Next Steps:**
- Review the {result_count} records identified
- Focus on high-impact items first
- Consider process improvements for recurring issues
- Contact support if you need more detailed analysis
"""
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error creating fallback analysis: {e}")
            return f"I found {len(sql_result)} records for your question but couldn't provide detailed analysis. Please contact support for assistance."


# Global LLM instance
llm_config = None

def get_llm_config():
    """Get or create global LLM configuration instance"""
    global llm_config
    if llm_config is None:
        llm_config = LLMConfig()
    return llm_config