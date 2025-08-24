import datetime
import os.path
from tzlocal import get_localzone_name

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
AEGIS_CALENDAR_NAME = "Aegis_Shasanam"

# Dynamic timezone detection (same as in scheduler_v3.py)
try:
    LOCAL_TIMEZONE = get_localzone_name()
except Exception:
    print("Warning: Could not automatically detect timezone. Falling back to UTC.")
    LOCAL_TIMEZONE = "UTC"

def setup_google_calendar_api():
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

def find_aegis_calendar_id(service):
    calendar_list = service.calendarList().list().execute()
    for calendar_list_entry in calendar_list["items"]:
        if calendar_list_entry["summary"] == AEGIS_CALENDAR_NAME:
            return calendar_list_entry["id"]
    return None

def get_local_day_boundaries():
    """
    Returns the start and end of the current local day in UTC.
    Same helper function as in scheduler_v3.py.
    """
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    now_local = datetime.datetime.now(local_tz)
    
    start_of_local_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_local_day = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
    
    # Convert to UTC for API calls
    start_utc = start_of_local_day.astimezone(datetime.timezone.utc)
    end_utc = end_of_local_day.astimezone(datetime.timezone.utc)
    
    return start_utc, end_utc

def get_todays_briefing(service, calendar_id):
    """Gets today's Aegis events using consistent timezone logic."""
    start_utc, end_utc = get_local_day_boundaries()
    
    print(f"--- Aegis_Shasanam Daily Briefing for {datetime.date.today()} ({LOCAL_TIMEZONE}) ---")

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_utc.isoformat(),
        timeMax=end_utc.isoformat(),
        timeZone=LOCAL_TIMEZONE,
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])

    if not events:
        print("Your schedule is clear. A new plan will be generated shortly.")
        return

    # Get local timezone for display
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

    for event in events:
        start_str = event['start'].get('dateTime')
        if start_str:
            # Parse the datetime and convert to local time for display
            start_dt_utc = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            local_start = start_dt_utc.astimezone(local_tz)
            print(f"  - {local_start.strftime('%H:%M')}: {event['summary']}")
        else:
            # Handle all-day events
            print(f"  - All Day: {event['summary']}")
    print("---------------------------------------------------------")

def main():
    print(f"Using timezone: {LOCAL_TIMEZONE}")
    service = setup_google_calendar_api()
    aegis_calendar_id = find_aegis_calendar_id(service)
    if not aegis_calendar_id:
        print(f"Error: Calendar '{AEGIS_CALENDAR_NAME}' not found.")
        return
    get_todays_briefing(service, aegis_calendar_id)

if __name__ == "__main__":
    main()
