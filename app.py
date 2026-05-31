import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from openai import OpenAI
import whisper
from dotenv import dotenv_values, load_dotenv
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from google_sheets import write_to_google_sheet

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)
RESULTS_DIR = BASE_DIR / "downloads" / "transcriptions"
RESULTS_DIR.mkdir(exist_ok=True)
GROQ_SUMMARY_DIR = BASE_DIR / "downloads" / "GROQ-Summary"
GROQ_SUMMARY_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "tiny").strip() or "tiny"
WHISPER_MODEL = None
WHISPER_MODEL_LOCK = threading.Lock()

jobs = {}
jobs_lock = threading.Lock()

# -------------------------------------------------------------
# Utility function to validate if the provided URL is a supported YouTube or Instagram link
# -------------------------------------------------------------
def is_supported_link(url: str) -> bool:
    pattern = re.compile(
        r"^(https?://)?(www\.)?(youtube\.com|youtu\.be|instagram\.com)/.+$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url.strip()))

# -------------------------------------------------------------
# Utility function to sanitize error messages by removing ANSI escape codes and trimming whitespace
# -------------------------------------------------------------
def sanitize_error_message(message: str) -> str:
    return ANSI_ESCAPE_RE.sub("", message or "").strip()

# -------------------------------------------------------------
# Google Sheets Configuration and Functions
# -------------------------------------------------------------
def get_cookies_from_browser():
    # If a cookie file is configured, prefer it and skip browser-cookie mode.
    if get_cookies_file():
        return None
    browser = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip().lower()
    if browser in {"chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi"}:
        return (browser,)
    return None

# ------------------------------------------------------------- 
# Get the cookies file path from environment variable if set and valid
# -------------------------------------------------------------
def get_cookies_file() -> str:
    cookies_file = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    if not cookies_file:
        return ""
    expanded = os.path.expandvars(cookies_file)
    expanded = os.path.expanduser(expanded)
    return expanded if Path(expanded).exists() else ""

# -------------------------------------------------------------
# Build yt-dlp options based on environment variables and defaults
# -------------------------------------------------------------
def build_ydl_opts(output_template: str = "", skip_download: bool = False) -> dict:
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        },
    }
    if output_template:
        opts["outtmpl"] = output_template
    if skip_download:
        opts["skip_download"] = True

    cookies_file = get_cookies_file()
    if cookies_file:
        opts["cookiefile"] = cookies_file
    else:
        cookies = get_cookies_from_browser()
        if cookies:
            opts["cookiesfrombrowser"] = cookies
    return opts

# -------------------------------------------------------------
# Humanize yt-dlp download errors for better user feedback
# -------------------------------------------------------------
def humanize_download_error(err: Exception) -> str:
    text = sanitize_error_message(str(err)).lower()
    if "accounts/login" in text or "login required" in text or "authentication" in text:
        return (
            "This Instagram link requires login. Set YTDLP_COOKIES_FROM_BROWSER "
            "to your browser name (for example: chrome) and try again."
        )
    if "http error 403" in text or "forbidden" in text:
        return (
            "The source blocked direct download (HTTP 403). Update yt-dlp and retry. "
            "If it still fails, set YTDLP_COOKIES_FROM_BROWSER=chrome and try again."
        )
    if "unsupported url" in text:
        return "Unsupported or private link. Use a public YouTube/Instagram video or reel URL."
    return sanitize_error_message(str(err))

# -------------------------------------------------------------
# Detect the platform (YouTube or Instagram) based on the URL
# -------------------------------------------------------------
def is_cookie_db_lock_error(err: Exception) -> bool:
    text = sanitize_error_message(str(err)).lower()
    return "could not copy chrome cookie database" in text or "cookies" in text and "database" in text

# -------------------------------------------------------------
# Update the job status in the global jobs dictionary
# -------------------------------------------------------------
def update_job(job_id: str, **kwargs):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)

