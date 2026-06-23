import nltk
from nltk.tokenize import sent_tokenize
from typing import List, Dict, Optional
import re

try:
    from llama_index.core.schema import TextNode
except ImportError:
    class TextNode:
        def __init__(self, text: str, metadata: Optional[Dict] = None):
            self.text = text
            self.metadata = metadata if metadata is not None else {}
        def __repr__(self):
            return f"TextNode(text='{self.text[:50]}...', metadata={self.metadata})"

try:
    nltk.data.find('tokenizers/punkt')
except Exception:
    try:
        nltk.download('punkt', quiet=True)
    except Exception as e:
        print(f"Warning: Failed to download nltk 'punkt' tokenizer. Error: {e}")


def pre_segment_into_major_units(text: str) -> List[Dict[str, str]]:
    """Segments text into major units based on patterns like 'Unit X: Title'."""
    keywords = ["Unit", "Chapter", "Section", "Module", "Part"]
    keyword_pattern = "|".join(keywords)
    
    try:
        unit_delimiters = list(re.finditer(
            r"^((?:%s)\s*\d+:\s*.*?)(?=\n|$)" % keyword_pattern, 
            text, 
            re.MULTILINE | re.IGNORECASE
        ))
    except re.error as e:
        print(f"Regex error in pre_segment_into_major_units: {e}")
        unit_delimiters = []
        
    if not unit_delimiters:
        if text.strip():
            return [{
                "title_line": "Full Document Content",
                "content": text.strip(),
                "is_primary_unit": False 
            }]
        return []

    segmented_units = []
    for i, match_obj in enumerate(unit_delimiters):
        unit_title_line = match_obj.group(1).strip()
        content_start_index = match_obj.end()
        
        if i + 1 < len(unit_delimiters):
            content_end_index = unit_delimiters[i+1].start()
        else:
            content_end_index = len(text)
            
        unit_content = text[content_start_index:content_end_index].strip()
        
        if unit_content:
            segmented_units.append({
                "title_line": unit_title_line,
                "content": unit_content,
                "is_primary_unit": True
            })
            
    return segmented_units


def smart_chunk_with_content_awareness(
    text: str,
    max_chunk_chars: int = 6000,
    overlap_chars: int = 200,
    metadata: Optional[Dict] = None
) -> List[TextNode]:
    """Splits text into chunks based on paragraphs with content awareness."""
    if not text.strip():
        return []

    raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if not raw_paragraphs:
        raw_paragraphs = [text.strip()]
        
    chunks = []
    current_chunk_content = ""

    for para_text in raw_paragraphs:
        # Handle oversized paragraphs
        if len(para_text) > max_chunk_chars:
            if current_chunk_content.strip():
                chunks.append(TextNode(text=current_chunk_content, metadata=dict(metadata or {})))
                current_chunk_content = ""
            
            # Split large paragraph at sentence boundaries
            chunks.extend(_split_oversized_paragraph(para_text, max_chunk_chars, metadata))
            continue

        # Check if adding paragraph would exceed limit
        separator_len = len("\n\n") if current_chunk_content else 0
        if current_chunk_content and (len(current_chunk_content) + separator_len + len(para_text) > max_chunk_chars):
            chunks.append(TextNode(text=current_chunk_content, metadata=dict(metadata or {})))
            
            # Extract overlap using your existing logic
            overlap_text = _extract_overlap_content(current_chunk_content, overlap_chars)
            current_chunk_content = overlap_text
            
            if current_chunk_content and para_text:
                current_chunk_content += "\n\n" + para_text
            elif para_text:
                current_chunk_content = para_text
        else:
            # Add paragraph to current chunk
            if current_chunk_content:
                current_chunk_content += "\n\n" + para_text
            else:
                current_chunk_content = para_text

    if current_chunk_content.strip():
        chunks.append(TextNode(text=current_chunk_content, metadata=dict(metadata or {})))
    
    return chunks


def _split_oversized_paragraph(para_text: str, max_chunk_chars: int, metadata: Optional[Dict]) -> List[TextNode]:
    """Split oversized paragraph at sentence boundaries when possible."""
    try:
        sentences = sent_tokenize(para_text)
    except Exception:
        # Fallback to simple splitting
        return [TextNode(text=para_text[i:i+max_chunk_chars], metadata=dict(metadata or {})) 
                for i in range(0, len(para_text), max_chunk_chars)]
    
    chunks = []
    current_content = ""
    
    for sentence in sentences:
        if len(sentence) > max_chunk_chars:
            # Handle extremely long sentences
            if current_content:
                chunks.append(TextNode(text=current_content, metadata=dict(metadata or {})))
                current_content = ""
            
            # Split long sentence by characters
            for i in range(0, len(sentence), max_chunk_chars):
                chunk_text = sentence[i:i+max_chunk_chars]
                chunks.append(TextNode(text=chunk_text, metadata=dict(metadata or {})))
        elif current_content and len(current_content) + len(sentence) + 1 > max_chunk_chars:
            chunks.append(TextNode(text=current_content, metadata=dict(metadata or {})))
            current_content = sentence
        else:
            current_content += (" " if current_content else "") + sentence
    
    if current_content:
        chunks.append(TextNode(text=current_content, metadata=dict(metadata or {})))
    
    return chunks


def _extract_overlap_content(current_chunk_content: str, overlap_chars: int) -> str:
    """Extract overlap content using your existing logic."""
    if overlap_chars <= 0 or not current_chunk_content:
        return ""
    
    try:
        sentences = sent_tokenize(current_chunk_content)
        temp_overlap_content = ""
        
        for s_idx in range(len(sentences) - 1, -1, -1):
            s = sentences[s_idx]
            test_length = len(s) + len(temp_overlap_content) + (1 if temp_overlap_content else 0)
            
            if test_length <= overlap_chars:
                temp_overlap_content = s + (" " if temp_overlap_content else "") + temp_overlap_content
            else:
                if not temp_overlap_content and len(s) > overlap_chars:
                    temp_overlap_content = s[-overlap_chars:]
                break
        
        return temp_overlap_content.strip()
    except Exception:
        if len(current_chunk_content) > overlap_chars:
            return current_chunk_content[-overlap_chars:]
        else:
            return current_chunk_content