import datetime

LOG_FILE = "feedback.log"

def main():
    """Gathers and logs user feedback for the day."""
    print("--- Aegis_Shasanam Daily Feedback ---")
    print("Reflect on the schedule generated for you today.")

    rating = ""
    while rating not in ["1", "2", "3", "4", "5"]:
        rating = input("On a scale of 1-5, how would you rate today's schedule? ")

    comments = input("Any comments on what worked or what didn't? (e.g., 'too packed', 'not enough project time')\n> ")

    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"--- Feedback for {datetime.date.today()} ---\n")
            f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Rating: {rating}/5\n")
            f.write(f"Comments: {comments}\n\n")
        print("\nThank you. Your feedback has been logged.")
    except IOError as e:
        print(f"\nError: Could not write to log file: {e}")

if __name__ == "__main__":
    main()
