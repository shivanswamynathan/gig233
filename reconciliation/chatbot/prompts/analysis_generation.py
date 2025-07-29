class AnalysisGenerationPrompts:
    """Concise analysis generation prompts for quick business insights"""
    
    INTELLIGENT_ANALYSIS_PROMPT = """
You are an expert business analyst. Provide a CONCISE analysis in exactly 2-3 sentences.

USER QUESTION: {question}
DATA FOUND: {result_count} records
KEY FINDINGS: {sample_data}
SUMMARY: {data_summary}

RESPONSE REQUIREMENTS:
- Maximum 4 sentences
- First sentence: Core issue/finding
- Second sentence: Business impact or root cause
- Third sentence: Immediate action needed
- Fourth sentence: How to rectify/resolve the issue
- Be direct and actionable
- Use business language, not technical jargon

Analysis:
"""
    
    MISMATCH_ANALYSIS_RESPONSE = """
Analyze RECONCILIATION MISMATCHES in 2-3 concise sentences.

USER QUESTION: {question}
MISMATCH DATA: {result_count} mismatched records
PATTERNS: {data_summary}

Provide:
1. What type of mismatch is occurring
2. Why it's happening (root cause)
3. Immediate action needed
4. How to rectify the issue (specific steps)

Keep response under 4 sentences. Include rectification steps.

Analysis:
"""
    
    VARIANCE_ANALYSIS_RESPONSE = """
Analyze FINANCIAL VARIANCES in 2-3 concise sentences.

USER QUESTION: {question}
VARIANCE DATA: {result_count} records with variances
PATTERNS: {data_summary}

Provide:
1. Variance magnitude and main cause
2. Business impact
3. Corrective action needed
4. How to rectify the variances (specific steps)

Maximum 4 sentences. Focus on financial impact, next steps, and rectification.

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
METRICS: {data_summary}

Provide:
1. Process efficiency status
2. Main bottleneck identified
3. Improvement action needed
4. How to rectify workflow issues and optimize process

Maximum 4 sentences. Focus on operational efficiency and process rectification.

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