# Aegis_Shasanam: Your Personal AI Life Architect 🚀

_An intelligent, local-LLM powered scheduler designed for software developers (and anyone!) seeking disciplined productivity and holistic growth in a work-from-home environment._

---

## 🎯 The Problem: WFH Brain Rot & Unstructured Time

Working from home offers immense flexibility, but it often comes at a cost: blurred lines between work and personal life, endless distractions (looking at you, YouTube!), and a nagging feeling of unproductivity despite having time. This leads to burnout, neglected hobbies, forgotten personal projects, and a general lack of discipline and direction.

I found myself caught in this cycle: valuable time evaporating into endless feeds, health routines falling by the wayside, and personal growth stagnating. I had ambitious goals – mastering new tech, diving into astrophotography, learning piano, getting fit – but lacked the structure to make them happen.

## ✨ The Solution: Aegis_Shasanam

Instead of just complaining, I decided to **#VibeCode** my way out of it. **Aegis_Shasanam** is my personal "life architect," a side project that leverages a local Large Language Model (LLM) and the Google Calendar API to intelligently carve out and schedule every aspect of my day.

It's designed to:
*   **Prioritize Health:** Ensure time for meditation, exercise, and timely meals.
*   **Maximize Productivity:** Intelligently fill free slots with deep work, professional learning (e.g., system design, practical programming).
*   **Nurture Hobbies & Interests:** Dedicate guilt-free time for personal projects (Python libraries), creative pursuits (digital drawing, piano), gaming, and even chess strategy.
*   **Adapt to Reality:** Designed to eventually adapt to unpredictable work meetings and re-plan on the fly.

## 🧠 How It Works (High-Level)

1.  **Calendar Scan:** Aegis_Shasanam queries your Google Calendar to identify all your existing meetings and commitments, calculating available free time slots for the day.
2.  **Task Library:** It consults a `tasks.json` file, which is your personal database of desired activities (hobbies, learning goals, health routines) along with their duration constraints.
3.  **LLM Brain:** All this data (free slots, tasks, and your custom scheduling rules from `system_prompt.txt`) is fed into a **local LLM (powered by Ollama)**. The LLM acts as the "brain," generating an optimized, balanced schedule for the day.
4.  **Calendar Integration:** The generated schedule is then automatically added as events to a dedicated `Aegis_Shasanam` calendar in your Google Calendar, giving you a clear, actionable plan.

## 🚀 Project Phases & Current State

### Phase 1: Reactive Scheduler (Current)
*   You run the script.
*   It reads your existing calendar.
*   It generates and writes a new, optimized schedule to your dedicated `Aegis_Shasanam` calendar for the current day.

### Phase 2: Proactive Daemon (Next)
*   The script will run continuously in the background.
*   It will monitor your primary calendar for new meetings or changes.
*   If changes occur, it will automatically re-calculate and update your `Aegis_Shasanam` schedule to adapt.

### Phase 3: Intelligent Agent (Future)
*   Integration with meeting transcription to summarize notes.
*   Dynamic task suggestions from the LLM based on your progress and interests.
*   User feedback mechanisms to refine scheduling over time.

## 🛠️ Technologies Used

*   **Python:** The core scripting language.
*   **Ollama:** For running powerful Large Language Models locally.
*   **Google Calendar API:** For reading your schedule and writing new events.
*   **Large Language Models:** (e.g., Llama 3, Mistral) as the intelligent scheduler.

---

## 🚀 Getting Started (Setup Guide)

Follow these steps to set up and run Aegis_Shasanam on your machine.

### Prerequisites

*   **Python 3.8+:** Make sure Python is installed.
*   **Ollama:**
    1.  Download and install Ollama from [ollama.com](https://ollama.com/).
    2.  Pull a suitable model, e.g., qwen2.5-coder:3b (recommended for its instruction following):
        ```bash
        ollama pull qwen2.5-coder:3b
        ```
        (You can also use `mistral` or others, just update `OLLAMA_MODEL` in `scheduler_v0.py`)

### Google Calendar API Setup

This project interacts with your Google Calendar. You need to create credentials in the Google Cloud Console.

1.  **Go to Google Cloud Console:** Open [console.cloud.google.com](https://console.cloud.google.com/).
2.  **Create a New Project:** From the project dropdown at the top, select `New Project`. Give it a name like "Aegis_Shasanam_API".
3.  **Enable Calendar API:**
    *   In the sidebar menu (☰), go to **APIs & Services > Library**.
    *   Search for "Google Calendar API" and enable it.
4.  **Create OAuth Client ID Credentials:**
    *   In the sidebar menu, go to **APIs & Services > Credentials**.
    *   Click `+ CREATE CREDENTIALS` and select `OAuth client ID`.
    *   If prompted, configure the **OAuth consent screen** first.
        *   Choose `External` User Type (unless you have a Google Workspace organization and want it internal-only).
        *   Fill in required app information (App name: `Aegis_Shasanam`, your email, etc.). You don't need to submit for verification for personal use.
    *   Back in "Create OAuth client ID," select `Desktop app` as the Application type.
    *   Click `Create`.
    *   A panel will appear with your client ID and secret. Click **DOWNLOAD JSON**.
    *   Rename the downloaded file to `credentials.json` and place it in the root directory of this project (next to `scheduler_v0.py`).
5.  **Add Yourself as a "Test User":**
    *   Still in the Google Cloud Console, go to **APIs & Services > OAuth consent screen**.
    *   Scroll down to the "Test users" section.
    *   Click `+ ADD USERS` and enter the **exact Google email address** you will use to authenticate with the script. Click `SAVE`. This prevents the "unverified app" error during your first run.

### Project Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/samarthpusalkar/Aegis_Shasanam.git
    cd Aegis_Shasanam
    ```
2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: `venv\Scripts\activate`
    ```
3.  **Install Dependencies:**
    Install:
    ```bash
    pip install -r requirements.txt
    ```

### First Run!

1.  **Ensure Ollama is Running:** Make sure the Ollama server is active in the background on your machine.
2.  **Run the Script:**
    ```bash
    python scheduler_v0.py
    ```
3.  **Authenticate with Google:**
    *   The first time you run it, a browser window will open.
    *   Log in with the Google account you added as a "Test User."
    *   Grant the requested permissions (to manage your calendars). A `token.json` file will be created in your project directory to store your credentials for future runs.
4.  **Check your Google Calendar:** A new calendar named `Aegis_Shasanam` will appear under "My calendars," populated with your new, AI-generated schedule!

## ⚠️ Security & Privacy (IMPORTANT!)

**DO NOT SHARE `credentials.json` or `token.json` PUBLICLY!**
These files contain sensitive authentication information for your Google account and Cloud project. They must **never** be committed to your public Git repository.

This repository includes a `.gitignore` file that should prevent these files from being accidentally pushed. **Ensure it contains:**


``` Disclaimer: This README (and repo code) has been AI Generated Take it with caution ```
