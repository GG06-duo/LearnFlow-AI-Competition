from typing import Optional
from .explain_prompt import explain_prompter
from .tools.figure_generator import make_figure_tool
from .tools.code_generator import make_code_snippet
from agents.models import ExplanationResponse, VisualAid, CodeExample
import re
import base64
import os
import logging

from llama_index.core.agent import AgentRunner
from llama_index.llms.litellm import LiteLLM
from services.vector_store import VectorStore 
from services.llm_factory import _PROVIDER_MAP 

# Configure logging for explainer agent
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ExplainerAgent:
    def __init__(self, provider: str = "openai", vector_store: Optional[VectorStore] = None, model_name: str = None, api_key: str = None):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        
        # Get provider configuration, determine model and api key
        provider_cfg = _PROVIDER_MAP.get(provider, _PROVIDER_MAP["custom"])
        
        actual_model_name = model_name if model_name and model_name.strip() else provider_cfg["default_model"]
        full_model_id = f"{provider_cfg['model_prefix']}{actual_model_name}"
        
        actual_api_key = api_key if api_key and api_key.strip() else provider_cfg["api_key"]

        self.llm = LiteLLM(
            model=full_model_id,
            api_key=actual_api_key,
            api_base=provider_cfg.get("api_base")
        )
        
        self.tools = [make_figure_tool]
        self.agent = AgentRunner.from_llm(
            llm=self.llm,
            tools=self.tools,
            verbose=True,
            tool_calling_llm=self.llm
        )
        self.vector_store = vector_store 

    def act(self, title: str, content: str,
            explanation_style: str = "Concise") -> ExplanationResponse:
        
        retrieved_context = []
        if self.vector_store:
            # Use the title and content to query the vector store for relevant chunks
            # Combine title and start of context for the query and utilize top 3 relevant docs
            query = f"{title}. {content[:100]}" 
            retrieved_docs = self.vector_store.search(query, k=3) 
            retrieved_context = [doc['content'] for doc in retrieved_docs]
            logging.info(f"ExplainerAgent: Retrieved {len(retrieved_context)} context chunks.")

        base_prompt = explain_prompter(title, content, retrieved_context)
        
        if explanation_style == "Concise":
            style_instruction = ("Keep the explanation concise (max 400 words), "
                                 "focusing on core concepts.")
        elif explanation_style == "Detailed":
            style_instruction = ("Provide a detailed explanation, elaborating on concepts,"
                                 " examples, and deeper insights to master the topic.")
        else:
            style_instruction = ("Keep the explanation concise (max 400 words), "
                                 "focusing on core concepts.")

        prompt_message = f"""
        {base_prompt}
        {style_instruction}
        """
        
        chat_response = self.agent.chat(prompt_message)
        response_content = str(chat_response)

        visual_aids = []
        
        figure_path_pattern = re.compile(r'\[FIGURE_PATH: (.*?)\]')
        
        def embed_figure_in_markdown(match):
            figure_path = match.group(1).strip()
            logging.info(f"ExplainerAgent: Processing generated figure path: '{figure_path}'")
            
            if not figure_path or not os.path.exists(figure_path):
                logging.warning(f"ExplainerAgent: Figure path '{figure_path}' is invalid or "
                                "file does not exist. Skipping embedding.")
                return f'\n\n*📊 Figure not found at: {figure_path}*\n\n'

            figure_caption = f"Generated Figure for {title}"
            
            visual_aids.append(VisualAid(type="image", path=figure_path, caption=figure_caption))
            try:
                with open(figure_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode()
                logging.info(f"ExplainerAgent: Successfully encoded image to base64 for "
                             f"'{figure_caption}'")
                return f'\n\n![{figure_caption}](data:image/png;base64,{img_data})\n\n'
            except Exception as e:
                logging.error(f"Error reading/encoding image file {figure_path} for figure "
                              f"'{figure_caption}': {e}", exc_info=True)
                return f'\n\n*📊 Error displaying figure: {figure_caption} ' \
                       f'(File I/O or encoding error)*\n\n'

        response_content = figure_path_pattern.sub(embed_figure_in_markdown, response_content)

        code_examples = []
        code_pattern = re.compile(r'\[CODE(?::\s*(.*?))?\]')
        
        def replace_code(match):
            raw_llm_desc = match.group(1)
            logging.info(f"ExplainerAgent: Processing code placeholder: '{match.group(0)}', "
                         f"raw LLM description: '{raw_llm_desc}'")
            
            actual_display_desc: str
            desc_for_generator: str

            forbidden_descs = ["code", "code example", "code snippet", "sample", "example", 
                               "[error: missing or generic code description from llm]"]

            is_generic_desc = not raw_llm_desc or raw_llm_desc.strip().lower() in forbidden_descs
            
            if is_generic_desc:
                actual_display_desc = f"Python code illustrating '{title}'"
                desc_for_generator = (
                    f"Context: '{title}'. Task: Generate a runnable, self-contained Python code example. "
                    f"The LLM provided a generic description: '{raw_llm_desc}'. Your final line of code MUST be a print() statement."
                )
                logging.warning(f"ExplainerAgent: LLM provided generic or no code description: "
                                f"'{raw_llm_desc}'. Using fallback title.")
            else:
                actual_display_desc = raw_llm_desc.strip()
                desc_for_generator = (
                    f"Generate a runnable, self-contained Python code snippet for: '{raw_llm_desc}'. "
                    f"It must include all necessary imports and initialize all variables. "
                    f"Your final line of code MUST be a print() statement to display the result."
                )
            
            code_snippet = make_code_snippet(
                title,
                content,
                desc_for_generator,
                llm_provider=self.provider,
                llm_model_name=self.model_name,
                llm_api_key=self.api_key
            )
            
            if code_snippet:
                # 1. Create the CodeExample object
                new_code_example = CodeExample(language="python", code=code_snippet,
                                               description=actual_display_desc)
                # 2. Add it to the list that app.py will use
                code_examples.append(new_code_example)
                
                # 3. Get the index of the newly added item
                insertion_index = len(code_examples) - 1
                
                # 4. Create the EXACT placeholder your app.py expects
                placeholder = f"[CODE_INSERTION_POINT_{insertion_index}]"

                logging.info(f"ExplainerAgent: Generated code for '{actual_display_desc}', "
                             f"returning placeholder: '{placeholder}'")
                return placeholder
            else:
                logging.warning(f"ExplainerAgent: make_code_snippet returned empty for description: "
                                f"'{desc_for_generator}'. Removing placeholder from markdown.")
                return ''
        
        response_content = code_pattern.sub(replace_code, response_content)

        return ExplanationResponse(
            markdown=response_content.strip(),
            visual_aids=visual_aids,
            code_examples=code_examples
        )