# -------------------------------------------------------------
# Detect the platform (YouTube or Instagram) based on the URL
# -------------------------------------------------------------
def save_transcript_to_file(transcript: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"transcript_{timestamp}.txt"
    output_path.write_text(transcript, encoding="utf-8")
    return output_path

# -------------------------------------------------------------
# save the extracted information into md file
# -------------------------------------------------------------
def save_groq_summary_to_md(qa_summary: str, description: str = "", transcript: str = "") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = GROQ_SUMMARY_DIR / f"AI_summary_{timestamp}.md"
    md_body = (
        "# AI Summary\n\n"
        "## Video/Reel Description\n"
        f"{description.strip() if description else 'Not available'}\n\n"
        "## Transcript\n"
        f"{transcript.strip() if transcript else 'Not available'}\n\n"
        "## Detailed Q&A Summary\n"
        f"{qa_summary.strip() if qa_summary else 'Not available'}\n"
    )
    output_path.write_text(md_body, encoding="utf-8")
    return output_path

# -------------------------------------------------------------
# extract the audio from the given URL
# -------------------------------------------------------------
def download_audio(url: str, job_id: str) -> Path:
    media_id = str(uuid.uuid4())
    output_template = str(DOWNLOADS_DIR / f"ExtractedAudio_{media_id}.%(ext)s")

    def progress_hook(data):
        status = data.get("status")
        if status == "downloading":
            percent_text = str(data.get("_percent_str", "0")).replace("%", "").strip()
            try:
                raw_percent = float(percent_text)
            except ValueError:
                raw_percent = 0.0
            mapped = 35 + int((raw_percent / 100.0) * 25)  # 35 -> 60
            update_job(
                job_id,
                progress=max(35, min(mapped, 60)),
                step=f"Extracting audio from link... {int(raw_percent)}%",
            )
        elif status == "finished":
            update_job(job_id, progress=62, step="Finalizing extracted audio...")

    ydl_opts = build_ydl_opts(output_template=output_template)
    ydl_opts["postprocessors"] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]
    ydl_opts["progress_hooks"] = [progress_hook]

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except DownloadError as err:
        if is_cookie_db_lock_error(err):
            # Retry once without browser cookies when Chrome locks the cookie DB.
            ydl_opts_no_cookies = dict(ydl_opts)
            ydl_opts_no_cookies.pop("cookiesfrombrowser", None)
            update_job(
                job_id,
                step="Chrome cookies are locked. Retrying download without browser cookies...",
            )
            try:
                with YoutubeDL(ydl_opts_no_cookies) as ydl:
                    ydl.download([url])
            except DownloadError as err2:
                raise RuntimeError(humanize_download_error(err2)) from err2
        else:
            raise RuntimeError(humanize_download_error(err)) from err

    mp3_path = DOWNLOADS_DIR / f"ExtractedAudio_{media_id}.mp3"
    if not mp3_path.exists():
        raise FileNotFoundError("Audio extraction failed. Ensure ffmpeg is installed and on PATH.")

    return mp3_path

# -------------------------------------------------------------
# Extract video description using yt-dlp
# -------------------------------------------------------------
def extract_video_description(url: str) -> str:
    ydl_opts = build_ydl_opts(skip_download=True)
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as err:
        if is_cookie_db_lock_error(err):
            ydl_opts_no_cookies = dict(ydl_opts)
            ydl_opts_no_cookies.pop("cookiesfrombrowser", None)
            try:
                with YoutubeDL(ydl_opts_no_cookies) as ydl:
                    info = ydl.extract_info(url, download=False)
            except DownloadError:
                return ""
        else:
            return ""

    description = (info or {}).get("description")
    return str(description).strip() if description else ""

# -------------------------------------------------------------
# Return the transcript text from the extracted audio using OpenAI's Whisper model
# -------------------------------------------------------------
def transcribe_audio(audio_path: Path, job_id: str) -> str:
    global WHISPER_MODEL
    with WHISPER_MODEL_LOCK:
        if WHISPER_MODEL is None:
            WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME)

    done = threading.Event()
    holder = {"result": None, "error": None}

    def run_transcription():
        try:
            holder["result"] = WHISPER_MODEL.transcribe(
                str(audio_path),
                fp16=False,
                condition_on_previous_text=False,
                temperature=0,
            )
        except Exception as exc:
            holder["error"] = exc
        finally:
            done.set()

    thread = threading.Thread(target=run_transcription, daemon=True)
    thread.start()

    live_progress = 65
    reached_plateau = False
    while not done.is_set():
        if live_progress < 82:
            live_progress += 1
            update_job(
                job_id,
                progress=live_progress,
                step=f"Creating transcription for extracted audio... {live_progress}%",
            )
        elif not reached_plateau:
            reached_plateau = True
            update_job(
                job_id,
                progress=82,
                step="Finalizing transcription for extracted audio...",
            )
        time.sleep(1.2)

    if holder["error"] is not None:
        raise holder["error"]

    result = holder["result"]
    return result.get("text", "").strip()

# -------------------------------------------------------------
# Analyze the transcript using OpenAI's GROQ API and return a detailed Q&A summary
# -------------------------------------------------------------
def read_env_key_fallback(key: str) -> str:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return ""
    try:
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip("\"'").strip()
    except Exception:
        return ""
    return ""

