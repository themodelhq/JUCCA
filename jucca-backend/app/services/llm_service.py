"""
GPT4All LLM Service for JUCCA

This module provides LLM capabilities using GPT4All with:
- Local model inference (offline-capable)
- Response caching for performance
- Streaming responses
- Fallback to cloud API when overloaded
- Model management and fallback hierarchy
"""

import os
import hashlib
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Generator, AsyncGenerator
from functools import lru_cache

# GPT4All imports
try:
    from gpt4all import GPT4All as GPT4AllClient
    GPT4ALL_AVAILABLE = True
except ImportError:
    GPT4ALL_AVAILABLE = False
    logging.warning("GPT4All not installed. Install with: pip install gpt4all")

# OpenAI imports for fallback
try:
    from openai import OpenAI as OpenAIClient
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Language detection
try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    logging.warning("langdetect not installed. Language detection disabled.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================
# Configuration
# ========================

class LLMConfig:
    """LLM configuration management."""
    
    # Model settings
    MODEL_NAME = os.getenv("GPT4ALL_MODEL", "mistral-7b-openorca.Q8_0.gguf")
    MODEL_PATH = os.getenv("GPT4ALL_MODEL_PATH", "./models")
    
    # Fallback hierarchy
    FALLBACK_MODELS = [
        "mistral-7b-openorca.Q8_0.gguf",
        "mistral-7b-openorca.gguf",
        "nous-hermes-llama2.gguf",
        "orca-mini-3b.gguf"
    ]
    
    # Cloud fallback
    USE_CLOUD_FALLBACK = os.getenv("USE_CLOUD_FALLBACK", "true").lower() == "true"
    CLOUD_API_KEY = os.getenv("OPENAI_API_KEY", "")
    CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gpt-3.5-turbo")
    
    # Performance settings
    CACHE_ENABLED = os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL_MINUTES = int(os.getenv("LLM_CACHE_TTL", "60"))
    STREAMING_ENABLED = os.getenv("STREAMING_ENABLED", "true").lower() == "true"
    
    # Load shedding settings
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
    REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
    OVERLOAD_THRESHOLD = int(os.getenv("OVERLOAD_THRESHOLD", "80"))
    
    # Model inference settings
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "300"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    TOP_P = float(os.getenv("TOP_P", "0.9"))
    N_BATCH = int(os.getenv("N_BATCH", "2048"))


# ========================
# Response Cache
# ========================

class ResponseCache:
    """LRU cache for LLM responses with TTL support."""
    
    def __init__(self, max_size: int = 1000, ttl_minutes: int = 60):
        self.cache = {}
        self.max_size = max_size
        self.ttl = timedelta(minutes=ttl_minutes)
        self.access_times = {}
    
    def _generate_key(self, question: str, decision: str, reason: str, 
                      role: str, detected_entities: Optional[dict] = None) -> str:
        """Generate a unique cache key from request parameters."""
        # Normalize inputs
        key_parts = {
            "question": question.strip().lower(),
            "decision": decision,
            "reason": reason,
            "role": role,
            "entities": detected_entities or {}
        }
        key_string = json.dumps(key_parts, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, question: str, decision: str, reason: str, 
            role: str, detected_entities: Optional[dict] = None) -> Optional[str]:
        """Retrieve cached response if valid."""
        key = self._generate_key(question, decision, reason, role, detected_entities)
        
        if key in self.cache:
            access_time = self.access_times.get(key)
            if access_time and datetime.now() - access_time < self.ttl:
                logger.debug(f"Cache hit for key: {key}")
                return self.cache[key]
            else:
                # Expired entry
                del self.cache[key]
                del self.access_times[key]
        
        return None
    
    def set(self, question: str, decision: str, reason: str,
            role: str, response: str, detected_entities: Optional[dict] = None):
        """Store response in cache with TTL."""
        key = self._generate_key(question, decision, reason, role, detected_entities)
        
        # Evict oldest entries if cache is full
        while len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times.keys(), 
                           key=lambda k: self.access_times.get(k, datetime.min))
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        self.cache[key] = response
        self.access_times[key] = datetime.now()
        logger.debug(f"Cached response for key: {key}")
    
    def clear(self):
        """Clear all cached responses."""
        self.cache.clear()
        self.access_times.clear()
        logger.info("Cache cleared")
    
    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_minutes": self.ttl.total_seconds() / 60
        }


