import json
import logging
import tempfile
import shutil
from typing import List, Any, Dict, Literal, Optional

from .preprocess import smart_chunk_with_content_awareness, \
    pre_segment_into_major_units
from .plan_prompt import plan_prompter
from .direct_summarize_prompt import direct_summarize_prompter
from services.vector_store import VectorStore
from services.llm_factory import get_completion_fn
from agents.models import LearningUnit, PlannerResponse
from llama_index.core.schema import TextNode
from llama_index.core import SimpleDirectoryReader

class PlannerAgent:
    def __init__(self, provider: str = "openai", model_name: str = None, api_key: str = None):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.llm = get_completion_fn(provider, model_name, api_key)
        self.vector_store = VectorStore() # Initialize VectorStore for Planner's internal context

    def _load_document_with_llama_index(self, file_path: str) -> str:
        """
        Loads content from various document types using LlamaIndex's SimpleDirectoryReader.
        Returns concatenated text content from all loaded documents.
        """
        try:
            # Create a temporary directory and copy the file into it
            # SimpleDirectoryReader expects a directory
            with tempfile.TemporaryDirectory() as tmpdir:
                shutil.copy(file_path, tmpdir)
                
                reader = SimpleDirectoryReader(input_dir=tmpdir)
                documents = reader.load_data()
                
                full_text = ""
                for doc in documents:
                    full_text += doc.text + "\n\n" # Concatenate text from all documents
                return full_text.strip()
        except Exception as e:
            logging.error(f"Error loading document with LlamaIndex from {file_path}: {e}", exc_info=True)
            return ""

    def _direct_llm_summarization(self, content: str,
                                  source_metadata_base: Dict[str, Any]) -> List[LearningUnit]:
        """
        Attempts to get learning units directly from LLM summarization.
        Returns a list of LearningUnit objects or an empty list on failure.
        """
        logging.info("Attempting direct LLM summarization...")
        prompt = direct_summarize_prompter(content)
        try:
            response_str = self.llm(prompt)
            response_str = response_str.strip()
            if response_str.startswith("```json") and response_str.endswith("```"):
                response_str = response_str[len("```json"):-len("```")].strip()
            elif response_str.startswith("```") and response_str.endswith("```"):
                response_str = response_str[len("```"):-len("```")].strip()

            raw_units = json.loads(response_str)
            if not isinstance(raw_units, list):
                raise ValueError("LLM did not return a JSON array.")

            validated_units = []
            for item in raw_units:
                if "title" in item and "summary" in item:
                    unit_content = content # For direct summarization, the unit content is the whole document
                    unit_metadata = {**source_metadata_base,
                                     "generation_method": "direct_llm_summarization"}
                    validated_units.append(LearningUnit(
                        title=item["title"],
                        content_raw=unit_content,
                        summary=item["summary"],
                        metadata=unit_metadata
                    ))
                else:
                    logging.warning(f"Skipping malformed unit from direct LLM response: {item}")
            
            if len(validated_units) > 50:
                logging.warning(f"Direct LLM generated {len(validated_units)} units, "
                                "truncating to the first 50.")
                validated_units = validated_units[:50]

            logging.info(f"Direct LLM summarization successful, generated {len(validated_units)} units.")
            return validated_units
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logging.error(f"Direct LLM summarization failed: {e}", exc_info=True)
            return []

    def act(self, data: str, input_type: str) -> List[LearningUnit]:
        raw_text_to_process = ""
        source_metadata_base: Dict[str, Any] = {}

        # Use the new LlamaIndex loader for all file types, including PDF
        if input_type.upper() in ["PDF", "FILE"]: # Added "FILE"
            raw_text_to_process = self._load_document_with_llama_index(data)
            source_metadata_base = {"source_file": data.split('/')[-1]
                                    if '/' in data else data, "original_input_type": input_type.upper()}
        elif input_type.upper() == "TEXT":
            raw_text_to_process = data
            source_metadata_base = {"source_type": "text_input", "original_input_type": "TEXT"}
        else:
            logging.warning(f"Unsupported input_type: {input_type}")
            return []

        if not raw_text_to_process.strip():
            logging.warning("No text content to process after loading.")
            return []

        # Clear vector store for new document processing
        self.vector_store.clear()

        direct_units = self._direct_llm_summarization(raw_text_to_process,
                                                       source_metadata_base)
        if direct_units:
            logging.info("Using units from direct LLM summarization.")
            # Add units to Planner's internal vector store
            self.vector_store.add_documents([unit.model_dump() for unit in direct_units])
            return PlannerResponse(units=direct_units).units
        
        logging.info("Direct LLM summarization failed or returned no units. "
                     "Falling back to sophisticated segmentation.")

        major_identified_units = pre_segment_into_major_units(raw_text_to_process)
        logging.debug(f"Number of major_identified_units: {len(major_identified_units)}")
        
        all_final_nodes_for_llm = []
        if not major_identified_units and raw_text_to_process.strip():
            major_identified_units = [{"title_line": "Document Content",
                                       "content": raw_text_to_process,
                                       "is_primary_unit": True}]

        for major_unit in major_identified_units:
            major_unit_title_line = major_unit["title_line"]
            major_unit_content = major_unit["content"]
            
            current_metadata = {
                **source_metadata_base,
                "original_unit_heading": major_unit_title_line,
                "is_primary_unit_segment": str(major_unit.get("is_primary_unit", False)),
                "generation_method": "sophisticated_segmentation"
            }
            
            nodes_from_this_major_unit = smart_chunk_with_content_awareness(
                major_unit_content,
                metadata=current_metadata
            )
            logging.debug(f"For major_unit '{major_unit_title_line}', smart_chunker produced "
                          f"{len(nodes_from_this_major_unit)} nodes.")
            
            if not nodes_from_this_major_unit and major_unit_content.strip():
                all_final_nodes_for_llm.append(TextNode(text=major_unit_content,
                                                        metadata=current_metadata))
            else:
                all_final_nodes_for_llm.extend(nodes_from_this_major_unit)

        logging.debug(f"Total nodes in all_final_nodes_for_llm before LLM processing: "
                      f"{len(all_final_nodes_for_llm)}")

        units_processed_raw = []
        node_counter = 0
        for node in all_final_nodes_for_llm:
            node_counter += 1
            chunk_content = node.text
            chunk_metadata = node.metadata
            
            contextual_heading = chunk_metadata.get("original_unit_heading",
                                                    f"Segment {node_counter}")
            
            # Retrieve previous chapter context from Planner's internal vector store
            previous_chapter_context = []
            if self.vector_store.documents: # Only search if there are existing documents
                retrieved_docs = self.vector_store.search(chunk_content, k=2) # Retrieve top 2 relevant docs
                previous_chapter_context = [doc['content'] for doc in retrieved_docs]
                logging.debug(f"Retrieved {len(previous_chapter_context)} previous chapter contexts for segment {node_counter}.")

            prompt = plan_prompter(chunk_content, context_title=contextual_heading,
                                   previous_chapter_context=previous_chapter_context) 

            try:
                response_str = self.llm(prompt)
                unit_details_from_llm = json.loads(response_str) 

                if not isinstance(unit_details_from_llm, dict):
                    raise ValueError("LLM did not return a JSON object (dictionary).")

                final_title = unit_details_from_llm.get("title", "").strip()
                if not final_title:
                    if chunk_metadata.get("is_primary_unit_segment"):
                        final_title = chunk_metadata.get("original_unit_heading")
                    else:
                        final_title = (f"{chunk_metadata.get('original_unit_heading', 'Content Segment')} - "
                                       f"Part {node_counter}")
                
                if not final_title:
                     final_title = f"Learning Unit {node_counter}"

                new_unit_data = {
                    "title": final_title,
                    "content_raw": chunk_content,
                    "summary": unit_details_from_llm.get("summary", "Summary not available."),
                    "metadata": chunk_metadata
                }
                units_processed_raw.append(new_unit_data)
                # Add the newly generated unit to the Planner's internal vector store
                self.vector_store.add_documents([new_unit_data])

            except (json.JSONDecodeError, ValueError, Exception) as e:
                logging.error(f"Error processing LLM response for node (context: {contextual_heading}): {e}. "
                              f"Response: '{response_str[:200]}...'", exc_info=True)
                fb_title = chunk_metadata.get("original_unit_heading",
                                              f"Unit Segment {node_counter}")
                try:
                    fb_summary = self.llm(f"Provide a concise summary (max 80 words) for the following content, "
                                          f"which is part of '{fb_title}':\n\n{chunk_content}")
                except Exception as e_sum:
                    logging.error(f"Error generating fallback summary: {e_sum}", exc_info=True)
                    fb_summary = "Summary generation failed."
                
                fallback_unit_data = {
                    "title": fb_title,
                    "content_raw": chunk_content,
                    "summary": fb_summary.strip(),
                    "metadata": chunk_metadata
                }
                units_processed_raw.append(fallback_unit_data)
                # Add the fallback unit to the Planner's internal vector store
                self.vector_store.add_documents([fallback_unit_data])
        
        final_learning_units_data = []
        titles_seen = set()
        for unit_data in units_processed_raw:
            current_title = unit_data['title']
            temp_title = current_title
            part_counter = 1
            while temp_title in titles_seen:
                temp_title = f"{current_title} (Part {part_counter})"
                part_counter += 1
            
            unit_data['title'] = temp_title
            titles_seen.add(temp_title)
            final_learning_units_data.append(unit_data)

        validated_units = [LearningUnit(**unit_data) for unit_data in final_learning_units_data]
        
        if len(validated_units) > 50:
            logging.warning(f"Generated {len(validated_units)} units, truncating to the first 50.")
            validated_units = validated_units[:50]
            
        return PlannerResponse(units=validated_units).units
