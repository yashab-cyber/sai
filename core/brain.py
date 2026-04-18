import json
import logging
import os
import requests
import base64
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

class Brain:
    """
    Core Intelligence Layer (LLM Interface).
    Supports multiple providers: OpenAI, Google Gemini, Anthropic, Ollama.
    """
    
    def __init__(self, provider: Optional[str] = None):
        # Load environment variables from .env
        load_dotenv()
        
        self.provider = provider or os.getenv("SAI_PROVIDER", "mock").lower()
        self.model = os.getenv("MODEL_NAME", "gpt-4-turbo")
        self.logger = logging.getLogger("SAI.Brain")
        
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        self.logger.info(f"Brain initialized with provider: {self.provider}")

    def prompt(self, system_prompt: str, user_query: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """Routes the query to the correct LLM provider, supporting optional visual input."""
        try:
            if self.provider == "openai":
                return self._call_openai(system_prompt, user_query, image_path)
            elif self.provider == "gemini":
                return self._call_gemini(system_prompt, user_query, image_path)
            elif self.provider == "ollama":
                return self._call_ollama(system_prompt, user_query) # Ollama vision support pending
            else:
                return self._mock_response(user_query)
        except Exception as e:
            self.logger.error(f"LLM call failed: {str(e)}")
            return self._mock_response(user_query)

    def _encode_image(self, image_path: str) -> str:
        """Encodes an image to a base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _call_openai(self, system_prompt: str, user_query: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """Implementation for OpenAI API with Vision support."""
        if not self.openai_key:
            raise ValueError("OpenAI API key missing.")
            
        import openai
        import time as _time
        client = openai.OpenAI(
            api_key=self.openai_key,
            base_url=self.openai_base_url
        )
        
        content = [{"type": "text", "text": user_query}]
        if image_path and os.path.exists(image_path):
            base64_image = self._encode_image(image_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
            })

        messages = [
            {"role": "system", "content": f"{system_prompt}. Respond ONLY in valid JSON."},
            {"role": "user", "content": content}
        ]

        # Retry once on empty/null response (transient proxy issue)
        for attempt in range(2):
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            if raw_content and raw_content.strip():
                return json.loads(raw_content)

            self.logger.warning(
                "LLM returned empty content (attempt %d/2). Retrying...", attempt + 1
            )
            if attempt < 1:
                _time.sleep(1.0)

        raise ValueError("LLM returned empty response after 2 attempts.")

    def _call_gemini(self, system_prompt: str, user_query: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """Implementation for Google Gemini API with Multimodal support."""
        if not self.gemini_key:
            raise ValueError("Gemini API key missing.")
            
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel(self.model)
        
        prompt_parts = [f"{system_prompt}\n\nTask: {user_query}\n\nRespond ONLY as a JSON object."]
        
        if image_path and os.path.exists(image_path):
            from PIL import Image
            img = Image.open(image_path)
            prompt_parts.append(img)

        response = model.generate_content(prompt_parts)
        
        # Extract JSON from response text
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif text.startswith("```"): # Handle cases where it's just triple backticks without 'json'
             text = text.strip("`").strip()
        return json.loads(text)

    def _call_ollama(self, system_prompt: str, user_query: str) -> Dict[str, Any]:
        """Implementation for local Ollama API."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            "format": "json",
            "stream": False
        }
        response = requests.post(f"{self.ollama_url}/api/chat", json=payload)
        response.raise_for_status()
        return json.loads(response.json()["message"]["content"])

    def _mock_response(self, query: str) -> Dict[str, Any]:
        """Fallback mock response — JARVIS style."""
        return {
            "thought": f"Running in demonstration mode, sir. The directive '{query}' would normally be handled by the {self.provider} neural engine. Shall I attempt an alternative approach?",
            "plan": ["Reconnaissance", "Strategic execution", "Verification and debrief"],
            "tool": "executor.shell",
            "parameters": {"command": "echo 'S.A.I. standing by in demonstration mode, sir.'"}
        }

    def generate_plan(self, task: str) -> List[str]:
        response = self.prompt(
            "You are S.A.I., an autonomous AI assistant modeled after J.A.R.V.I.S. "
            "Plan tasks with tactical precision and elegant efficiency, sir.",
            task
        )
        return response.get("plan", ["Research", "Execute", "Verify"])
        
    def get_embedding(self, text: str) -> List[float]:
        """Generates a high-dimensional vector representation of text for semantic memory."""
        try:
            if self.provider == "openai":
                # Check for local copilot-api proxy to prevent 400 Bad Request on embeddings
                if self.openai_base_url and ("localhost" in self.openai_base_url or "127.0.0.1" in self.openai_base_url):
                    self.logger.debug("Local OpenAI proxy detected. Bypassing API embeddings to use ChromaDB native ONNX models.")
                    return []
                    
                if not self.openai_key:
                    raise ValueError("OpenAI API key missing.")
                import openai
                client = openai.OpenAI(api_key=self.openai_key, base_url=self.openai_base_url)
                resp = client.embeddings.create(input=text, model="text-embedding-3-small")
                return resp.data[0].embedding
                
            elif self.provider == "gemini":
                if not self.gemini_key:
                    raise ValueError("Gemini API key missing.")
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                    task_type="retrieval_document"
                )
                return result['embedding']
                
            elif self.provider == "ollama":
                payload = {
                    "model": self.model,
                    "prompt": text
                }
                resp = requests.post(f"{self.ollama_url}/api/embeddings", json=payload)
                resp.raise_for_status()
                return resp.json()["embedding"]
                
            else:
                import random
                import hashlib
                seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
                random.seed(seed)
                # Mock embedding (1536 dims to match standard embeddings)
                return [random.uniform(-1.0, 1.0) for _ in range(1536)]
                
        except Exception as e:
            self.logger.error(f"Embedding generation failed: {str(e)}")
            return []
