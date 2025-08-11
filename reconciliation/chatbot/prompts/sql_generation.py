class SQLGenerationPrompts:
    """Simplified and dynamic SQL generation prompts for the reconciliation chatbot"""
    
    BASE_SQL_PROMPT = """
You are an expert SQL generator for invoice reconciliation. Generate ONLY SELECT queries.

AVAILABLE TABLES:
{schema_info}

USER QUESTION: {question}{context_section}

CRITICAL RULES:
1. ALWAYS add WHERE clauses based on user intent
2. Use ONLY SELECT statements
3. Use proper PostgreSQL syntax

DYNAMIC FILTERING - ANALYZE USER QUESTION AND ADD APPROPRIATE WHERE CONDITIONS:

F user mentions specific PO numbers (like "PO-MAA_OVN_CKSCFI25-07298"):
→ Use FLEXIBLE matching: WHERE po_number ILIKE '%CFI25-07298%' OR po_number ILIKE '%MAA_OVN_CKS%'
→ Extract the unique parts and use partial matching
→ ALWAYS check invoice_grn_reconciliation table FIRST for PO-specific questions

IF user mentions "mismatch" OR "doesn't match" OR "not matching":
→ WHERE match_status != 'perfect_match'

IF user mentions "description" + mismatch words:
→ WHERE description_match_score < 1.0

IF user mentions "amount" + ("variance"|"difference"|"mismatch"):
→ WHERE total_amount_variance != 0 OR ABS(total_amount_variance) > 0

IF user mentions "quantity" + variance words:
→ WHERE quantity_variance != 0

IF user mentions "HSN" + mismatch words:
→ WHERE hsn_match_score < 1.0

IF user mentions "vendor" + mismatch words:
→ WHERE vendor_match = false

IF user mentions "review" OR "manual":
→ WHERE requires_review = true

IF user mentions "exception" OR "critical":
→ WHERE is_exception = true

IF user mentions specific PO/invoice numbers (like "CFI25-06432"):
→ WHERE po_number ILIKE '%CFI25-06432%' OR invoice_number ILIKE '%CFI25-06432%'

IF user mentions amount thresholds (like "above 1000"):
→ WHERE ABS(total_amount_variance) > 1000

EXAMPLES:
Q: "Show items where description does not match"
A: SELECT * FROM invoice_item_reconciliation WHERE description_match_score < 1.0;

Q: "why this PO-MAA_OVN_CKSCFI25-07298 is partial match"
A: SELECT po_number, invoice_number, match_status, vendor_match, gst_match, date_valid, 
   total_variance, subtotal_variance, reconciliation_notes 
   FROM invoice_grn_reconciliation 
   WHERE po_number ILIKE '%CFI25-07298%' OR po_number ILIKE '%MAA_OVN_CKS%';

Q: "List variances above 500"
A: SELECT * FROM invoice_item_reconciliation WHERE ABS(total_amount_variance) > 500;

Q: "Why is PO-CFI25-06432 showing partial match?"
A: SELECT * FROM invoice_grn_reconciliation WHERE po_number ILIKE '%CFI25-06432%';

Generate ONLY the SQL query - no explanations:
"""
    
    MISMATCH_ANALYSIS_PROMPT = """
Generate SQL for MISMATCH ANALYSIS. Focus on finding reconciliation problems.

TABLES: {schema_info}
QUESTION: {question}{context_section}

MISMATCH DETECTION RULES:
- "description mismatch" → WHERE description_match_score < 1.0
- "amount mismatch" → WHERE total_amount_variance != 0
- "vendor mismatch" → WHERE vendor_match = false
- "HSN mismatch" → WHERE hsn_match_score < 1.0
- "quantity mismatch" → WHERE quantity_variance != 0
- "partial match" → WHERE match_status = 'partial_match'
- "no match" → WHERE match_status = 'no_match'

ALWAYS include relevant variance fields in SELECT:
- total_amount_variance, quantity_variance, hsn_match_score, description_match_score
- match_status, requires_review, is_exception

Generate SQL query only:
"""
    
    VARIANCE_ANALYSIS_PROMPT = """
Generate SQL for VARIANCE ANALYSIS. Focus on amount/quantity differences.

TABLES: {schema_info}
QUESTION: {question}{context_section}

VARIANCE DETECTION RULES:
- Look for ABS(total_amount_variance) > threshold
- Include percentage calculations
- Filter out zero variances unless specifically asked

ALWAYS include in SELECT:
- total_amount_variance, total_amount_variance_percentage
- quantity_variance, quantity_variance_percentage
- unit_rate_variance, subtotal_variance

Generate SQL query only:
"""
    
    EXCEPTION_ANALYSIS_PROMPT = """
Generate SQL for EXCEPTION ANALYSIS. Focus on critical issues.

TABLES: {schema_info}
QUESTION: {question}{context_section}

EXCEPTION DETECTION RULES:
- WHERE is_exception = true
- WHERE requires_review = true
- WHERE match_status IN ('no_match', 'multiple_grn')

ALWAYS include in SELECT:
- is_exception, requires_review, match_status
- total_amount_variance, approval_status

Generate SQL query only:
"""
    
    WORKFLOW_ANALYSIS_PROMPT = """
Generate SQL for WORKFLOW ANALYSIS. Focus on approval process.

TABLES: {schema_info}
QUESTION: {question}{context_section}

WORKFLOW DETECTION RULES:
- "pending" → WHERE approval_status = 'pending'
- "approved" → WHERE approval_status = 'approved'
- "rejected" → WHERE approval_status = 'rejected'
- "workflow" → Include approval_status, approved_at, requires_review

ALWAYS include in SELECT:
- approval_status, approved_at, requires_review
- is_auto_matched, reconciled_at

Generate SQL query only:
"""
    
    TREND_ANALYSIS_PROMPT = """
Generate SQL for TREND ANALYSIS. Focus on patterns over time.

TABLES: {schema_info}
QUESTION: {question}{context_section}

TREND DETECTION RULES:
- Include DATE functions for time grouping
- Use aggregation functions (COUNT, SUM, AVG)
- GROUP BY time periods or categories

ALWAYS include in SELECT:
- Date fields (reconciled_at, updated_at)
- Aggregation functions
- GROUP BY and ORDER BY clauses

Generate SQL query only:
"""
    
    # Simplified fallback prompt
    SIMPLE_SQL_PROMPT = """
Generate a PostgreSQL SELECT query for reconciliation data.

TABLES: {table_names}
QUESTION: {question}

Rules:
1. Use only SELECT statements
2. Add appropriate WHERE clauses based on question intent
3. Use proper PostgreSQL syntax

QUICK FILTERS:
- mismatch words → WHERE match_status != 'perfect_match'
- specific PO/invoice → WHERE po_number ILIKE '%number%'
- variance words → WHERE total_amount_variance != 0
- review words → WHERE requires_review = true

SQL Query:
"""
    
    @classmethod
    def get_prompt_for_analysis_type(cls, analysis_type: str) -> str:
        """Get specific prompt based on analysis type"""
        prompt_map = {
            'mismatch_analysis': cls.MISMATCH_ANALYSIS_PROMPT,
            'variance_analysis': cls.VARIANCE_ANALYSIS_PROMPT,
            'exception_analysis': cls.EXCEPTION_ANALYSIS_PROMPT,
            'workflow_analysis': cls.WORKFLOW_ANALYSIS_PROMPT,
            'trend_analysis': cls.TREND_ANALYSIS_PROMPT,
            'general': cls.BASE_SQL_PROMPT
        }
        return prompt_map.get(analysis_type, cls.BASE_SQL_PROMPT)