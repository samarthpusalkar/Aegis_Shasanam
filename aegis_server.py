# aegis_server.py
from flask import Flask, request, jsonify
import datetime

# Import the necessary Google Calendar functions from your main script
# (This assumes your functions are in a file named scheduler.py)
from scheduler import setup_google_calendar_api, LOCAL_TIMEZONE

app = Flask(__name__)

# Initialize the Google Calendar service once on startup
try:
    print("Initializing Google Calendar service for server...")
    google_service = setup_google_calendar_api()
    print("Service initialized successfully.")
except Exception as e:
    print(f"FATAL: Could not initialize Google Calendar service: {e}")
    google_service = None

@app.route('/add_event', methods=['POST'])
def add_event():
    if not google_service:
        return jsonify({"error": "Google Calendar service not available"}), 500

    data = request.json
    print(f"Received request to add event: {data}")

    # Basic validation
    if not all(k in data for k in ['summary', 'start_time', 'end_time']):
        return jsonify({"error": "Missing required fields: summary, start_time, end_time"}), 400

    event = {
        'summary': data['summary'],
        'start': {
            'dateTime': data['start_time'], # Expects "YYYY-MM-DDTHH:MM:SS"
            'timeZone': LOCAL_TIMEZONE,
        },
        'end': {
            'dateTime': data['end_time'],
            'timeZone': LOCAL_TIMEZONE,
        },
    }

    try:
        created_event = google_service.events().insert(
            calendarId='primary', # Add to the PRIMARY calendar
            body=event
        ).execute()
        print(f"Successfully added event to primary calendar: {created_event.get('htmlLink')}")
        return jsonify({"status": "success", "eventId": created_event['id']}), 200
    except Exception as e:
        print(f"Error creating calendar event: {e}")
        return jsonify({"error": "Failed to create calendar event"}), 500

if __name__ == '__main__':
    # Runs on http://0.0.0.0:5678, accessible from other devices on your network
    app.run(host='0.0.0.0', port=5678, debug=True)
