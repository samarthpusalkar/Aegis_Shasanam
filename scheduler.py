import datetime
import os.path
import json
import time
import hashlib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.generativeai as genai

from default_variables import SCOPES, OLLAMA_API_URL, OLLAMA_MODEL, TASKS_FILE, PROMPT_FILE, \
    AEGIS_CALENDAR_NAME, STATE_FILE, CHECK_INTERVAL_SECONDS, FEEDBACK_FILE, LOCAL_TIMEZONE, GEMINI_API_KEY


# --- Core Google API and Calendar Functions ---

def setup_google_calendar_api():
    """Initializes and returns the Google Calendar API service object."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
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

# --- State and Time Helper Functions ---

def get_local_day_boundaries():
    """Returns the start and end of the current local day in UTC."""
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    now_local = datetime.datetime.now(local_tz)
    start_of_local_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_local_day = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
    return start_of_local_day.astimezone(datetime.timezone.utc), end_of_local_day.astimezone(datetime.timezone.utc)

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
    start_utc, end_utc = get_local_day_boundaries()
    events_result = service.events().list(
        calendarId="primary", timeMin=start_utc.isoformat(), timeMax=end_utc.isoformat(),
        timeZone=LOCAL_TIMEZONE, singleEvents=True, orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])
    events_str = json.dumps(events, sort_keys=True)
    return hashlib.sha256(events_str.encode("utf-8")).hexdigest()

# --- Adaptive Scheduling Core Functions ---

def clear_future_aegis_events(service, calendar_id):
    """Deletes Aegis events from now until the end of the day."""
    print(f"Clearing future Aegis events from '{AEGIS_CALENDAR_NAME}'...")
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    now_local = datetime.datetime.now(local_tz)
    end_of_day_local = now_local.replace(hour=23, minute=59, second=59, microsecond=0)

    start_utc = now_local.astimezone(datetime.timezone.utc)
    end_utc = end_of_day_local.astimezone(datetime.timezone.utc)

    events_result = service.events().list(
        calendarId=calendar_id, timeMin=start_utc.isoformat(), timeMax=end_utc.isoformat(),
        timeZone=LOCAL_TIMEZONE, singleEvents=True
    ).execute()
    events = events_result.get("items", [])
    
    if not events:
        print("No future events to clear.")
        return

    print(f"  [DEBUG] Found {len(events)} future events to delete.")
    for event in events:
        service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
    print(f"Successfully cleared {len(events)} future events.")

def get_daily_context(service, aegis_calendar_id):
    """Gets past Aegis events and future free slots for adaptive planning."""
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    now_local = datetime.datetime.now(local_tz)

    # Get Past/In-Progress Aegis Events
    day_start_utc, _ = get_local_day_boundaries()
    now_utc = now_local.astimezone(datetime.timezone.utc)
    past_events_result = service.events().list(
        calendarId=aegis_calendar_id, timeMin=day_start_utc.isoformat(),
        timeMax=now_utc.isoformat(), singleEvents=True
    ).execute()
    past_aegis_events = past_events_result.get("items", [])

    # Calculate Future Free Slots
    structured_day_start = now_local.replace(hour=7, minute=0, second=0, microsecond=0)
    structured_day_end = now_local.replace(hour=23, minute=0, second=0, microsecond=0)
    planning_start_local = max(now_local, structured_day_start)
    planning_end_local = structured_day_end
    planning_start_utc = planning_start_local.astimezone(datetime.timezone.utc)
    planning_end_utc = planning_end_local.astimezone(datetime.timezone.utc)

    future_events_result = service.events().list(
        calendarId="primary", timeMin=planning_start_utc.isoformat(),
        timeMax=planning_end_utc.isoformat(), timeZone=LOCAL_TIMEZONE,
        singleEvents=True, orderBy="startTime"
    ).execute()
    future_busy_events = future_events_result.get("items", [])

    future_free_slots = []
    last_end_time_utc = planning_start_utc
    for busy in future_busy_events:
        start_str = busy["start"].get("dateTime")
        end_str = busy["end"].get("dateTime")
        if not start_str or not end_str:
            print(f"  [WARN] Skipping all-day event '{busy.get('summary')}' in free slot calculation.")
            continue
        
        busy_start_utc = datetime.datetime.fromisoformat(start_str)
        if busy_start_utc > last_end_time_utc:
            future_free_slots.append({"start": last_end_time_utc.isoformat(), "end": busy_start_utc.isoformat()})
        last_end_time_utc = max(last_end_time_utc, datetime.datetime.fromisoformat(end_str))
    
    if last_end_time_utc < planning_end_utc:
        future_free_slots.append({"start": last_end_time_utc.isoformat(), "end": planning_end_utc.isoformat()})

    return {"past_events": past_aegis_events, "future_free_slots": future_free_slots}

# --- LLM and Event Creation Functions ---
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

def query_gemini(prompt_data, feedback_text):
    """Sends the structured prompt and feedback to the Gemini API."""
    print("\nQuerying Aegis (Gemini 2.5 Flash)...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')

    with open(PROMPT_FILE, "r") as f:
        system_prompt = f.read()

    full_prompt = f"""
