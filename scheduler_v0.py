import datetime
import os.path
import json
import requests
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
# STEP 1: SCOPES updated to full access
SCOPES = ["https://www.googleapis.com/auth/calendar"]
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:3b"  # Or whatever model you pulled
TASKS_FILE = "tasks.json"
PROMPT_FILE = "system_prompt.txt"
AEGIS_CALENDAR_NAME = "Aegis_Shasanam"


def setup_google_calendar_api():
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        # STEP 2: This part will trigger because we deleted token.json
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


# --- NEW FUNCTION ---
def find_or_create_aegis_calendar(service):
    """Finds the Aegis_Shasanam calendar or creates it if it doesn't exist."""
    print(f"Looking for '{AEGIS_CALENDAR_NAME}' calendar...")
    calendar_list = service.calendarList().list().execute()
    for calendar_list_entry in calendar_list["items"]:
        if calendar_list_entry["summary"] == AEGIS_CALENDAR_NAME:
            print("Found calendar.")
            return calendar_list_entry["id"]

    print("Calendar not found. Creating it...")
    new_calendar = {"summary": AEGIS_CALENDAR_NAME}
    created_calendar = service.calendars().insert(body=new_calendar).execute()
    print("Calendar created.")
    return created_calendar["id"]


def get_free_slots(service):
    """Gets busy slots for today and returns free slots."""
    now = datetime.datetime.utcnow()
    start_of_day = now.replace(hour=7, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=0, second=0, microsecond=0)

    print("Getting today's busy slots from primary calendar...")
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

    busy_slots = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        busy_slots.append({"start": start, "end": end})

    free_slots = []
    last_end_time = start_of_day
    for busy in busy_slots:
        busy_start = datetime.datetime.fromisoformat(
            busy["start"].replace("Z", "+00:00")
        )
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
    response_json = json.loads(response.text)
    return response_json["response"]

# --- REVISED AND CORRECTED FUNCTION ---
def create_events_from_schedule(service, calendar_id, schedule_str):
    """Parses the LLM schedule and creates events on the specified calendar."""
    try:
        schedule_data = json.loads(schedule_str)
    except json.JSONDecodeError:
        print("Error: LLM did not return valid JSON. Cannot create events.")
        print("LLM Output:", schedule_str)
        return

    # THE FIX: Check for the 'events' key and get the list from there.
    schedule_list = schedule_data.get("events")

    # Add a check to ensure the list exists and is actually a list.
    if not schedule_list or not isinstance(schedule_list, list):
        print("Error: JSON from LLM is missing the 'events' list.")
        print("LLM Output:", schedule_str)
        return

    print(
        f"\nCreating {len(schedule_list)} events in '{AEGIS_CALENDAR_NAME}' calendar..."
    )
    for item in schedule_list:
        # Check if the item is a dictionary before trying to access it
        if not isinstance(item, dict):
            print(f"  - Skipping invalid item in schedule: {item}")
            continue

        event = {
            "summary": item.get("summary", "Aegis Task"),
            "description": item.get("description", ""),
            "start": {"dateTime": item["start_time"], "timeZone": "UTC"},
            "end": {"dateTime": item["end_time"], "timeZone": "UTC"},
        }
        service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"  - Created: {event['summary']} at {event['start']['dateTime']}")
        time.sleep(0.2)  # Be nice to the API, avoid rate limiting


def main():
    """Main execution block"""
    try:
        service = setup_google_calendar_api()
        aegis_calendar_id = find_or_create_aegis_calendar(service)
        free_slots = get_free_slots(service)

        with open(TASKS_FILE, "r") as f:
            tasks_data = json.load(f)

        prompt_data = {"tasks": tasks_data["tasks"], "free_slots": free_slots}
        suggested_schedule_str = query_ollama(prompt_data)

        print("\n--- AEGIS SUGGESTED SCHEDULE (JSON) ---")
        print(suggested_schedule_str)
        print("--------------------------------------")

        create_events_from_schedule(service, aegis_calendar_id, suggested_schedule_str)

        print("\nPhase 1 Complete. Schedule has been written to your calendar.")

    except HttpError as error:
        print(f"An error occurred: {error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
