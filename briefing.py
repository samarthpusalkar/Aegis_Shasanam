import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
AEGIS_CALENDAR_NAME = "Aegis_Shasanam"

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

def get_todays_briefing(service, calendar_id):
    now = datetime.datetime.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_of_day.isoformat() + "Z",
        timeMax=end_of_day.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])

    print(f"--- Aegis_Shasanam Daily Briefing for {datetime.date.today()} ---")
    if not events:
        print("Your schedule is clear. A new plan will be generated shortly.")
        return

    for event in events:
        start_str = event['start'].get('dateTime')
        start_dt_utc = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        local_start = start_dt_utc.astimezone(datetime.datetime.now().astimezone().tzinfo)
        print(f"  - {local_start.strftime('%H:%M')}: {event['summary']}")
    print("---------------------------------------------------------")

def main():
    service = setup_google_calendar_api()
    aegis_calendar_id = find_aegis_calendar_id(service)
    if not aegis_calendar_id:
        print(f"Error: Calendar '{AEGIS_CALENDAR_NAME}' not found.")
        return
    get_todays_briefing(service, aegis_calendar_id)

if __name__ == "__main__":
    main()
