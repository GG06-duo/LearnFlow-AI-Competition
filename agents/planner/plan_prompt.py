from typing import List

def plan_prompter(chunk: str, context_title: str, previous_chapter_context: List[str]) -> str:
    """
    Generates a prompt for the LLM to process a pre-segmented chunk of text
    as a single learning unit, considering previously generated chapters.

    Args:
        chunk: The text content of the current segment.
        context_title: The original heading or broader topic context for this chunk
                       (e.g., "Unit 474: Gaussian Quadrature with 4 Integration Points").
        previous_chapter_context: A list of content from previously generated learning units,
                                  relevant to the current chunk.
    Returns:
        A string prompt for the LLM.
    """
    previous_context_section = ""
    if previous_chapter_context:
        context_items = "\n".join([f"- {item}" for item in previous_chapter_context])
        previous_context_section = f"""
**Previously Generated Learning Units (Relevant Context):**
The following are summaries or content from learning units that have already been generated and are semantically similar to the current text segment. Use this information to ensure the new unit's title and summary avoid redundancy and, where appropriate, build upon these existing concepts.

{context_items}

---
"""
    return f"""
You are an expert in curriculum design and instructional breakdown.

**Your Task:**
You have been provided with a text segment. This segment is part of a larger topic originally identified with the heading or context: "{context_title}".
Your job is to treat THIS specific text segment as a **single, focused learning unit**.

### Text Segment:
---
{chunk}
---

{previous_context_section}

### Instructions for THIS Segment:
1.  **Title:** Create a clear, concise, and descriptive title for THIS specific text segment.
    *   You can use or adapt the context "{context_title}" if it accurately reflects the content of THIS segment.
    *   If THIS segment is clearly a specific part of "{context_title}", the title should reflect that (e.g., if context_title is "Derivatives" and the chunk is about the chain rule, a title like "Derivatives: The Chain Rule" would be good).
    *   Avoid generic titles like "Unit 1" unless "{context_title}" itself implies it's the only topic.
    *   **Crucially, review the "Previously Generated Learning Units" section to ensure your new title does not overlap significantly with existing titles and accurately reflects new information or a deeper dive.**
2.  **Summary:** Write a 1-paragraph summary (approximately 50-80 words) explaining what THIS specific text segment teaches. The summary should be self-contained for this segment.
    *   **Crucially, review the "Previously Generated Learning Units" section to ensure your new summary avoids redundancy with existing summaries and, if applicable, explicitly builds upon or extends concepts from those previous units.**

### Output Format:
Return your response as a **SINGLE JSON object** (NOT a JSON array).
This JSON object MUST contain exactly two keys:
  - `"title"`: (string) The refined title for this segment.
  - `"summary"`: (string) The summary of this segment.

**Example of Expected Output Format:**
{{
  "title": "Gaussian Quadrature: 4-Point Integration",
  "summary": "This unit explains the application of Gaussian quadrature using 4 integration points, focusing on its use in the Gauss-Legendre quadrature method for numerical analysis."
}}

---

**Crucial Constraints for THIS Task:**
- **DO NOT** attempt to break THIS text segment into multiple smaller units. Process it as one.
- Your output **MUST BE a single JSON object**, not a list or array.
---
"""
