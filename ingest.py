import whisper
import requests
import json
import sys
from default_variables import OLLAMA_API_URL, OLLAMA_MODEL, WHISPER_MODEL


def transcribe_audio(file_path):
    """Transcribes the given audio file using Whisper."""
    print(f"Loading Whisper model '{WHISPER_MODEL}'...")
    model = whisper.load_model(WHISPER_MODEL)
    print("Model loaded. Starting transcription...")
    result = model.transcribe(file_path)
    print("Transcription complete.")
    return result["text"]

def summarize_text(text):
    """Sends text to Ollama for summarization."""
    print("Sending transcript to LLM for summarization...")
    system_prompt = """
    You are a world-class meeting summarization AI. You will be given a
    raw transcript of a technical meeting. Your task is to provide a
    concise summary of the key discussion points and a bulleted list
    of any explicit or implicit action items for the user.
    Format your response clearly with "Summary" and "Action Items" sections.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": f"Here is the meeting transcript:\n\n{text}",
        "stream": False,
    }
    response = requests.post(OLLAMA_API_URL, json=payload)
    response.raise_for_status()
    response_json = json.loads(response.text)
    return response_json["response"]

def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <path_to_audio_file>")
        return

    audio_file = sys.argv[1]
    transcript = transcribe_audio(audio_file)
    summary = summarize_text(transcript)

    print("\n\n--- MEETING SUMMARY ---")
    print(summary)
    print("-----------------------")

    # Save the summary to a log file
    with open("meeting_summaries.log", "a") as f:
        f.write(f"--- Summary for {audio_file} at {datetime.datetime.now()} ---\n")
        f.write(summary)
        f.write("\n\n")

if __name__ == "__main__":
    import datetime
    main()
