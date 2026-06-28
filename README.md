# AI Telegram Team Runtime

Локальна multi-agent система для Telegram: один Telegram bot як вхід у систему, а всередині центральний runtime з PM, Coder, QA і Final PM агентами.

Поточний стан: робочий MVP. Архітектура вже повна для базового локального dev workflow: агенти можуть створювати папки/файли в workspace, запускати safe allowlist-команди і показувати git status/diff.

```text
Telegram Bot
  -> Conversation Router
  -> Main Orchestrator
  -> PM Agent
  -> Coder Agent
  -> QA Agent
  -> Final PM Agent
  -> Telegram response
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Заповни `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
LLAMA_BASE_URL=http://127.0.0.1:8081/v1
LLAMA_MODEL=ornith-1.0-9b-Q4_K_M.gguf
DEFAULT_WORKSPACE=E:\ai-agents-system
WRITE_MODE=bypass
```

## Run

Спочатку запусти `llama-server` на `127.0.0.1:8081`, потім:

```powershell
python main.py
```

## Telegram UX

Можна писати природною мовою:

```text
Зроби сторінку логіну на React і Tailwind
```

Можна звертатись до конкретного агента:

```text
QA, перевір чи нормальний план
```

```text
Coder, поясни рішення
```

Можна виконувати прості filesystem-задачі:

```text
Створи папку TEST
```

```text
Створи файл notes.txt з текстом hello в папці TEST
```

Можна попросити diff/status:

```text
Покажи зміни
```

```text
Як там?
```

Команди:

```text
/start
/help
/status
/workspace E:\ai-agents-system
```

## Logs

Кожна задача пишеться в:

```text
logs/task_*/
```

Там зберігаються:

```text
task.json
user_message.md
pm_plan.md
coder_round_*.md
qa_round_*.md
final_summary.md
```

## Safety

Tool Layer працює тільки всередині активного workspace.

Дозволено автоматично:

```text
create_directory
write_file
run_command для allowlist build/test/lint/compileall команд
git status
git diff
```

Заблоковано:

```text
shell-команди сирим рядком
git push
npm publish
package install
видалення файлів
робота поза workspace
.env edits
```

## Roadmap

- MVP 1: один Telegram bot + повний text-only agent workflow.
- MVP 2: read-only workspace tools.
- MVP 3: safe create/write tools у workspace.
- MVP 4: QA build/test/lint loop через allowlist `run_command`.
- MVP 5: git diff/status.
- Future: Telegram group mode і optional bot personas поверх одного central runtime.