# Global cache instance
response_cache = ResponseCache(
    max_size=1000,
    ttl_minutes=LLMConfig.CACHE_TTL_MINUTES
)


# ========================
# Load Manager
# ========================

class LoadManager:
    """Manages system load and implements load shedding."""
    
    _instance = None
    active_requests = 0
    total_requests = 0
    failed_requests = 0
    total_latency = 0.0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def start_request(self) -> bool:
        """Start tracking a new request. Returns False if overloaded."""
        if self.active_requests >= LLMConfig.MAX_CONCURRENT_REQUESTS:
            logger.warning("Load shedding: too many concurrent requests")
            return False
        self.active_requests += 1
        self.total_requests += 1
        return True
    
    def end_request(self, latency: float, success: bool = True):
        """End tracking a request."""
        self.active_requests = max(0, self.active_requests - 1)
        self.total_latency += latency
        if not success:
            self.failed_requests += 1
    
    def get_stats(self) -> dict:
        """Get load statistics."""
        avg_latency = self.total_latency / self.total_requests if self.total_requests > 0 else 0
        success_rate = (1 - self.failed_requests / self.total_requests * 100) if self.total_requests > 0 else 100
        return {
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "avg_latency_ms": avg_latency * 1000,
            "success_rate": f"{success_rate:.1f}%",
            "capacity_used": f"{(self.active_requests / LLMConfig.MAX_CONCURRENT_REQUESTS) * 100:.1f}%"
        }
    
    def should_use_cloud(self) -> bool:
        """Determine if cloud fallback should be used."""
        # Use cloud if local model is overloaded
        if self.active_requests >= LLMConfig.MAX_CONCURRENT_REQUESTS * 0.8:
            return True
        # Check system load
        try:
            import psutil
            load = psutil.cpu_percent()
            if load > LLMConfig.OVERLOAD_THRESHOLD:
                return True
        except ImportError:
            pass
        return False


# Global load manager
load_manager = LoadManager()


# ========================
# GPT4All Model Manager
# ========================

