class AnalysisGenerationPrompts:
    """Concise analysis generation prompts for quick business insights"""
    
    INTELLIGENT_ANALYSIS_PROMPT = """
You are an expert business analyst analyzing reconciliation data.

USER QUESTION: {question}
DATA FOUND: {result_count} records
ACTUAL DATA SAMPLE: {sample_data}
DATA SUMMARY: {data_summary}

RESPONSE RULES:
1. If user asks to "show", "list", "display", "give me", "what are" - FIRST show actual data from the sample
2. Extract relevant fields from the sample data and display them in a clean list format
3. Then provide 2-3 sentence business analysis
4. Include rectification steps

RESPONSE FORMAT when showing data:
**[Relevant Data Title]:**
[Extract and display actual values from sample_data - in tabel format]
| Column1 | Column2 | Column3 | Column4 |
|---------|---------|---------|---------|
| value1  | value2  | value3  | value4  |

**Analysis:** [Your 2-3 sentence analysis with rectification steps]

For non-listing questions, provide analysis only.

Analysis:
"""
    
    MISMATCH_ANALYSIS_RESPONSE = """
Analyze RECONCILIATION MISMATCHES in 2-3 concise sentences.

USER QUESTION: {question}
MISMATCH DATA: {result_count} mismatched records
ACTUAL DATA: {sample_data}
PATTERNS: {data_summary}

RESPONSE RULES:
1. If user asks to "show", "list", "display", "give me" - FIRST show actual data from sample_data
2. Extract relevant fields dynamically and display them
3. Then provide mismatch analysis with rectification steps

RESPONSE FORMAT for data requests:
**[Dynamic Title Based on Data]:**
[Extract and display actual values from sample_data - in table format]
| Column1 | Column2 | Column3 | Column4 |
|---------|---------|---------|---------|
| value1  | value2  | value3  | value4  |

**Analysis:** [Your analysis with rectification steps]

For other questions, provide analysis only.

Analysis:
"""
    
    VARIANCE_ANALYSIS_RESPONSE = """
Analyze FINANCIAL VARIANCES in 2-3 concise sentences.

USER QUESTION: {question}
VARIANCE DATA: {result_count} records with variances
ACTUAL DATA: {sample_data}
PATTERNS: {data_summary}

Provide:
1. If user asks to "show", "list", "display", "give me" - FIRST show actual data from sample_data
2. Extract relevant fields dynamically and display them in a clean list
3. Variance magnitude and main cause
4. Business impact
5. Corrective action needed
6. How to rectify the variances (specific steps)

RESPONSE FORMAT for data requests:
**Records Found:**
[Extract and list actual values from sample_data - show PO numbers, invoice numbers, variance amounts, etc.]
| Column1 | Column2 | Column3 | Column4 |
|---------|---------|---------|---------|
| value1  | value2  | value3  | value4  |

**Analysis:** [Brief workflow analysis]

For other questions, provide analysis only.

Analysis:
Analysis:
"""
    
    EXCEPTION_ANALYSIS_RESPONSE = """
Analyze CRITICAL EXCEPTIONS in 2-3 concise sentences.

USER QUESTION: {question}
EXCEPTION DATA: {result_count} exceptions
SEVERITY: {data_summary}

Provide:
1. Exception type and urgency level
2. Business risk
3. Immediate resolution steps
4. How to rectify and prevent future exceptions

Maximum 4 sentences. Prioritize by business impact and include rectification.

Analysis:
"""
    
    WORKFLOW_ANALYSIS_RESPONSE = """
Analyze WORKFLOW EFFICIENCY in 2-3 concise sentences.

USER QUESTION: {question}
WORKFLOW DATA: {result_count} workflow records
ACTUAL DATA: {sample_data}
METRICS: {data_summary}

Provide:
1.If user asks to "show", "list", "display", "give me" - FIRST show actual data from sample_data
2. Extract relevant fields dynamically and display them in a clean list
3. Process efficiency status
4. Main bottleneck identified
5. Improvement action needed
6. How to rectify workflow issues and optimize process

RESPONSE FORMAT for data requests:
**Records Found:**
[Extract and list actual values from sample_data - show PO numbers, invoice numbers, variance amounts, etc.]

**Analysis:** [Brief workflow analysis]

For other questions, provide analysis only.

Analysis:
Analysis:
"""
    
    SIMPLE_ANALYSIS_RESPONSE = """
Provide a concise reconciliation analysis in exactly 2-3 sentences.

USER QUESTION: {question}
DATA FOUND: {result_count} records
KEY FINDINGS: {sample_data}

Requirements:
1. Summarize the core issue in one sentence
2. Explain the business impact in one sentence  
3. State the immediate action needed in one sentence
4. Include rectification steps to resolve the issue

Keep it simple, direct, and actionable with specific rectification guidance.

Analysis:
"""
    SUMMARY_ANALYSIS_RESPONSE = """
Provide a concise summary analysis for count/total queries.
USER QUESTION: {question}
COUNT RESULT: {result_count} records
DATA: {sample_data}

For count queries, provide:
1. Direct answer to the count question
2. Brief interpretation of what this number means
3. Context about whether this is good/bad/normal
4. One actionable next step if relevant

Keep response under 3 sentences and focus on answering the count question directly.

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
            'summary_analysis': cls.SUMMARY_ANALYSIS_RESPONSE,
            'general': cls.INTELLIGENT_ANALYSIS_PROMPT
        }
        return prompt_map.get(analysis_type, cls.SIMPLE_ANALYSIS_RESPONSE)