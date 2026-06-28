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

        if self._is_create_directory_capability_question(lowered):
            return IntentResult("capability_request", 0.9, message, extracted_task="create_directory")

        directory_name = self._extract_directory_to_create(text)
        if directory_name:
            return IntentResult(
                name="create_directory",
                confidence=0.92,
                raw_message=message,
                target_path=directory_name,
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
            ("що відхилив qa", "чому qa", "qa fail", "qa відхилив", "що qa знайшов", "покажи qa"),
        ):
            return IntentResult("qa_history_request", 0.9, message, references_active_task=True)

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

        if self._is_general_question(text):
            return IntentResult("general_question", 0.82, message)

        if self._contains_any(
            lowered,
            (
                "зроби",
                "створи",
                "додай",
                "добав",
                "зміни",
                "заміни",
                "онови",
                "покращи",
                "відредагуй",
                "реалізуй",
                "перероби",
                "виправ",
                "перевір",
                "знайди помилку",
                "збілди",
                "запусти",
            ),
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
    def _is_create_directory_capability_question(lowered: str) -> bool:
        return (
            "можеш" in lowered
            and ("створити папку" in lowered or "створити директор" in lowered or "create folder" in lowered)
        )

    @staticmethod
    def _extract_directory_to_create(text: str) -> str | None:
        lowered = text.lower()
        if not re.match(r"^\s*(створи|додай|create|make)\s+(папку|папка|директорію|директор|folder|directory)\b", lowered):
            if not re.match(r"^\s*зроби\s+(папку|папка|директорію|директор)\b", lowered):
                return None
        if "?" in lowered:
            return None

        absolute_match = re.search(r"([A-Za-z]:\\[^\n\r]+)", text)
        if absolute_match:
            return absolute_match.group(1).strip().strip("\"`'")

        patterns = (
            r"(?:папку|папці|папка|директорію|folder|directory)\s+[`\"']?([A-Za-zА-Яа-яІіЇїЄєҐґ0-9_. -]+?)[`\"']?(?:[.?!]|$)",
            r"[`\"']([A-Za-zА-Яа-яІіЇїЄєҐґ0-9_. -]+)[`\"']",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if candidate:
                    return candidate

        return None

    @staticmethod
    def _is_general_question(text: str) -> bool:
        lowered = text.lower().strip()
        task_prefixes = (
            "зроби",
            "створи",
            "додай",
            "добав",
            "зміни",
            "заміни",
            "онови",
            "покращи",
            "відредагуй",
            "реалізуй",
            "перероби",
            "виправ",
            "перевір",
            "знайди",
            "збілди",
            "запусти",
        )
        if lowered.startswith(task_prefixes):
            return False

        question_prefixes = (
            "ти можеш",
            "можеш",
            "чи можеш",
            "можна",
            "що ",
            "як ",
            "де ",
            "коли ",
            "чому ",
            "навіщо ",
            "який ",
            "яка ",
            "яке ",
            "які ",
        )
        return lowered.endswith("?") or lowered.startswith(question_prefixes)

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