class GPT4AllManager:
    """Manages GPT4All model lifecycle and inference."""
    
    _instance = None
    model = None
    model_name = None
    last_used = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self.model is None:
            self._load_model()
    
    def _load_model(self, model_name: str = None):
        """Load GPT4All model with fallback support."""
        if not GPT4ALL_AVAILABLE:
            logger.warning("GPT4All not available")
            return False
        
        # Determine which models to try
        if model_name:
            models_to_try = [model_name] + LLMConfig.FALLBACK_MODELS
        else:
            models_to_try = [LLMConfig.MODEL_NAME] + LLMConfig.FALLBACK_MODELS
        
        # Remove duplicates while preserving order
        seen = set()
        unique_models = []
        for m in models_to_try:
            if m not in seen:
                seen.add(m)
                unique_models.append(m)
        
        # Try each model until one succeeds
        for target_model in unique_models:
            try:
                logger.info(f"Attempting to load GPT4All model: {target_model}")
                self.model = GPT4AllClient(
                    model_name=target_model,
                    model_path=LLMConfig.MODEL_PATH,
                    allow_download=True,
                    n_threads=-1  # Use all available threads
                )
                self.model_name = target_model
                logger.info(f"Model {target_model} loaded successfully")
                return True
            except Exception as e:
                logger.warning(f"Failed to load model {target_model}: {e}")
                continue
        
        # All models failed
        logger.error("Failed to load any GPT4All model")
        return False
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using GPT4All."""
        if self.model is None:
            if not self._load_model():
                raise RuntimeError("GPT4All model not loaded")
        
        start_time = time.time()
        
        try:
            # Apply inference parameters
            params = {
                "max_tokens": kwargs.get("max_tokens", LLMConfig.MAX_TOKENS),
                "temp": kwargs.get("temperature", LLMConfig.TEMPERATURE),
                "top_p": kwargs.get("top_p", LLMConfig.TOP_P),
                "n_batch": kwargs.get("n_batch", LLMConfig.N_BATCH),
                "repeat_penalty": kwargs.get("repeat_penalty", 1.1),
                "repeat_last_n": kwargs.get("repeat_last_n", 64),
            }
            
            with self.model.chat_session():
                response = self.model.generate(prompt, **params)
            
            latency = time.time() - start_time
            logger.info(f"GPT4All inference completed in {latency:.2f}s")
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"GPT4All inference error: {e}")
            raise
    
    def generate_streaming(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """Generate streaming response using GPT4All."""
        if self.model is None:
            if not self._load_model():
                raise RuntimeError("GPT4All model not loaded")
        
        try:
            params = {
                "max_tokens": kwargs.get("max_tokens", LLMConfig.MAX_TOKENS),
                "temp": kwargs.get("temperature", LLMConfig.TEMPERATURE),
                "top_p": kwargs.get("top_p", LLMConfig.TOP_P),
                "n_batch": kwargs.get("n_batch", LLMConfig.N_BATCH),
            }
            
            # GPT4All doesn't natively support streaming in the same way as OpenAI
            # So we generate and yield chunks manually
            full_response = self.model.generate(prompt, **params)
            
            # Simulate streaming by yielding chunks
            chunk_size = max(1, len(full_response) // 10)
            for i in range(0, len(full_response), chunk_size):
                yield full_response[i:i + chunk_size]
                
        except Exception as e:
            logger.error(f"GPT4All streaming error: {e}")
            raise
    
    def is_healthy(self) -> bool:
        """Check if model is loaded and healthy."""
        return self.model is not None
    
    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            "model_name": self.model_name,
            "loaded": self.model is not None,
            "path": LLMConfig.MODEL_PATH
        }


# Global model manager
gpt4all_manager = GPT4AllManager()


# ========================
# Cloud Fallback (OpenAI)
# ========================

class CloudLLMClient:
    """OpenAI client for cloud fallback."""
    
    _instance = None
    client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._client = None
        return cls._instance
    
    @property
    def client(self):
        if self._client is None and OPENAI_AVAILABLE and LLMConfig.CLOUD_API_KEY:
            self._client = OpenAIClient(api_key=LLMConfig.CLOUD_API_KEY)
        return self._client
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI."""
        if not self.client:
            raise RuntimeError("Cloud client not available")
        
        try:
            response = self.client.chat.completions.create(
                model=LLMConfig.CLOUD_MODEL,
                messages=[{"role": "system", content: prompt}],
                max_tokens=kwargs.get("max_tokens", LLMConfig.MAX_TOKENS),
                temperature=kwargs.get("temperature", LLMConfig.TEMPERATURE),
                stream=False
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Cloud API error: {e}")
            raise
    
    def generate_streaming(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """Generate streaming response using OpenAI."""
        if not self.client:
            raise RuntimeError("Cloud client not available")
        
        response = self.client.chat.completions.create(
            model=LLMConfig.CLOUD_MODEL,
            messages=[{"role": "system", content: prompt}],
            max_tokens=kwargs.get("max_tokens", LLMConfig.MAX_TOKENS),
            temperature=kwargs.get("temperature", LLMConfig.TEMPERATURE),
            stream=True
        )
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def is_available(self) -> bool:
        """Check if cloud client is available."""
        return self.client is not None


# Global cloud client
cloud_client = CloudLLMClient()


# ========================
# Language Detection
# ========================

SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "French",
    "ar": "Arabic"
}

def detect_language(text: str) -> str:
    """Detect the language of the input text."""
    if not LANGDETECT_AVAILABLE:
        return "en"
    
    try:
        lang = detect(text)
        return lang if lang in SUPPORTED_LANGUAGES else "en"
    except LangDetectException:
        return "en"


# ========================
# Response Tone
# ========================

def get_response_tone(role: str = "seller") -> str:
    """Get the appropriate response tone based on user role."""
    tones = {
        "seller": (
            "Use friendly, supportive, and encouraging language. "
            "Be helpful and clear. Avoid legal threats or overly technical jargon. "
            "Make the seller feel supported."
        ),
        "admin": (
            "Use professional, factual language. "
            "Be direct and comprehensive."
        ),
        "legal": (
            "Use strict, precise legal and policy language. "
            "Reference specific policies where applicable."
        )
    }
    return tones.get(role, tones["seller"])


# ========================
# Prompt Builder
# ========================

def build_prompt(question: str, decision: str, reason: str,
                role: str, detected_entities: Optional[dict] = None) -> str:
    """Build the LLM prompt from request parameters."""
    tone_instruction = get_response_tone(role)
    
    entity_context = ""
    if detected_entities:
        if detected_entities.get("brand"):
            entity_context += f" Brand detected: {detected_entities['brand']}."
        if detected_entities.get("category"):
            entity_context += f" Category detected: {detected_entities['category']}."
        if detected_entities.get("country"):
            entity_context += f" Country: {detected_entities['country']}."
    
    prompt = f"""You are JUCCA, a helpful compliance assistant for marketplace sellers.
{tone_instruction}

The user asked: "{question}"
{entity_context}

Compliance Decision: {decision}
Policy Reason: {reason}

Provide a clear, helpful response that:
1. Clearly states whether the product can be listed or not
2. Explains the policy reason in simple terms
3. If restricted, explains what would be needed to comply
4. Offers helpful next steps if applicable

Keep your response concise but complete. Do not invent policies or rules."""
    
    return prompt


# ========================
# Main LLM Service
# ========================

class LLMService:
    """Main LLM service with caching, fallback, and streaming support."""
    
    def __init__(self):
        self.cache = response_cache
        self.load_manager = load_manager
    
    def _try_local_model(self, prompt: str, **kwargs) -> Optional[str]:
        """Try to generate response using local GPT4All model."""
        try:
            if gpt4all_manager.is_healthy():
                return gpt4all_manager.generate(prompt, **kwargs)
        except Exception as e:
            logger.error(f"Local model failed: {e}")
        return None
    
    def _try_cloud_fallback(self, prompt: str, **kwargs) -> Optional[str]:
        """Try cloud API as fallback."""
        if not LLMConfig.USE_CLOUD_FALLBACK:
            return None
        
        try:
            if cloud_client.is_available():
                return cloud_client.generate(prompt, **kwargs)
        except Exception as e:
            logger.error(f"Cloud fallback failed: {e}")
        return None
    
    def _generate_with_fallback(self, prompt: str, **kwargs) -> str:
        """Generate response with fallback hierarchy."""
        # Try local model first
        result = self._try_local_model(prompt, **kwargs)
        if result:
            return result
        
        # Try cloud fallback
        result = self._try_cloud_fallback(prompt, **kwargs)
        if result:
            return result
        
        # All models failed, use template
        raise RuntimeError("All LLM providers failed")
    
    def generate(self, question: str, decision: str, reason: str,
                role: str = "seller", detected_entities: Optional[dict] = None) -> str:
        """Generate LLM response with caching and fallback."""
        start_time = time.time()
        
        # Check cache first
        if LLMConfig.CACHE_ENABLED:
            cached = self.cache.get(question, decision, reason, role, detected_entities)
            if cached:
                logger.debug("Returning cached response")
                return cached
        
        # Check if overloaded, use cloud directly
        use_cloud = self.load_manager.should_use_cloud()
        
        if use_cloud:
            # Use cloud directly when overloaded
            prompt = build_prompt(question, decision, reason, role, detected_entities)
            response = self._try_cloud_fallback(prompt)
            if response:
                if LLMConfig.CACHE_ENABLED:
                    self.cache.set(question, decision, reason, role, response, detected_entities)
                return response
        
        # Generate response
        prompt = build_prompt(question, decision, reason, role, detected_entities)
        
        try:
            response = self._generate_with_fallback(prompt)
        except RuntimeError:
            # Fall back to template response
            response = generate_template_response(question, decision, reason, role, detected_entities)
        
        # Cache the response
        if LLMConfig.CACHE_ENABLED:
            self.cache.set(question, decision, reason, role, response, detected_entities)
        
        latency = time.time() - start_time
        load_manager.end_request(latency, success=True)
        
        return response
    
    def generate_streaming(self, question: str, decision: str, reason: str,
                          role: str = "seller", 
                          detected_entities: Optional[dict] = None) -> AsyncGenerator[str, None]:
        """Generate streaming LLM response."""
        prompt = build_prompt(question, decision, reason, role, detected_entities)
        
        # Try local model first
        if gpt4all_manager.is_healthy():
            try:
                for chunk in gpt4all_manager.generate_streaming(prompt):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"Local streaming failed: {e}")
        
        # Try cloud fallback
        if cloud_client.is_available():
            try:
                for chunk in cloud_client.generate_streaming(prompt):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"Cloud streaming failed: {e}")
        
        # Fallback to non-streaming
        response = self.generate(question, decision, reason, role, detected_entities)
        yield response
    
    def get_status(self) -> dict:
        """Get service status and statistics."""
        return {
            "cache": self.cache.stats(),
            "load": self.load_manager.get_stats(),
            "model": gpt4all_manager.get_model_info(),
            "cloud_available": cloud_client.is_available(),
            "config": {
                "cache_enabled": LLMConfig.CACHE_ENABLED,
                "streaming_enabled": LLMConfig.STREAMING_ENABLED,
                "cloud_fallback": LLMConfig.USE_CLOUD_FALLBACK
            }
        }
    
    def clear_cache(self):
        """Clear the response cache."""
        self.cache.clear()


