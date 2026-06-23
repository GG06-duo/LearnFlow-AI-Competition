def direct_summarize_prompter(document_content: str) -> str:
    """
    Generates a prompt for the LLM to directly summarize a document into learning units.
    The LLM is expected to return a JSON array of LearningUnit-like objects.
    """
    return f"""
You are an expert educator and content structurer. Your task is to read the provided document and break it down into a list of distinct, coherent learning units. Each unit should have a concise title and a summary of its content.

The output MUST be a JSON array of objects, where each object has the following structure:
{{
    "title": "Concise title of the learning unit",
    "summary": "A brief summary of the learning unit's content (max 100 words)"
}}

Ensure that:
- Each learning unit covers a distinct concept or section from the document.
- Titles are clear and descriptive.
- Summaries are informative and capture the essence of the unit.
- The entire document is covered across the generated units.
- Do NOT include any introductory or concluding remarks outside the JSON.
- The JSON array should contain between 5 and 50 learning units, depending on the document's length and complexity.

Here is the document content:

---
{document_content}
---

Please provide the JSON array of learning units:
"""
