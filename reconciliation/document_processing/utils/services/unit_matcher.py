"""
Unit Matcher using Gemini LLM with Caching (No Fallback)
"""

import google.generativeai as genai
import os
from django.conf import settings

# Initialize Gemini
api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# Cache for repeated calls
unit_cache = {}

def check_unit_match(unit1, unit2):
    """
    Compare two units using LLM only. No fallback.
    Returns True if equivalent, else False.
    """
    if not unit1 or not unit2:
        return False

    u1 = unit1.strip().upper()
    u2 = unit2.strip().upper()


    key = f"{u1}|{u2}"
    if key in unit_cache:
        return unit_cache[key]

    try:

        prompt = f"""
        Are these two units of measurement equivalent or the same?

        Unit 1: {unit1}
        Unit 2: {unit2}

        Consider:
        - PCS, PIECES, NOS, NUMBERS are all counting units (equivalent)
        - KG, KILOGRAM are weight units (equivalent)
        - M, METER, METRES are length units (equivalent)
        - Different units like KG vs PCS are NOT equivalent

        Respond with only: YES or NO
        """
        response = model.generate_content(prompt)
        answer = response.text.strip().upper()
        result = "YES" in answer
        unit_cache[key] = result
        return result

    except Exception as e:
        print(f"Gemini API error in unit match: {e}")
        unit_cache[key] = False
        return False
