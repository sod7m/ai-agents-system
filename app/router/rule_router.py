from __future__ import annotations

import re

from app.router.intents import IntentResult


class RuleRouter:
    def detect(self, message: str) -> IntentResult:
        text = message.strip()
        lowered = text.lower()

        direct_agent = self._detect_direct_agent(text)
        if direct_agent:
            target_agent, cleaned_message = direct_agent
            return IntentResult(
                name="direct_agent_message",
                confidence=0.95,
                raw_message=message,
                target_agent=target_agent,
                extracted_task=cleaned_message,
                references_active_task=True,
            )

        workspace = self._extract_workspace(text)
        if workspace:
            return IntentResult(
                name="workspace_change",
                confidence=0.9,
                raw_message=message,
                workspace=workspace,
            )

        if self._contains_any(
            lowered,
            ("як там", "що по задачі", "є прогрес", "статус", "на якому етапі", "що вже зроблено"),
        ):
            return IntentResult("status_request", 0.9, message, references_active_task=True)

        if self._contains_any(
            lowered,
            ("покажи зміни", "що змінилось", "diff", "які файли", "що ти змінив"),
        ):
            return IntentResult("show_diff", 0.9, message, references_active_task=True)

        if self._contains_any(
            lowered,
            ("дай посилання", "дай шлях", "де папка", "де файл", "покажи папку", "посилання на цю папку", "папку test"),
        ):
            return IntentResult("path_request", 0.9, message, references_active_task=True)

        if self._contains_any(lowered, ("стоп", "скасуй", "зупини", "не продовжуй")):
            return IntentResult("cancel_task", 0.9, message, references_active_task=True)

        if self._contains_any(
            lowered,
            ("не чіпай", "не змінюй", "тільки не", "без зміни", "не треба чіпати"),
        ):
            return IntentResult(
                name="task_clarification",
                confidence=0.85,
                raw_message=message,
                constraints=(text,),
                references_active_task=True,
            )

        if self._contains_any(
            lowered,
            ("зроби", "створи", "додай", "реалізуй", "перероби", "виправ", "перевір", "знайди помилку", "збілди", "запусти"),
        ):
            return IntentResult(
                name="new_task",
                confidence=0.88,
                raw_message=message,
                extracted_task=text,
            )

        return IntentResult("general_chat", 0.5, message)

    @staticmethod
    def _contains_any(text: str, triggers: tuple[str, ...]) -> bool:
        return any(trigger in text for trigger in triggers)

    @staticmethod
    def _extract_workspace(text: str) -> str | None:
        if not re.search(r"(працюй з|workspace|папка|проєкт|проект|ось шлях)", text, re.IGNORECASE):
            return None

        match = re.search(r"([A-Za-z]:\\[^\n\r]+)", text)
        if match:
            return match.group(1).strip().strip('"')

        return None

    @staticmethod
    def _detect_direct_agent(text: str) -> tuple[str, str] | None:
        patterns = (
            (r"^(pm|project manager|project-manager|пм)\s*[:,\-]\s*(.+)$", "pm"),
            (r"^(coder|кодер|developer|dev)\s*[:,\-]\s*(.+)$", "coder"),
            (r"^(qa|тестувальник|tester)\s*[:,\-]\s*(.+)$", "qa"),
        )

        for pattern, target in patterns:
            match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return target, match.group(2).strip()

        lowered = text.lower()
        if "питання до qa" in lowered:
            return "qa", text
        if "питання до coder" in lowered or "питання до кодер" in lowered:
            return "coder", text
        if "питання до pm" in lowered:
            return "pm", text

        return None
