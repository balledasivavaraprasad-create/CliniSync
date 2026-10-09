from typing import Dict, List
from app.config import settings


def get_model_list() -> List[Dict]:
    """
    Returns the model list for LiteLLM Router configuration.
    Formats keys and model identifiers from environment variables.
    """
    models = []

    # 1. LLM Generation models
    models.append({
        "model_name": "llm_generate",
        "litellm_params": {
            "model": settings.LLM_PRIMARY,
            "api_key": settings.GEMINI_API_KEY if "gemini" in settings.LLM_PRIMARY else settings.GROQ_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
        },
    })
    models.append({
        "model_name": "llm_generate",
        "litellm_params": {
            "model": settings.LLM_SECONDARY,
            "api_key": settings.GEMINI_API_KEY if "gemini" in settings.LLM_SECONDARY else settings.GROQ_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
        },
    })
    models.append({
        "model_name": "llm_generate",
        "litellm_params": {
            "model": settings.LLM_FALLBACK_1,
            "api_key": settings.GROQ_API_KEY if "groq" in settings.LLM_FALLBACK_1 else settings.GEMINI_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
        },
    })
    models.append({
        "model_name": "llm_generate",
        "litellm_params": {
            "model": settings.LLM_FALLBACK_2,
            "api_key": settings.GROQ_API_KEY if "groq" in settings.LLM_FALLBACK_2 else settings.GEMINI_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
        },
    })

    # 2. LLM Extraction models (temperature 0)
    models.append({
        "model_name": "llm_extract",
        "litellm_params": {
            "model": settings.LLM_PRIMARY,
            "api_key": settings.GEMINI_API_KEY if "gemini" in settings.LLM_PRIMARY else settings.GROQ_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
            "temperature": 0.0,
        },
    })
    models.append({
        "model_name": "llm_extract",
        "litellm_params": {
            "model": settings.LLM_FALLBACK_1,
            "api_key": settings.GROQ_API_KEY if "groq" in settings.LLM_FALLBACK_1 else settings.GEMINI_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
            "temperature": 0.0,
        },
    })

    # 3. LLM Judge models (Groq primary, Gemini fallback)
    models.append({
        "model_name": "llm_judge",
        "litellm_params": {
            "model": settings.LLM_JUDGE_PRIMARY,
            "api_key": settings.GROQ_API_KEY if "groq" in settings.LLM_JUDGE_PRIMARY else settings.GEMINI_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
            "temperature": 0.0,
        },
    })
    models.append({
        "model_name": "llm_judge",
        "litellm_params": {
            "model": settings.LLM_JUDGE_FALLBACK,
            "api_key": settings.GEMINI_API_KEY if "gemini" in settings.LLM_JUDGE_FALLBACK else settings.GROQ_API_KEY,
            "timeout": settings.LLM_TIMEOUT_S,
            "temperature": 0.0,
        },
    })

    return models
