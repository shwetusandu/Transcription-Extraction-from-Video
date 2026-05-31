# Transcription Extraction from Video

An AI-powered automation platform that extracts transcripts from YouTube videos and Instagram reels, generates structured AI summaries and Q&A insights using Whisper + Groq LLMs, stores outputs in Google Sheets, and enables downstream n8n automation workflows.

---

# Features

* YouTube & Instagram Reel support
* Audio extraction using `yt-dlp` + `ffmpeg`
* Speech-to-text transcription using `OpenAI Whisper`
* AI-powered Q&A summary generation using `Groq LLM`
* Google Sheets integration for structured storage
* n8n-ready workflow automation architecture
* Real-time job progress tracking
* Transcript & AI summary file exports
* Instagram cookie-based authentication support
* Error handling & retry mechanisms
* Cloud deployment ready (Render / Railway)

---

# Architecture

```text
YouTube / Instagram URL
            ↓
     yt-dlp Download
            ↓
     Audio Extraction
            ↓
   Whisper Transcription
            ↓
      Groq AI Analysis
            ↓
   Google Sheets Storage
            ↓
      n8n Automation
            ↓
AI Content Repurposing Pipeline
```

---

# Tech Stack

| Component        | Technology       |
| ---------------- | ---------------- |
| Backend          | Flask            |
| AI Transcription | OpenAI Whisper   |
| LLM Analysis     | Groq API         |
| Video Download   | yt-dlp           |
| Audio Processing | ffmpeg           |
| Database         | Google Sheets    |
| Automation       | n8n              |
| Deployment       | Render / Railway |

---

# Supported Platforms

* YouTube Videos
* YouTube Shorts
* Instagram Reels
* Instagram Videos

---

# Project Structure

```text
project/
│
├── app.py
├── google_sheets.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── README.md
├── .gitignore
│
├── templates/
│   └── index.html
│
├── downloads/
│   ├── transcriptions/
│   └── GROQ-Summary/
```

---

# Environment Variables

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
WHISPER_MODEL=tiny

# Optional Instagram Authentication
YTDLP_COOKIES_FROM_BROWSER=chrome
YTDLP_COOKIES_FILE=C:\path\to\instagram-cookies.txt

# Google Sheets
SPREADSHEET_ID=your_google_sheet_id
```

---

# Installation

## Clone Repository

```bash
git clone <your-repository-url>
cd Transcription-Extraction-from-Video
```

---

## Create Virtual Environment

### Windows

```bash
py -m venv .venv
.venv\Scripts\activate
```

### Mac/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

# Install FFmpeg

FFmpeg must be installed and available in PATH.

## Windows

Download:
https://ffmpeg.org/download.html

Verify:

```bash
ffmpeg -version
```

---

# Google Sheets Setup

## 1. Enable APIs

Enable:

* Google Sheets API
* Google Drive API

Inside:
Google Cloud Console → APIs & Services

---

## 2. Create Service Account

Create:

```text
google-sheets-writer
```

Download JSON credentials.

Rename to:

```text
service_account.json
```

Place in project root.

---

## 3. Share Google Sheet

Share your Google Sheet with the service account email:

```text
google-sheets-writer@your-project.iam.gserviceaccount.com
```

Permission:

```text
Editor
```

---

# Run Application

```bash
py app.py
```

Application runs at:

```text
http://127.0.0.1:5000
```

---

# API Endpoint

## Process Video/Reel

### Endpoint

```http
POST /process
```

### Request Body

```json
{
  "source_url": "https://www.youtube.com/watch?v=example"
}
```

---

# Output Generated

The system automatically generates:

* Video/Reel Description
* Full Transcript
* Detailed AI Q&A Summary
* Transcript TXT file
* AI Summary Markdown file
* Google Sheets records

---

# Google Sheets Output

The application writes data into:

```text
MyVirtualAssistant_DB
→ AI_Transcripts
```

Columns:

| Column          |
| --------------- |
| Timestamp       |
| Source_URL      |
| Platform        |
| Description     |
| Transcript      |
| QA_Summary      |
| Status          |
| Score           |
| Briefed Summary |
| Video Creation  |
| Upload          |
| Uploaded Status |

---

# Cloud Deployment

## Deploy on Render

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
gunicorn app:app
```

---

# Procfile

```text
web: gunicorn app:app
```

---

# runtime.txt

```text
python-3.11.9
```

---

# Security Notes

Do NOT commit:

* `.env`
* `service_account.json`
* `downloads/`

Use `.gitignore`.

---

# .gitignore

```gitignore
.env
service_account.json
downloads/
__pycache__/
*.pyc
.venv/
```

---

# Example Use Cases

* AI content repurposing
* Podcast intelligence
* Creator automation
* Knowledge extraction
* AI shorts generation
* Social media automation
* Video summarization pipelines

---

# Future Enhancements

* Multi-user authentication
* Supabase/PostgreSQL integration
* AI clip generation
* LinkedIn/Twitter automation
* AI avatar video generation
* Background task queues
* Docker support
* SaaS dashboard

---

# Resume Project Description

Built an AI-powered video intelligence and automation platform that extracts transcripts from YouTube and Instagram content, generates structured AI summaries and Q&A insights using Whisper and Groq LLMs, stores outputs in Google Sheets, and triggers downstream n8n automation workflows for scalable content repurposing.

---

# License

MIT License