# Global service instance
llm_service = LLMService()


# ========================
# Template Response Generator
# ========================

def generate_template_response(question: str, decision: str, reason: str,
                             role: str = "seller", 
                             detected_entities: Optional[dict] = None) -> str:
    """Generate template-based responses when LLM is unavailable."""
    brand = detected_entities.get("brand", "") if detected_entities else ""
    category = detected_entities.get("category", "") if detected_entities else ""
    country = detected_entities.get("country", "") if detected_entities else ""
    
    if decision == "Allowed":
        responses = [
            f"Great news! You can list this item. {reason}",
            f"This appears to be allowed. {reason}",
            f"Good news - no policy issues found. {reason}"
        ]
    elif decision == "Restricted":
        responses = [
            f"This item has some restrictions. {reason}",
            f"You may need special authorization for this. {reason}",
            f"Before listing, please check the requirements: {reason}"
        ]
    elif decision == "Prohibited":
        responses = [
            f"Unfortunately, this item cannot be listed. {reason}",
            f"This product is prohibited on our marketplace. {reason}",
            f"I'm sorry, but {reason}"
        ]
    else:  # Blocked
        responses = [
            f"This listing is blocked. {reason}",
            f"Unable to approve this listing. {reason}",
            f"This content violates our policies: {reason}"
        ]
    
    import random
    response = random.choice(responses)
    
    # Add entity-specific guidance
    if brand and decision == "Restricted":
        response += f" To sell {brand} products, you would need to become an authorized reseller."
    elif brand and decision == "Blocked":
        response += f" Items related to {brand} cannot be listed due to policy violations."
    
    return response


# ========================
# Convenience Functions
# ========================

def generate_explanation(question: str, decision: str, reason: str,
                        role: str = "seller", 
                        detected_entities: Optional[dict] = None) -> str:
    """Generate a conversational explanation for the compliance decision."""
    if not question:
        return "Please provide a question about product compliance."
    
    return llm_service.generate(
        question=question,
        decision=decision,
        reason=reason,
        role=role,
        detected_entities=detected_entities
    )


def generate_explanation_streaming(question: str, decision: str, reason: str,
                                  role: str = "seller",
                                  detected_entities: Optional[dict] = None):
    """Generate streaming explanation."""
    return llm_service.generate_streaming(
        question=question,
        decision=decision,
        reason=reason,
        role=role,
        detected_entities=detected_entities
    )
