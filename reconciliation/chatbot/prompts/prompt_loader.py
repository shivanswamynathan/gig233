import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PromptLoader:
    """Utility class to load and manage prompts from files or classes"""
    
    @staticmethod
    def load_template(prompt_content: str, **kwargs) -> str:
        """
        Load and format a prompt template with provided variables
        
        Args:
            prompt_content: The prompt template content
            **kwargs: Variables to substitute in the template
            
        Returns:
            Formatted prompt string
        """
        try:
            return prompt_content.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            raise ValueError(f"Missing required template variable: {e}")
        except Exception as e:
            logger.error(f"Error formatting prompt template: {e}")
            raise
    
    @staticmethod
    def validate_required_vars(prompt_content: str, provided_vars: Dict[str, Any]) -> bool:
        """
        Validate that all required variables are provided for a prompt template
        
        Args:
            prompt_content: The prompt template content
            provided_vars: Dictionary of provided variables
            
        Returns:
            True if all required variables are provided
        """
        import re
        
        # Find all variables in the format {variable_name}
        required_vars = set(re.findall(r'\{(\w+)\}', prompt_content))
        provided_vars_set = set(provided_vars.keys())
        
        missing_vars = required_vars - provided_vars_set
        
        if missing_vars:
            logger.warning(f"Missing required variables: {missing_vars}")
            return False
        
        return True
    
    @staticmethod
    def get_prompt_with_fallback(primary_prompt: str, fallback_prompt: str, **kwargs) -> str:
        """
        Try to use primary prompt, fall back to simpler prompt if variables are missing
        
        Args:
            primary_prompt: Main prompt template to try first
            fallback_prompt: Simpler prompt to use if primary fails
            **kwargs: Variables for template substitution
            
        Returns:
            Formatted prompt string
        """
        try:
            if PromptLoader.validate_required_vars(primary_prompt, kwargs):
                return PromptLoader.load_template(primary_prompt, **kwargs)
            else:
                logger.info("Using fallback prompt due to missing variables")
                return PromptLoader.load_template(fallback_prompt, **kwargs)
        except Exception as e:
            logger.error(f"Error in prompt loading: {e}")
            return fallback_prompt.format(**{k: v for k, v in kwargs.items() if k in fallback_prompt})