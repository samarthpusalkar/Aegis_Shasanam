import os
from tzlocal import get_localzone_name


SCOPES = os.getenv('SCOPES', 'https://www.googleapis.com/auth/calendar'.split(','))
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', "qwen2.5-coder:3b")
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base.en')
TASKS_FILE = "tasks.json"
PROMPT_FILE = "system_prompt.txt"
FEEDBACK_FILE = "feedback.log"
AEGIS_CALENDAR_NAME = "Aegis_Shasanam"
STATE_FILE = "state.json"
CHECK_INTERVAL_SECONDS = 60
try:
    # This is the new dynamic way to get the local timezone name
    LOCAL_TIMEZONE = get_localzone_name()
except Exception:
    print("Warning: Could not automatically detect timezone. Falling back to UTC.")
    LOCAL_TIMEZONE = "UTC"

print(f"--- Detected local timezone as: {LOCAL_TIMEZONE} ---")
