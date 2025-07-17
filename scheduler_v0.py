import datetime
import os.path
import json
import requests

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:3b"  # Or whatever model you pulled
TASKS_FILE = "tasks.json"
PROMPT_FILE = "system_prompt.txt"


def setup_google_calendar_api():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def get_free_slots(service):
    """Gets busy slots for today and returns free slots."""
    now = datetime.datetime.utcnow()
    start_of_day = now.replace(hour=7, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=0, second=0, microsecond=0)

    print("Getting today's busy slots...")
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_day.isoformat() + "Z",
            timeMax=end_of_day.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        print("No upcoming events found.")
        # Return one large free block for the whole day
        return [
            {
                "start": start_of_day.isoformat(),
                "end": end_of_day.isoformat(),
            }
        ]

    busy_slots = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        busy_slots.append({"start": start, "end": end})

    print("--- BUSY SLOTS ---")
    for slot in busy_slots:
        print(f"  From {slot['start']} to {slot['end']}")
    print("--------------------")

    free_slots = []
    last_end_time = start_of_day
    for busy in busy_slots:
        busy_start = datetime.datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
        if busy_start > last_end_time:
            free_slots.append(
                {
                    "start": last_end_time.isoformat(),
                    "end": busy_start.isoformat(),
                }
            )
        last_end_time = max(
            last_end_time,
            datetime.datetime.fromisoformat(busy["end"].replace("Z", "+00:00")),
        )

    if last_end_time < end_of_day:
        free_slots.append(
            {"start": last_end_time.isoformat(), "end": end_of_day.isoformat()}
        )

    return free_slots


def query_ollama(prompt_data):
    """Sends the structured prompt to the local Ollama server."""
    print("\nQuerying Aegis (Ollama LLM)...")
    with open(PROMPT_FILE, "r") as f:
        system_prompt = f.read()

    full_prompt = f"""
Here is the data for today:
- Current Time: {datetime.datetime.now().isoformat()}
- Available Tasks: {json.dumps(prompt_data['tasks'], indent=2)}
- Free Time Slots: {json.dumps(prompt_data['free_slots'], indent=2)}

Based on all this information and your core directives, generate the JSON schedule.
"""
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": full_prompt,
        "format": "json",
        "stream": False,
    }

    response = requests.post(OLLAMA_API_URL, json=payload)
    response.raise_for_status()
    # The response from Ollama is a JSON string, which needs to be parsed.
    # The actual content is in the 'response' key.
    response_json = json.loads(response.text)
    return response_json["response"]


def main():
    """Main execution block"""
    try:
        service = setup_google_calendar_api()
        free_slots = get_free_slots(service)

        print("\n--- FREE SLOTS ---")
        for slot in free_slots:
            start = datetime.datetime.fromisoformat(slot["start"])
            end = datetime.datetime.fromisoformat(slot["end"])
            duration = (end - start).total_seconds() / 60
            print(f"  Slot from {start.strftime('%H:%M')} to {end.strftime('%H:%M')} ({duration:.0f} mins)")
        print("--------------------")


        with open(TASKS_FILE, "r") as f:
            tasks_data = json.load(f)

        prompt_data = {"tasks": tasks_data["tasks"], "free_slots": free_slots}

        suggested_schedule_str = query_ollama(prompt_data)

        print("\n\n--- AEGIS SUGGESTED SCHEDULE (JSON) ---")
        # Pretty-print the JSON string returned by the LLM
        suggested_schedule = json.loads(suggested_schedule_str)
        print(json.dumps(suggested_schedule, indent=2))
        print("--------------------------------------")
        print("\nPhase 0 Complete. The core engine is running.")
        print("Next step (Phase 1) is to parse this JSON and write to Google Calendar.")

    except HttpError as error:
        print(f"An error occurred: {error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
