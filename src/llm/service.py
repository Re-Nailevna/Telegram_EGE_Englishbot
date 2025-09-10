"""
Сервис для работы с Yandex GPT API.
"""

import logging
import asyncio
from typing import Optional
from openai import AsyncOpenAI, APITimeoutError, APIError

logger = logging.getLogger(__name__)

class LLMService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Инициализация клиента Yandex GPT"""
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        self.ya_api_key = os.getenv("YA_API_KEY")
        self.ya_folder_id = os.getenv("YA_FOLDER_ID")
        
        if not self.ya_api_key or not self.ya_folder_id:
            raise ValueError("Yandex API credentials not found in .env")
        
        try:
            self.client = AsyncOpenAI(
                api_key=self.ya_api_key,
                base_url="https://llm.api.cloud.yandex.net/v1",
                timeout=30
            )
            self.model = f"gpt://{self.ya_folder_id}/yandexgpt-lite"
            self._prompts_cache = self._load_prompts()
            logger.info("LLMService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService: {e}")
            raise
    
    def _load_prompts(self) -> dict:
        """Загружает промпты из файлов"""
        import os
        from pathlib import Path
        
        prompts = {}
        prompts_dir = Path("src/llm/prompts")
        
        try:
            for prompt_file in prompts_dir.glob("*.txt"):
                try:
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        prompts[prompt_file.stem] = f.read().strip()
                    logger.debug(f"Loaded prompt: {prompt_file.stem}")
                except Exception as e:
                    logger.warning(f"Failed to load prompt {prompt_file}: {e}")
                    prompts[prompt_file.stem] = f"Default prompt for {prompt_file.stem}"
        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")
            prompts = {"default": "You are a helpful assistant."}
        
        return prompts
    
    async def generate_content(
        self,
        prompt_type: str = "tutor",
        user_message: str = "",
        additional_context: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Генерация контента через Yandex GPT"""
        
        system_prompt = self._prompts_cache.get(prompt_type, self._prompts_cache.get("tutor", "You are a helpful assistant."))
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if additional_context:
            messages.append({"role": "system", "content": additional_context})
        
        if user_message:
            messages.append({"role": "user", "content": user_message})
        else:
            messages.append({"role": "user", "content": "Please generate content"})
        
        try:
            logger.debug(f"Generating content with prompt type: {prompt_type}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            result = response.choices[0].message.content
            logger.debug(f"Generated content length: {len(result)}")
            return result
            
        except APITimeoutError:
            logger.warning("Yandex GPT API timeout")
            return "⏰ Сервис временно недоступен. Попробуйте позже."
        except APIError as e:
            logger.error(f"Yandex GPT API error: {e}")
            return "❌ Ошибка сервиса AI. Попробуйте позже."
        except Exception as e:
            logger.error(f"Unexpected error in generate_content: {e}")
            return "❌ Произошла непредвиденная ошибка."

# Глобальный экземпляр сервиса
llm_service = LLMService()