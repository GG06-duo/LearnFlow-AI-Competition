import re
import textwrap
from typing import Optional 
from services.llm_factory import get_completion_fn

def make_code_snippet(
    title: str,
    content: str,
    suggestion: str,
    llm_provider: str,
    llm_model_name: Optional[str] = None,
    llm_api_key: Optional[str] = None
) -> str:
    """Generate a code snippet based on suggestion using LLM."""
    if not suggestion.strip():
        return textwrap.dedent(
            f"""
            # No specific code suggestion for {title}
            # Content preview: {content[:40]}...
            """
        )
    
    prompt = f"""
    You are an expert Python programmer tasked with generating a single, self-contained, and runnable code snippet.
    
    **Task:**
    Generate a concise Python code snippet that directly implements the following request.
    - The code MUST be self-contained (include all necessary imports).
    - The code MUST end with a `print()` statement to show the final result.
    - For mathematical/scientific tasks, **strongly prefer using libraries like `numpy`, `scipy`, and `sympy`** to ensure the code is correct and robust.
    - Do not include any explanations or comments outside of essential clarifications.
    - Do not use plotting libraries like matplotlib.

    **Request:** "{suggestion}"
    
    **Full Context (for reference):**
    - Unit Title: {title}
    - Unit Content: {content}

    **Your Python Code Snippet:**
    ```python
    # Your code here
    ```
    """
    
    try:
        llm = get_completion_fn(
            provider=llm_provider, 
            model_name=llm_model_name, 
            api_key=llm_api_key
        )
        response = llm(prompt)
        
        # Extract code block, being more flexible with whitespace around backticks
        code_match = re.search(r'```python\s*\n(.*?)\n\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Fallback if no code block is found, return the whole response
        return response.strip()
    except Exception as e: 
        logging.error(f"Failed to generate code for '{title}' due to LLM error: {e}", exc_info=True)
        return textwrap.dedent(
            f"""
            # Failed to generate code for {title}
            # Content preview: {content[:40]}...
            # Error: {e}
            """
        )