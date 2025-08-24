import datetime
import os.path
import json
import requests
import time
import hashlib
from pytz import timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from default_variables import SCOPES, OLLAMA_API_URL, OLLAMA_MODEL, TASKS_FILE, PROMPT_FILE, \
    AEGIS_CALENDAR_NAME, STATE_FILE, CHECK_INTERVAL_SECONDS, FEEDBACK_FILE, LOCAL_TIMEZONE



def setup_google_calendar_api():
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

# --- NEW HELPER FUNCTIONS ---
def load_state():
    """Loads the last known state from the state file."""
    if not os.path.exists(STATE_FILE):
        return {"last_known_hash": None}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    """Saves the current state to the state file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_primary_calendar_state_hash(service):
    """Fetches today's primary calendar events and returns a hash."""
    
    # 1. Get current local time
    local_tz = timezone(LOCAL_TIMEZONE)
    now_local = datetime.datetime.now(local_tz)

    # 2. Define the start and end of *today* in local time
    start_of_local_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_local_day = now_local.replace(hour=23, minute=59, second=59, microsecond=0)

    # 3. Convert these local times to UTC for the API request
    start_of_utc_day = start_of_local_day.astimezone(datetime.timezone.utc)
    end_of_utc_day = end_of_local_day.astimezone(datetime.timezone.utc)

    print(f"  [DEBUG] Local time: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    print(f"  [DEBUG] Fetching primary calendar events from {start_of_utc_day.isoformat()} to {end_of_utc_day.isoformat()} (UTC)")

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_utc_day.isoformat(), # No 'Z' needed if it's already timezone-aware
            timeMax=end_of_utc_day.isoformat(),   # No 'Z' needed if it's already timezone-aware
            timeZone=LOCAL_TIMEZONE, # Hint to the API to interpret times in your local TZ
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    print(f"  [DEBUG] Found {len(events)} events in primary calendar:")
    for event in events:
        summary = event.get('summary', 'No Summary')
        start_time_info = event['start'].get('dateTime', event['start'].get('date', 'Unknown Start'))
        end_time_info = event['end'].get('dateTime', event['end'].get('date', 'Unknown End'))
        print(f"    - {summary} from {start_time_info} to {end_time_info}")

    # Create a stable string representation of the events for hashing
    events_str = json.dumps(events, sort_keys=True)
    current_hash = hashlib.sha256(events_str.encode("utf-8")).hexdigest()
    print(f"  [DEBUG] Calculated hash: {current_hash}")
    return current_hash

def clear_aegis_calendar(service, calendar_id):
    """Deletes all events from the Aegis calendar for today."""
    print(f"Clearing today's events from '{AEGIS_CALENDAR_NAME}'...")
    now = datetime.datetime.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_of_day.isoformat() + "Z",
        timeMax=end_of_day.isoformat() + "Z",
        singleEvents=True
    ).execute()
    
    events = events_result.get("items", [])
    if not events:
        print("No events to clear.")
        return

    for event in events:
        service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
        print(f"  - Deleted: {event.get('summary')}")
        time.sleep(0.1) # Be nice to the API
    print("Calendar cleared.")


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

def query_ollama(prompt_data, feedback_text):
    """Sends the structured prompt and feedback to the local Ollama server."""
    print("\nQuerying Aegis (Ollama LLM) with feedback...")
    with open(PROMPT_FILE, "r") as f:
        system_prompt = f.read()

    full_prompt = f"""
Here is the data for today:
- Current Time: {datetime.datetime.now().isoformat()}
- Available Tasks (with last completion time): {json.dumps(prompt_data['tasks'], indent=2)}
- Free Time Slots: {json.dumps(prompt_data['free_slots'], indent=2)}
- Recent User Feedback:
---
{feedback_text}
---

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


def read_recent_feedback(lines_to_read=15):
    """Reads the last few lines of the feedback log."""
    if not os.path.exists(FEEDBACK_FILE):
        return "No feedback has been provided yet."
    try:
        with open(FEEDBACK_FILE, "r") as f:
            lines = f.readlines()
            recent_lines = lines[-lines_to_read:]
            return "".join(recent_lines)
    except Exception as e:
        print(f"Could not read feedback file: {e}")
        return "Error reading feedback file."

def update_tasks_completion(schedule_list):
    """Updates the last_completed_utc field in tasks.json."""
    if not os.path.exists(TASKS_FILE):
        print(f"Error: {TASKS_FILE} not found. Cannot update task completions.")
        return

    with open(TASKS_FILE, "r") as f:
        tasks_data = json.load(f)

    # Create a map for faster lookups
    task_map = {task['id']: task for task in tasks_data['tasks']}

    for event in schedule_list:
        task_id = event.get("task_id")
        if task_id in task_map:
            task_map[task_id]["last_completed_utc"] = event.get("end_time")
            print(f"  - Updated completion time for task: {task_id}")

    with open(TASKS_FILE, "w") as f:
        json.dump(tasks_data, f, indent=2)
    print("Task completion times have been updated.")


def main():
    """Main execution block, now runs as a continuous loop."""
    service = setup_google_calendar_api()
    aegis_calendar_id = find_or_create_aegis_calendar(service)
    
    print("\n--- Aegis_Shasanam Daemon Initialized ---")
    print(f"Checking for calendar changes every {CHECK_INTERVAL_SECONDS} seconds.")

    while True:
        try:
            print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for changes...")
            
            state = load_state()
            print(f"  [DEBUG] Last known hash from state: {state.get('last_known_hash')}")
            current_hash = get_primary_calendar_state_hash(service)

            if current_hash != state.get("last_known_hash"):
                print("!!! Change detected in primary calendar. Re-planning schedule. !!!")
                
                # 1. Clear the old schedule
                clear_aegis_calendar(service, aegis_calendar_id)

                # 2. Get new free slots
                free_slots = get_free_slots(service)

                # 3. Read tasks and recent feedback
                with open(TASKS_FILE, "r") as f:
                    tasks_data = json.load(f)
                feedback = read_recent_feedback()

                # 4. Query LLM with all context
                prompt_data = {"tasks": tasks_data["tasks"], "free_slots": free_slots}
                suggested_schedule_str = query_ollama(prompt_data, feedback)
                
                # 5. Create new events
                schedule_list = create_events_from_schedule(service, aegis_calendar_id, suggested_schedule_str)
                
                # 6. Update task completion times if schedule was created
                if schedule_list:
                    update_tasks_completion(schedule_list)

                # 7. Save the new state
                save_state({"last_known_hash": current_hash})
                print("--- Re-planning complete. ---")

            else:
                print("No changes detected. Standing by.")

            time.sleep(CHECK_INTERVAL_SECONDS)

        except HttpError as error:
            print(f"An API error occurred: {error}")
            print("Retrying after interval...")
            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Retrying after interval...")
            time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
