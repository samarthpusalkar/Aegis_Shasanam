import os


SCOPES = os.getenv('SCOPES', 'https://www.googleapis.com/auth/calendar'.split(','))
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', "qwen2.5-coder:3b")
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base.en')
TASKS_FILE = "tasks.json"
PROMPT_FILE = "system_prompt.txt"
AEGIS_CALENDAR_NAME = "Aegis_Shasanam"
STATE_FILE = "state.json"
CHECK_INTERVAL_SECONDS = 900
