import httpx
import json
from typing import List, Dict, Optional, Tuple
from backend.config import settings
from backend.models.schemas import DialogType, Difficulty, LangLevel


class LLMService:

    @staticmethod
    def _build_system_prompt(scenario, user_level: LangLevel, dialog_type: DialogType,
                             difficulty: Difficulty, target_language: str) -> str:

        level_instructions = {
            "A1": "very basic vocabulary, simple present tense, short sentences",
            "A2": "basic vocabulary, simple past/future, everyday topics",
            "B1": "intermediate vocabulary, various tenses, can express opinions",
            "B2": "good vocabulary range, complex sentences, abstract topics",
            "C1": "wide vocabulary, sophisticated language, nuanced expression",
            "C2": "extensive vocabulary, very sophisticated language, cultural references"
        }

        language_instruction = f"Respond only in {target_language}. " if target_language == "en" else "Отвечай только на русском языке. "
        level_desc = level_instructions.get(user_level, level_instructions["B1"])

        prompt = f"""{language_instruction}You are {scenario['character_name']}, {scenario['character_role']}.

Character traits: {scenario['character_traits']}

Language level: Adapt your language to {user_level} level - use {level_desc}.
"""

        if dialog_type == DialogType.MISSION:
            prompt += f"\nMission goal: {scenario['goal']}\nThe user will try to achieve this goal. Be challenging but fair."
        else:
            prompt += "\nThis is a casual conversation. Keep the dialogue flowing naturally."

        if difficulty == Difficulty.RELAX:
            prompt += "\nIf the user makes language mistakes, gently correct them in your response."
        else:
            prompt += "\nDo not correct language mistakes during the conversation."

        return prompt

    @staticmethod
    async def get_character_response(scenario: Dict, messages: List[Dict],
                                     user_level: LangLevel, dialog_type: DialogType,
                                     difficulty: Difficulty, target_language: str) -> Tuple[str, Optional[str]]:

        system_prompt = LLMService._build_system_prompt(
            scenario, user_level, dialog_type, difficulty, target_language
        )

        # Формируем историю сообщений для LLM
        llm_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            llm_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.openai_model,
                    "messages": llm_messages,
                    "temperature": 0.8,
                    "max_tokens": 300
                },
                timeout=30.0
            )
            response.raise_for_status()

            result = response.json()
            character_response = result["choices"][0]["message"]["content"]

            # Генерируем подсказку для Relax режима
            hint = None
            if difficulty == Difficulty.RELAX and len(messages) > 0:
                last_user_message = next((m for m in reversed(messages) if m["role"] == "user"), None)
                if last_user_message:
                    hint = await LLMService._generate_hint(last_user_message["content"], target_language)

            return character_response, hint

    @staticmethod
    async def _generate_hint(user_message: str, target_language: str) -> Optional[str]:
        hint_prompt = f"""Analyze this message for language learning: "{user_message}"
Give a brief helpful tip in {target_language} (grammar, vocabulary, or expression). Keep it under 50 words."""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.openai_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.openai_model,
                        "messages": [{"role": "user", "content": hint_prompt}],
                        "temperature": 0.3,
                        "max_tokens": 100
                    },
                    timeout=15.0
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except:
            return None

    @staticmethod
    async def evaluate_mission(messages: List[Dict], goal: str, target_language: str) -> Tuple[str, str]:
        """Оценивает выполнение миссии и анализирует ошибки"""

        conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

        eval_prompt = f"""Analyze this conversation where the user tried to achieve: "{goal}"

Conversation:
{conversation}

Provide:
1. SUCCESS or FAIL - did they achieve the goal?
2. Brief feedback on goal achievement ({target_language})
3. Language errors analysis ({target_language})

Format: SUCCESS/FAIL|Goal feedback|Errors analysis"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.openai_model,
                    "messages": [{"role": "user", "content": eval_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 400
                },
                timeout=30.0
            )
            response.raise_for_status()

            result = response.json()
            evaluation = result["choices"][0]["message"]["content"]

            parts = evaluation.split("|")
            if len(parts) >= 3:
                success = "success" if "SUCCESS" in parts[0] else "fail"
                goal_feedback = parts[1].strip()
                errors_summary = parts[2].strip()
                return success, goal_feedback, errors_summary

            return "fail", "Не удалось оценить результат", "Анализ недоступен"
