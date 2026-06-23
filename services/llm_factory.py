from __future__ import annotations

import os
from typing import Callable, List, Dict, Any, Optional
from dotenv import load_dotenv
import litellm

load_dotenv()

_PROVIDER_MAP = {
    "openai": {
        "default_model": "gpt-4o",
        "model_prefix": "openai/",
        "api_key": os.getenv("OPENAI_API_KEY"),
    },
    "mistral": {
        "default_model": "mistral-small-2503",
        "model_prefix": "mistral/",
        "api_key": os.getenv("MISTRAL_API_KEY"),
    },
    "gemini": {
        "default_model": "gemini-2.0-flash",
        "model_prefix": "gemini/",
        "api_key": os.getenv("GOOGLE_API_KEY"),
    },
    "custom": {
        "default_model": "deepseek-v4-flash",
        "model_prefix": "openai/",
        "api_key": os.getenv("CUSTOM_API_KEY"),
        "api_base": os.getenv("CUSTOM_API_BASE"),
    },
}


def get_default_model(provider: str) -> str:
    """Get the default model name for a provider."""
    return _PROVIDER_MAP.get(provider, {}).get("default_model", "gpt-3.5-turbo")


def get_completion_fn(provider: str, model_name: str = None, api_key: str = None) -> Callable[[str], str]:
    """Get completion function with optional custom model and API key."""
    cfg = _PROVIDER_MAP.get(provider, _PROVIDER_MAP["custom"])
    
    # Use provided model name or default
    if not model_name or model_name.strip() == "":
        model_name = cfg["default_model"]
    
    # Use provided API key or default from .env
    if not api_key or api_key.strip() == "":
        api_key = cfg["api_key"]
    
    # Construct full model name with prefix
    full_model = f"{cfg['model_prefix']}{model_name}"

    def _call(
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        
        # Add tool-related parameters if provided
        extra_params = {}
        if tools:
            extra_params["tools"] = tools
        if tool_choice:
            extra_params["tool_choice"] = tool_choice

        resp = litellm.completion(
            model=full_model,
            messages=messages,
            api_key=api_key,
            api_base=cfg.get("api_base"),
            **extra_params
        )
        
        # Handle tool calls
        if resp.choices[0].message.tool_calls:
            tool_calls = resp.choices[0].message.tool_calls
            return tool_calls[0].json() 
        
        return resp["choices"][0]["message"]["content"].strip()

    return _call
