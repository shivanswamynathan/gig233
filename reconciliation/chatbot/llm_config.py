import os
import decimal
import datetime
import re
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
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, datetime.time):
            return obj.isoformat()
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
        """Improved analysis type detection based on the question"""
        question_lower = question.lower()
        
        # More specific keyword matching with scoring
        analysis_keywords = {
            'mismatch_analysis': [
                ('mismatch', 3), ('not match', 3), ('differ', 2), ('discrepancy', 3), 
                ('why not matching', 4), ('description does not match', 4), 
                ('vendor mismatch', 4), ('hsn mismatch', 4), ('partial match', 3),
                ('doesn\'t match', 3), ('different', 2)
            ],
            'variance_analysis': [
                ('variance', 3), ('difference', 2), ('amount diff', 4), ('price diff', 4), 
                ('quantity diff', 4), ('above', 2), ('below', 2), ('greater than', 3), 
                ('less than', 3), ('variances', 3), ('threshold', 2), ('exceed', 3)
            ],
            'exception_analysis': [
                ('exception', 4), ('error', 2), ('issue', 2), ('problem', 2), 
                ('critical', 4), ('urgent', 3), ('review', 2), ('manual review', 4), 
                ('requires review', 4), ('flag', 2)
            ],
            'workflow_analysis': [
                ('workflow', 4), ('approval', 3), ('pending', 3), ('process', 2), 
                ('efficiency', 3), ('bottleneck', 3), ('approved', 3), ('rejected', 3), 
                ('status', 2), ('escalated', 3)
            ],
            'summary_analysis': [ 
                ('count', 4), ('how many', 4), ('total', 3), ('sum', 3), 
                ('number of', 4), ('show me all', 3), ('list all', 3)
            ],
            'trend_analysis': [
                ('trend', 4), ('over time', 4), ('monthly', 3), ('weekly', 3), 
                ('pattern', 3), ('growth', 3), ('history', 2), ('timeline', 3),
                ('daily', 3), ('period', 2)
            ]
        }
        
        # Calculate weighted scores for each analysis type
        scores = {}
        for analysis_type, keywords in analysis_keywords.items():
            score = 0
            for keyword, weight in keywords:
                if keyword in question_lower:
                    score += weight
            if score > 0:
                scores[analysis_type] = score
        
        # Return the analysis type with highest score
        if scores:
            best_type = max(scores.items(), key=lambda x: x[1])[0]
            logger.info(f"Determined analysis type: {best_type} (score: {scores[best_type]})")
            return best_type
        
        # Default to mismatch_analysis if no clear type found
        return 'general'
    
    def _extract_po_number_variants(self, question: str) -> list:
        """Extract PO number and create search variants"""
        
        
        # Find PO number patterns
        po_patterns = [
            r'PO[-_]?([A-Z0-9_-]+)',
            r'CFI\d+[-_]\d+',
            r'[A-Z]{3}_[A-Z]{3}_[A-Z]{3}CFI\d+[-_]\d+'
        ]
        
        variants = []
        for pattern in po_patterns:
            matches = re.findall(pattern, question, re.IGNORECASE)
            for match in matches:
                # Create different search variants
                variants.append(match)
                if '-' in match:
                    variants.append(match.replace('-', '_'))
                if '_' in match:
                    variants.append(match.replace('_', '-'))
                
                # Extract key parts (like CFI25-07298)
                cfi_match = re.search(r'(CFI\d+[-_]\d+)', match)
                if cfi_match:
                    variants.append(cfi_match.group(1))
        
        return list(set(variants))
    def generate_sql(self, question: str, table_schemas: list, conversation_context: str = None) -> str:
        """Generate SQL query using simplified prompts with dynamic filtering"""
        try:
            # Determine analysis type with improved detection
            analysis_type = self._determine_analysis_type(question)    

            # Prepare simplified schema info
            schema_info = ""
            table_names = []
            for schema in table_schemas:
                table_names.append(schema['table_name'])
                # Only include essential column info
                essential_columns = self._get_essential_columns(schema['columns_info'])
                schema_info += f"Table: {schema['table_name']}\n"
                schema_info += f"Key columns: {essential_columns}\n\n"

            logger.info(f"=== SQL GENERATION DEBUG ===")
            logger.info(f"Question: {question}")
            logger.info(f"Analysis type: {analysis_type}")
            logger.info(f"Available tables: {table_names}")
            
            context_section = f"\n\nConversation Context:\n{conversation_context}" if conversation_context else ""
            
            # Get appropriate prompt for analysis type
            prompt_template = self.sql_prompts.get_prompt_for_analysis_type(analysis_type)
            
            # Prepare template variables
            template_vars = {
                'question': question,
                'schema_info': schema_info.strip(),
                'context_section': context_section,
                'table_names': ', '.join(table_names)
            }
            
            # Load and format prompt with better fallback
            try:
                prompt = self.prompt_loader.load_template(prompt_template, **template_vars)
                logger.info(f"Final prompt (first 300 chars): {prompt[:300]}...")
            except Exception as e:
                logger.warning(f"Error with specific prompt, using simple fallback: {e}")
                # Use the simplest prompt possible
                simple_prompt = f"""Generate a PostgreSQL SELECT query for: {question}
                
    Tables available: {', '.join(table_names)}

    Key rules:
    1. Only SELECT statements
    2. Add WHERE clauses based on user intent
    3. If user mentions mismatch/variance/issues, filter for those
    4. If user mentions specific numbers/IDs, use ILIKE with wildcards

    SQL Query:"""
                prompt = simple_prompt
            
            # Generate SQL using Gemini with retry logic
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(prompt)
                    raw_sql = response.text.strip()
                    logger.info(f" Raw SQL received from Gemini:")
                    logger.info(f"RAW SQL: {raw_sql}")
                    
                    # Clean up the SQL query
                    sql_query = self._clean_sql_query(raw_sql)
                    logger.info(f" Cleaned SQL: {sql_query}")
                    
                    # Validate the generated SQL
                    if self._validate_sql_query(sql_query, table_names):
                        logger.info(f"Generated valid SQL for {analysis_type}: {sql_query[:100]}...")
                        return sql_query
                    else:
                        logger.warning(f"Generated invalid SQL on attempt {attempt + 1}")
                        if attempt == max_retries - 1:
                            # Last attempt - generate a safe fallback
                            return self._generate_fallback_sql(question, table_names)
                        
                except Exception as e:
                    logger.error(f"Error generating SQL on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        return self._generate_fallback_sql(question, table_names)
            
        except Exception as e:
            logger.error(f"Error in generate_sql: {str(e)}")
            # Return a safe fallback query
            return self._generate_fallback_sql(question, table_schemas[0]['table_name'] if table_schemas else 'invoice_grn_reconciliation')
        
    
    def _get_essential_columns(self, columns_info: dict) -> str:
        """Extract table-appropriate essential columns"""
        # Check which table we're dealing with based on unique columns
        if 'gst_match' in columns_info:  # invoice_grn_reconciliation
            essential_fields = [
                'match_status', 'gst_match', 'vendor_match', 'total_variance',
                'approval_status', 'requires_review', 'is_exception',
                'po_number', 'invoice_number', 'grn_number'
            ]
        else:  # invoice_item_reconciliation  
            essential_fields = [
                'match_status', 'hsn_match_score', 'description_match_score',
                'total_amount_variance', 'quantity_variance', 'requires_review',
                'is_exception', 'po_number', 'invoice_number'
            ]
        
        found_fields = [field for field in essential_fields if field in columns_info]
        return ', '.join(found_fields[:10])

    def _clean_sql_query(self, sql_query: str) -> str:
        """Clean and standardize the SQL query"""
        logger.info(f"=== SQL CLEANING ===")
        logger.info(f"Original SQL: {sql_query}")
        
        # Remove markdown and extra whitespace
        cleaned = sql_query.replace('```sql', '').replace('```', '').strip()
        
        # Join multiline queries into single line
        cleaned = ' '.join(line.strip() for line in cleaned.split('\n') if line.strip())
        
        # Ensure semicolon
        if not cleaned.endswith(';'):
            cleaned += ';'
        
        logger.info(f"Final cleaned SQL: {cleaned}")
        return cleaned
        

    def _validate_sql_query(self, sql_query: str, table_names: list) -> bool:
        """Basic validation of generated SQL"""
        try:
            sql_upper = sql_query.upper()

            logger.info(f"=== SQL VALIDATION ===")
            logger.info(f"Validating SQL: {sql_query}")
            
            # Must start with SELECT
            if not sql_upper.strip().startswith('SELECT'):
                logger.warning(f" Validation failed: Query doesn't start with SELECT")
                return False
            
            else:
                logger.info(f" Query starts with SELECT")
            
            # Must contain at least one of our tables
            # Must contain at least one of our tables
            found_tables = [table for table in table_names if table in sql_query.lower()]
            if not found_tables:
                logger.warning(f" No valid tables found. Expected: {table_names}")
                return False
            else:
                logger.info(f" Found valid tables: {found_tables}")
            
            # Must not contain dangerous keywords
            dangerous = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE']
            if any(keyword in sql_upper for keyword in dangerous):
                return False
            
            return True
            
        except Exception:
            return False

    def _generate_fallback_sql(self, question: str, table_names) -> str:
        """Generate a safe fallback SQL query when all else fails"""
        question_lower = question.lower()
        
        # Choose primary table
        if isinstance(table_names, list):
            table = table_names[0] if table_names else 'invoice_grn_reconciliation'
        else:
            table = table_names
        
        # Basic WHERE clause based on question keywords
        where_clauses = []
        
        if any(word in question_lower for word in ['mismatch', 'not match', 'differ']):
            where_clauses.append("match_status != 'perfect_match'")
        
        if any(word in question_lower for word in ['review', 'manual']):
            where_clauses.append("requires_review = true")
        
        if any(word in question_lower for word in ['exception', 'critical']):
            where_clauses.append("is_exception = true")
        
        if any(word in question_lower for word in ['variance', 'difference']):
            where_clauses.append("total_amount_variance != 0")
        
        # Extract potential PO/invoice numbers
        import re
        po_pattern = r'(?:po-?|cfi\d+[-_])\w*'
        po_matches = re.findall(po_pattern, question_lower)
        if po_matches:
            for po in po_matches[:1]:  # Use first match only
                where_clauses.append(f"po_number ILIKE '%{po}%'")
        
        # Build the query
        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        fallback_sql = f"""
        SELECT *
        FROM {table}
        WHERE {where_clause}
        ORDER BY updated_at DESC;
        """
        
        logger.info(f"Generated fallback SQL: {fallback_sql.strip()}")
        return fallback_sql.strip()
    
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
            sample_data = self._serialize_data(sql_result)
            
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