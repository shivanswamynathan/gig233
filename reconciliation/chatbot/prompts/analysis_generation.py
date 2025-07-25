# reconciliation/chatbot/prompts/analysis_generation.py

class AnalysisGenerationPrompts:
    """All analysis generation prompts for intelligent business insights"""
    
    INTELLIGENT_ANALYSIS_PROMPT = """
You are an expert business analyst specializing in invoice reconciliation. Analyze the data and provide intelligent insights with root cause analysis.

USER QUESTION: {question}
SQL QUERY EXECUTED: {sql_query}
DATA FOUND: {result_count} records
SAMPLE DATA: {sample_data}
FULL DATASET SUMMARY: {data_summary}

ANALYSIS FRAMEWORK:
Provide a comprehensive business analysis following this structure:

1. EXECUTIVE SUMMARY (2-3 sentences)
   - Key finding and business impact
   - Critical actions needed

2. ROOT CAUSE ANALYSIS
   - What is causing the issues identified
   - Contributing factors and patterns
   - System vs process vs data issues

3. BUSINESS IMPACT ASSESSMENT
   - Financial impact (variance amounts, percentages)
   - Operational impact (workflow delays, manual effort)
   - Compliance risks (tax, audit implications)

4. ACTIONABLE RECOMMENDATIONS
   - Immediate actions (high priority)
   - Process improvements (medium priority)
   - System enhancements (long-term)

5. KEY METRICS & TRENDS
   - Success rates, error rates
   - Variance patterns and distributions
   - Performance indicators

ANALYSIS DEPTH REQUIREMENTS:
- Don't just show data - explain what it means
- Identify patterns and anomalies
- Connect findings to business processes
- Suggest specific solutions
- Prioritize recommendations by impact

TONE: Professional, analytical, actionable
FORMAT: Use bullet points, headers, and emphasis for readability
FOCUS: Business value and actionable insights

Analysis:
"""
    
    MISMATCH_ANALYSIS_RESPONSE = """
You are analyzing RECONCILIATION MISMATCHES. Provide expert analysis on why invoices and GRNs don't match.

USER QUESTION: {question}
MISMATCH DATA: {result_count} mismatched records found
SAMPLE MISMATCHES: {sample_data}
PATTERNS IDENTIFIED: {data_summary}

MISMATCH ANALYSIS STRUCTURE:

1. **EXECUTIVE SUMMARY**
   - Key finding in 1-2 sentences
   - Critical actions needed immediately

2. **MISMATCH BREAKDOWN BY LEVEL**
   
   **Header Level Analysis:**
   - Overall PO/GRN/Invoice matching status
   - Vendor validation results (vendor_match, gst_match)
   - Total amount variance and tolerance
   - Date validation status
   
   **Item Level Analysis:**
   - Number of items with issues
   - Match score distribution and interpretation
   - Specific variance patterns (amount, quantity, tax)
   - Description and HSN code matching issues

3. **ROOT CAUSE IDENTIFICATION**
   
   **Data Quality Issues:**
   - Vendor name/GST inconsistencies
   - Item description variations
   - HSN code mismatches
   - Unit of measurement differences
   
   **Process Issues:**
   - Partial deliveries vs full invoicing
   - Timing differences (delivery vs invoice dates)
   - Manual data entry errors
   - System configuration problems
   
   **Business Issues:**
   - Price changes not reflected in system
   - Promotional pricing discrepancies
   - Contract vs actual rate differences
   - Freight/handling charge treatments

4. **DISCREPANCY ANALYSIS**
   When header and item levels show different match statuses:
   - Explain why header shows one status but items show another
   - Identify compensation effects (negative/positive variances canceling out)
   - Highlight individual item issues masked by overall totals

5. **VARIANCE IMPACT ASSESSMENT**
   - Financial impact by variance type
   - Inventory accuracy implications
   - Cash flow effects
   - Audit and compliance considerations

6. **RESOLUTION ROADMAP**
   
   **Immediate (Today):**
   - Critical variances requiring vendor contact
   - Missing delivery confirmations
   - High-value discrepancies
   
   **Short-term (This Week):**
   - Data standardization needs
   - Process clarifications
   - System configuration updates
   
   **Long-term (This Month):**
   - Vendor master data cleanup
   - Matching algorithm improvements
   - Tolerance threshold optimization

ANALYSIS GUIDELINES:
- Focus on business impact, not just technical details
- Provide specific, actionable recommendations
- Explain technical concepts in business terms
- Prioritize issues by financial and operational impact
- Include prevention strategies for future occurrences

Analysis:
"""
    
    VARIANCE_ANALYSIS_RESPONSE = """
You are analyzing FINANCIAL VARIANCES in reconciliation. Provide expert insights on amount differences and their implications.

USER QUESTION: {question}
VARIANCE DATA: {result_count} records with variances
VARIANCE PATTERNS: {sample_data}
STATISTICAL SUMMARY: {data_summary}

VARIANCE ANALYSIS STRUCTURE:

1. **VARIANCE MAGNITUDE ASSESSMENT**
   - Total variance amount and business impact
   - Distribution of variances (small, medium, large)
   - Percentage impact on total transaction values

2. **VARIANCE CATEGORIZATION**
   - Price variances (unit rate differences)
   - Quantity variances (delivery vs invoice quantities)
   - Tax variances (CGST, SGST, IGST differences)
   - Calculation errors vs legitimate differences

3. **ROOT CAUSE ANALYSIS**
   - Pricing discrepancies (negotiated vs contracted rates)
   - Measurement unit differences
   - Tax rate application errors
   - Freight and handling charge variations
   - Currency or exchange rate impacts

4. **TOLERANCE ANALYSIS**
   - Variances within acceptable tolerance
   - Variances exceeding thresholds
   - Tolerance setting appropriateness

5. **FINANCIAL IMPLICATIONS**
   - Impact on profitability
   - Cash flow effects
   - Budget variance implications
   - Audit trail requirements

6. **CORRECTIVE ACTIONS**
   - Immediate corrections needed
   - Vendor price confirmations required
   - Process standardization opportunities
   - System configuration improvements

Explain the business significance of each variance type.

Analysis:
"""
    
    EXCEPTION_ANALYSIS_RESPONSE = """
You are analyzing CRITICAL EXCEPTIONS in reconciliation. Provide expert guidance on high-priority issues requiring immediate attention.

USER QUESTION: {question}
EXCEPTION DATA: {result_count} exceptions identified
CRITICAL ISSUES: {sample_data}
SEVERITY ASSESSMENT: {data_summary}

EXCEPTION ANALYSIS STRUCTURE:

1. **EXCEPTION SEVERITY RANKING**
   - Critical (immediate action required)
   - High (resolve within 24-48 hours)
   - Medium (resolve within week)
   - Low (monitor and batch resolve)

2. **EXCEPTION CATEGORIZATION**
   - Missing records (no GRN found for invoice)
   - Data integrity issues (corrupt or incomplete data)
   - Business rule violations (tolerance exceeded)
   - System failures (matching algorithm issues)
   - Process breakdowns (approval bottlenecks)

3. **ROOT CAUSE INVESTIGATION**
   - System-level causes (configuration, bugs)
   - Process-level causes (workflow gaps, training)
   - Data-level causes (quality, completeness)
   - External causes (vendor issues, market changes)

4. **BUSINESS RISK ASSESSMENT**
   - Financial exposure
   - Compliance violations
   - Operational disruptions
   - Vendor relationship risks
   - Audit findings potential

5. **ESCALATION MATRIX**
   - Issues requiring immediate C-level attention
   - Department-level escalations needed
   - Vendor management involvement
   - IT support requirements

6. **RESOLUTION ROADMAP**
   - Emergency fixes (today)
   - Short-term solutions (this week)
   - Medium-term improvements (this month)
   - Long-term preventive measures

Prioritize by business impact and urgency.

Analysis:
"""
    
    WORKFLOW_ANALYSIS_RESPONSE = """
You are analyzing WORKFLOW EFFICIENCY in reconciliation processes. Provide expert insights on operational performance and bottlenecks.

USER QUESTION: {question}
WORKFLOW DATA: {result_count} workflow records
PROCESS METRICS: {sample_data}
EFFICIENCY INDICATORS: {data_summary}

WORKFLOW ANALYSIS STRUCTURE:

1. **PROCESS PERFORMANCE OVERVIEW**
   - Overall efficiency metrics
   - Automation vs manual processing rates
   - Average processing times
   - Bottleneck identification

2. **APPROVAL WORKFLOW ANALYSIS**
   - Approval success rates
   - Time-to-approval distributions
   - Escalation patterns
   - Manual intervention requirements

3. **RESOURCE UTILIZATION**
   - Staff workload distribution
   - Peak processing times
   - Capacity constraints
   - Skill gap identification

4. **QUALITY METRICS**
   - First-pass success rates
   - Rework requirements
   - Error rates by process step
   - User satisfaction indicators

5. **BOTTLENECK ANALYSIS**
   - Process steps causing delays
   - Resource constraints
   - System performance issues
   - Communication gaps

6. **OPTIMIZATION OPPORTUNITIES**
   - Automation possibilities
   - Process simplification options
   - Training needs
   - Technology improvements
   - Policy clarifications

7. **PERFORMANCE IMPROVEMENT PLAN**
   - Quick wins (immediate improvements)
   - Process redesign opportunities
   - Technology investments needed
   - Change management requirements

Focus on operational efficiency and user experience.

Analysis:
"""
    
    SIMPLE_ANALYSIS_RESPONSE = """
Analyze the reconciliation data and provide business insights.

USER QUESTION: {question}
DATA FOUND: {result_count} records
KEY FINDINGS: {sample_data}

Provide:
1. What the data shows
2. Key insights and patterns
3. Business implications
4. Recommended actions

Keep the response clear, actionable, and business-focused.

Analysis:
"""
    
    @classmethod
    def get_analysis_prompt_for_type(cls, analysis_type: str) -> str:
        """Get specific analysis prompt based on analysis type"""
        prompt_map = {
            'mismatch_analysis': cls.MISMATCH_ANALYSIS_RESPONSE,
            'variance_analysis': cls.VARIANCE_ANALYSIS_RESPONSE,
            'exception_analysis': cls.EXCEPTION_ANALYSIS_RESPONSE,
            'workflow_analysis': cls.WORKFLOW_ANALYSIS_RESPONSE,
            'general': cls.INTELLIGENT_ANALYSIS_PROMPT
        }
        return prompt_map.get(analysis_type, cls.INTELLIGENT_ANALYSIS_PROMPT)