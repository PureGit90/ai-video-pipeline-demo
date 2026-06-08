"""
pipeline.py — Core pipeline logic for the AI Video Workflow demo.
Handles: ElevenLabs TTS, HeyGen avatar video, Claude metadata, FFmpeg assembly.
"""

import os
import time
import subprocess
import json
import requests
from pathlib import Path


# ---------------------------------------------------------------------------
# ElevenLabs
# ---------------------------------------------------------------------------

def generate_voiceover(script: str, voice_id: str, api_key: str) -> str:
    """
    Call ElevenLabs TTS API and save audio to output/voiceover.mp3.
    Returns the path to the saved mp3.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    audio_path = output_dir / "voiceover.mp3"

    with open(audio_path, "wb") as f:
        f.write(resp.content)

    return str(audio_path)


# ---------------------------------------------------------------------------
# HeyGen
# ---------------------------------------------------------------------------

def submit_heygen_video(script: str, avatar_id: str, api_key: str) -> str:
    """
    Submit an async HeyGen video generation job.
    Returns the video_id string.
    """
    url = "https://api.heygen.com/v2/video/generate"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                },
                "background": {
                    "type": "color",
                    "value": "#FAFAFA",
                },
            }
        ],
        "dimension": {"width": 1920, "height": 1080},
    }

    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # HeyGen v2 response: {"data": {"video_id": "..."}}
    video_id = data.get("data", {}).get("video_id") or data.get("video_id")
    if not video_id:
        raise ValueError(f"HeyGen did not return a video_id. Response: {data}")
    return video_id


def poll_heygen_status(video_id: str, api_key: str) -> tuple[str, str | None]:
    """
    Poll HeyGen for the status of a video job.
    Returns (status, video_url). video_url is None until status == "completed".
    Possible statuses: pending, processing, completed, failed.
    """
    url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
    headers = {"X-Api-Key": api_key}

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    status = (
        data.get("data", {}).get("status")
        or data.get("status")
        or "unknown"
    )
    video_url = (
        data.get("data", {}).get("video_url")
        or data.get("video_url")
    )
    return status, video_url


def download_heygen_video(video_url: str) -> str:
    """
    Download the completed HeyGen video to output/avatar_video.mp4.
    Returns the local file path.
    """
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    video_path = output_dir / "avatar_video.mp4"

    resp = requests.get(video_url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(video_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return str(video_path)


# ---------------------------------------------------------------------------
# Claude — metadata generation
# ---------------------------------------------------------------------------

def generate_metadata(script: str, api_key: str) -> dict:
    """
    Use Claude (claude-haiku-4-5) to generate YouTube title, description, and tags.
    Returns {"title": str, "description": str, "tags": list[str]}.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are a YouTube SEO expert. Given the following video script, generate:
1. A compelling YouTube video title (max 70 characters)
2. A YouTube description (150-200 words, include relevant keywords)
3. A list of 10 relevant tags

Script:
{script}

Respond with valid JSON only, no markdown fences:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Mock audio (demo mode — no ElevenLabs key)
# ---------------------------------------------------------------------------

def generate_mock_audio(duration_secs: int = 8) -> str:
    """Create a short silent mp3 using FFmpeg for demo mode (no ElevenLabs key needed)."""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    audio_path = output_dir / "voiceover.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(duration_secs),
        "-q:a", "9",
        "-acodec", "libmp3lame",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Mock audio generation failed:\n{result.stderr}")
    return str(audio_path)


# ---------------------------------------------------------------------------
# FFmpeg assembly
# ---------------------------------------------------------------------------

def assemble_with_ffmpeg(audio_path: str, video_path: str, output_path: str) -> str:
    """
    Merge avatar video + voiceover audio into final_video.mp4 using FFmpeg.
    The avatar video's original audio (if any) is replaced by the TTS voiceover.
    Returns the output path.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")
    return output_path


def assemble_demo_mode(audio_path: str, thumbnail_path: str, output_path: str) -> str:
    """
    Demo mode fallback: combine static thumbnail image + TTS audio into MP4.
    Uses libx264 still-image encoding.
    """
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", thumbnail_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg demo mode failed:\n{result.stderr}")
    return output_path