System Instructions:
{system_prompt}
---
Here is the data for today:
- Current Time: {datetime.datetime.now().isoformat()}
- Available Tasks (with last completion time): {json.dumps(prompt_data['tasks'], indent=2)}
- Completed or In-Progress Tasks Today: {json.dumps(prompt_data['past_events'], indent=2)}
- Future Free Time Slots: {json.dumps(prompt_data['future_free_slots'], indent=2)}
- Recent User Feedback:
---
{feedback_text}
---
Based on all this information, generate the JSON schedule for ONLY the future free slots.
"""
    try:
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        return response.text
    except Exception as e:
        print(f"An error occurred while querying Gemini: {e}")
        return None

def create_events_from_schedule(service, calendar_id, schedule_str):
    """Parses the LLM schedule and creates events on the specified calendar."""
    try:
        schedule_data = json.loads(schedule_str)
        schedule_list = schedule_data.get("events")
        if not schedule_list or not isinstance(schedule_list, list):
            print("Error: JSON from LLM is missing the 'events' list.")
            return None
    except (json.JSONDecodeError, AttributeError):
        print("Error: LLM did not return valid JSON. Cannot create events.")
        print("LLM Output:", schedule_str)
        return None

    print(f"\nCreating {len(schedule_list)} new events in '{AEGIS_CALENDAR_NAME}' calendar...")
    for item in schedule_list:
        event = {
            "summary": item.get("summary", "Aegis Task"),
            "description": item.get("description", ""),
            "start": {"dateTime": item["start_time"], "timeZone": LOCAL_TIMEZONE},
            "end": {"dateTime": item["end_time"], "timeZone": LOCAL_TIMEZONE},
        }
        service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"  - Created: {event['summary']} at {item['start_time']} ({LOCAL_TIMEZONE})")
        time.sleep(0.2)
    return schedule_list

# --- Feedback and Task Update Functions ---

def read_recent_feedback(lines_to_read=15):
    """Reads the last few lines of the feedback log."""
    if not os.path.exists(FEEDBACK_FILE):
        return "No feedback has been provided yet."
    try:
        with open(FEEDBACK_FILE, "r") as f:
            return "".join(f.readlines()[-lines_to_read:])
    except Exception as e:
        print(f"Could not read feedback file: {e}")
        return "Error reading feedback file."

def update_tasks_completion(schedule_list):
    """Updates the last_completed_utc field in tasks.json."""
    with open(TASKS_FILE, "r+") as f:
        tasks_data = json.load(f)
        task_map = {task['id']: task for task in tasks_data['tasks']}
        for event in schedule_list:
            task_id = event.get("task_id")
            if task_id in task_map:
                task_map[task_id]["last_completed_utc"] = event.get("end_time")
        f.seek(0)
        json.dump(tasks_data, f, indent=2)
        f.truncate()
    print("Task completion times have been updated.")

# --- Main Execution Loop ---

def main():
    """Main execution block, runs as a continuous adaptive daemon."""
    service = setup_google_calendar_api()
    aegis_calendar_id = find_or_create_aegis_calendar(service)
    
    print("\n--- Aegis_Shasanam Daemon v4 (Adaptive) Initialized ---")
    print(f"Using timezone: {LOCAL_TIMEZONE}")
    print(f"Checking for calendar changes every {CHECK_INTERVAL_SECONDS} seconds.")

    while True:
        try:
            print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for changes...")
            state = load_state()
            current_hash = get_primary_calendar_state_hash(service)

            if current_hash != state.get("last_known_hash"):
                print("!!! Change detected. Adaptively re-planning schedule. !!!")

                # 1. Get the full context of the day (past events and future slots)
                daily_context = get_daily_context(service, aegis_calendar_id)

                # 2. Read tasks and recent feedback
                with open(TASKS_FILE, "r") as f:
                    tasks_data = json.load(f)
                feedback = read_recent_feedback()

                # 3. Query Gemini with the new, richer context
                prompt_data = {
                    "tasks": tasks_data["tasks"],
                    "past_events": daily_context["past_events"],
                    "future_free_slots": daily_context["future_free_slots"]
                }
                suggested_schedule_str = query_gemini(prompt_data, feedback)

                # 4. Adapt the schedule: clear future and create new events
                if suggested_schedule_str:
                    clear_future_aegis_events(service, aegis_calendar_id)
                    schedule_list = create_events_from_schedule(service, aegis_calendar_id, suggested_schedule_str)
                    if schedule_list:
                        update_tasks_completion(schedule_list)

                # 5. Save the new state
                save_state({"last_known_hash": current_hash})
                print("--- Adaptive re-planning complete. ---")
            else:
                print("No changes detected. Standing by.")

            time.sleep(CHECK_INTERVAL_SECONDS)

        except HttpError as error:
            print(f"An API error occurred: {error}")
            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