# -------------------------------------------------------------
# Analyze the transcript using OpenAI's GROQ API and return a detailed Q&A summary
# -------------------------------------------------------------
def analyze_transcript(transcript: str, description: str = "") -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        env_map = dotenv_values(BASE_DIR / ".env")
        api_key = str(env_map.get("GROQ_API_KEY", "")).strip()
    if not api_key:
        api_key = read_env_key_fallback("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to your environment before analysis.")

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    prompt = (
        "You are an expert analyst. Analyze the transcript and return a detailed summary in "
        "Question and Answer format. Include at least 10 Q&A items. Cover key themes, "
        "important facts, action items, risks, and conclusions."
    )

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Video/Reel description (if any):\n{description or 'Not available'}\n\n"
                    f"Transcript:\n\n{transcript}"
                ),
            },
        ],
    )
    return response.output_text.strip()

# -------------------------------------------------------------
# analysis the description only using OpenAI's GROQ API and return a detailed Q&A summary
# -------------------------------------------------------------
def analyze_description_only(description: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        env_map = dotenv_values(BASE_DIR / ".env")
        api_key = str(env_map.get("GROQ_API_KEY", "")).strip()
    if not api_key:
        api_key = read_env_key_fallback("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to your environment before analysis.")

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    prompt = (
        "You are an expert analyst. The user provided only a video/reel description and no spoken transcript. "
        "Create a detailed summary in Question and Answer format with at least 8 Q&A items. "
        "Cover key themes, likely intent, important highlights, action points, and concise conclusions. "
        "If some details are uncertain, mark them as inferred."
    )

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Video/Reel description:\n\n{description or 'Not available'}",
            },
        ],
    )
    return response.output_text.strip()

# -------------------------------------------------------------
# Combine the extracted information and output the data
# to Google Sheets for record-keeping and further processing
# -------------------------------------------------------------
def process_link(job_id: str, source_url: str):
    try:
        audio_path = None

        update_job(job_id, state="running", progress=10, step="Extracting video/reel description...")
        video_description = extract_video_description(source_url)

        update_job(job_id, progress=35, step="Extracting audio from link...")
        audio_path = download_audio(source_url, job_id)

        update_job(job_id, progress=65, step="Creating transcription for extracted audio...")
        transcript = transcribe_audio(audio_path, job_id)
        transcript_file = ""

        if not transcript:
            update_job(job_id, progress=85, step="Transcription is empty. Extracted only description")
            qa_summary = analyze_description_only(video_description)
        else:
            transcript_file = str(save_transcript_to_file(transcript))
            update_job(job_id, progress=85, step="Analyzing transcription and generating Q&A summary...")
            qa_summary = analyze_transcript(transcript, video_description)
        summary_file = save_groq_summary_to_md(
            qa_summary=qa_summary,
            description=video_description,
            transcript=transcript,
        )

        update_job(
            job_id,
            state="completed",
            progress=100,
            step="Completed",
            transcript=transcript,
            qa_summary=qa_summary,
            video_description=video_description,
            transcript_file=transcript_file,
            summary_file=str(summary_file),
            error="",
        )

        # Write data to Google Sheet
        write_to_google_sheet(
            source_url=source_url,
            description=video_description,
            transcript=transcript,
            qa_summary=qa_summary
        )
    except Exception as exc:
        update_job(
            job_id,
            state="error",
            progress=100,
            step="Failed",
            error=sanitize_error_message(str(exc)),
        )
    finally:
        try:
            if audio_path and audio_path.exists():
                audio_path.unlink()

        except Exception as cleanup_error:
            print(f"Cleanup Error: {cleanup_error}")
# -------------------------------------------------------------
# Home page route to render the main interface
# -------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html")

# -------------------------------------------------------------
# Endpoint to process the provided YouTube or Instagram link
# ------------------------------------------------------------- 
@app.post("/process")
def process():
    payload = request.get_json(silent=True) or {}
    source_url = (payload.get("source_url") or "").strip()

    if not source_url:
        return jsonify({"ok": False, "error": "Please enter a YouTube or Instagram link."}), 400
    if not is_supported_link(source_url):
        return jsonify({"ok": False, "error": "Only YouTube or Instagram links are supported."}), 400

    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {
            "state": "pending",
            "progress": 0,
            "step": "Queued",
            "error": "",
            "transcript": "",
            "qa_summary": "",
            "video_description": "",
            "transcript_file": "",
            "summary_file": "",
        }

    thread = threading.Thread(target=process_link, args=(job_id, source_url), daemon=True)
    thread.start()
    return jsonify({"ok": True, "job_id": job_id})

# -------------------------------------------------------------
# Endpoint to check the status of a job
# -------------------------------------------------------------
@app.get("/status/<job_id>")
def status(job_id: str):
    with jobs_lock:
        data = jobs.get(job_id)
    if not data:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    return jsonify({"ok": True, **data})

# -------------------------------------------------------------
# Run the Flask app
# -------------------------------------------------------------
if __name__ == "__main__":
    #app.run(debug=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
