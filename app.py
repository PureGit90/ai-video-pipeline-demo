"""
app.py — Streamlit UI for the AI Video Pipeline demo.
Script → ElevenLabs TTS → HeyGen Avatar → FFmpeg Merge → YouTube-ready MP4
"""

import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

from pipeline import (
    generate_voiceover,
    generate_mock_audio,
    submit_heygen_video,
    poll_heygen_status,
    download_heygen_video,
    generate_metadata,
    assemble_with_ffmpeg,
    assemble_demo_mode,
)

# ---------------------------------------------------------------------------
# Config / constants
# ---------------------------------------------------------------------------

VOICES = {
    "Rachel (warm, clear)": "21m00Tcm4TlvDq8ikWAM",
    "Adam (authoritative)": "pNInz6obpgDQGcFmaJgB",
    "Bella (friendly)": "EXAVITQu4vr4xnSDxMaL",
    "Antoni (professional)": "ErXwobaYiN019PkySvjV",
}

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

SAMPLE_SCRIPT_PATH = BASE_DIR / "sample_data" / "sample_script.txt"
THUMBNAIL_PATH = BASE_DIR / "sample_data" / "thumbnail.jpg"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Video Pipeline",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for a cleaner look
st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    .block-container { padding-top: 2rem; }
    h1 { color: #ffffff; }
    .status-box {
        background: #1e2130;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .pipeline-step {
        font-size: 0.9rem;
        padding: 0.3rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

defaults = {
    "video_id": None,
    "heygen_status": None,
    "final_video_path": None,
    "metadata": None,
    "audio_path": None,
    "avatar_video_path": None,
    "pipeline_log": [],
    "running": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def log(msg: str):
    st.session_state.pipeline_log.append(msg)


# ---------------------------------------------------------------------------
# Env key helpers
# ---------------------------------------------------------------------------

def get_key(env_name: str, label: str) -> str | None:
    val = os.getenv(env_name, "").strip()
    return val if val else None


ELEVENLABS_KEY = get_key("ELEVENLABS_API_KEY", "ElevenLabs API key")
HEYGEN_KEY = get_key("HEYGEN_API_KEY", "HeyGen API key")
HEYGEN_AVATAR = os.getenv("HEYGEN_AVATAR_ID", "").strip() or "default_avatar_id"
ANTHROPIC_KEY = get_key("ANTHROPIC_API_KEY", "Anthropic API key")

DEMO_MODE = not bool(HEYGEN_KEY)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("AI Video Pipeline")
st.caption("Script → ElevenLabs Voiceover → HeyGen Avatar → FFmpeg Assembly → YouTube-ready MP4")

if DEMO_MODE:
    st.caption("Sample output — pipeline runs end to end with placeholder audio and thumbnail.")

st.divider()

# ---------------------------------------------------------------------------
# Two-column layout
# ---------------------------------------------------------------------------

col_left, col_right = st.columns([1, 1], gap="large")

# ===========================================================================
# LEFT COLUMN — Inputs
# ===========================================================================

with col_left:
    st.subheader("Script & Settings")

    # Load sample script
    sample_text = ""
    if SAMPLE_SCRIPT_PATH.exists():
        sample_text = SAMPLE_SCRIPT_PATH.read_text().strip()

    script = st.text_area(
        "Video Script",
        value=sample_text,
        height=280,
        placeholder="Paste your video script here...",
        help="This text will be converted to voiceover AND used for the HeyGen avatar.",
    )

    st.markdown("**Voice Settings**")
    voice_label = st.selectbox(
        "ElevenLabs Voice",
        options=list(VOICES.keys()),
        index=0,
    )
    voice_id = VOICES[voice_label]
    st.caption(f"Voice ID: `{voice_id}`")

    if not DEMO_MODE:
        avatar_id_input = st.text_input(
            "HeyGen Avatar ID",
            value=HEYGEN_AVATAR,
            help="Find your avatar ID in your HeyGen dashboard.",
        )
    else:
        avatar_id_input = HEYGEN_AVATAR
        st.caption("HeyGen avatar: skipped (Demo Mode)")

    el_ok = bool(ELEVENLABS_KEY)
    an_ok = bool(ANTHROPIC_KEY)

    st.divider()
    generate_btn = st.button(
        "Generate Video",
        type="primary",
        use_container_width=True,
        disabled=not script.strip(),
    )

# ===========================================================================
# RIGHT COLUMN — Pipeline status + output
# ===========================================================================

with col_right:
    st.subheader("Pipeline Status")

    # Render past logs
    if st.session_state.pipeline_log:
        for entry in st.session_state.pipeline_log:
            st.markdown(f"- {entry}")

    # -------------------------------------------------------------------
    # MAIN PIPELINE — runs on button click
    # -------------------------------------------------------------------
    if generate_btn and script.strip():
        st.session_state.pipeline_log = []
        st.session_state.video_id = None
        st.session_state.heygen_status = None
        st.session_state.final_video_path = None
        st.session_state.metadata = None
        st.session_state.audio_path = None
        st.session_state.avatar_video_path = None

        # ---------------------------------------------------------------
        # Step 1 — ElevenLabs voiceover
        # ---------------------------------------------------------------
        with st.spinner("Step 1/4 — Generating voiceover (ElevenLabs)..."):
            if el_ok:
                try:
                    audio_path = generate_voiceover(script, voice_id, ELEVENLABS_KEY)
                    st.session_state.audio_path = audio_path
                    st.success(f"Voiceover saved: `output/voiceover.mp3`")
                    log("Step 1 — Voiceover generated (ElevenLabs)")
                except Exception as e:
                    st.error(f"ElevenLabs error: {e}")
                    log(f"Step 1 — FAILED: {e}")
                    st.stop()
            else:
                try:
                    audio_path = generate_mock_audio(duration_secs=8)
                    st.session_state.audio_path = audio_path
                    st.success("Voiceover ready (sample audio — add ELEVENLABS_API_KEY for real TTS)")
                    log("Step 1 — Sample audio generated (demo mode)")
                except Exception as e:
                    st.warning(f"Could not generate sample audio: {e}")
                    log(f"Step 1 — Sample audio failed: {e}")

        # ---------------------------------------------------------------
        # Step 2 — HeyGen avatar submit (or demo mode)
        # ---------------------------------------------------------------
        if not DEMO_MODE:
            with st.spinner("Step 2/4 — Submitting HeyGen avatar job..."):
                try:
                    video_id = submit_heygen_video(script, avatar_id_input, HEYGEN_KEY)
                    st.session_state.video_id = video_id
                    st.success(f"HeyGen job submitted — video_id: `{video_id}`")
                    st.info(
                        "HeyGen is processing your avatar video. This usually takes **2-3 minutes**. "
                        "Click **Check HeyGen Status** below when ready.",
                        icon="⏳",
                    )
                    log(f"Step 2 — HeyGen submitted, video_id={video_id}")
                except Exception as e:
                    st.error(f"HeyGen submit error: {e}")
                    log(f"Step 2 — FAILED: {e}")
        else:
            st.info("Step 2 — Demo Mode: HeyGen skipped. Will use thumbnail + audio.", icon="🎭")
            log("Step 2 — Skipped (Demo Mode)")

        # ---------------------------------------------------------------
        # Step 3 — Metadata via Claude
        # ---------------------------------------------------------------
        with st.spinner("Step 3/4 — Generating YouTube metadata (Claude)..."):
            if an_ok:
                try:
                    metadata = generate_metadata(script, ANTHROPIC_KEY)
                    st.session_state.metadata = metadata
                    log("Step 3 — Metadata generated (Claude)")
                    st.success("Metadata generated.")
                except Exception as e:
                    st.error(f"Metadata generation error: {e}")
                    log(f"Step 3 — FAILED: {e}")
            else:
                fallback_meta = {
                    "title": "AI Productivity Tools: Transform Your Workflow",
                    "description": (
                        "Discover how cutting-edge AI tools are transforming productivity "
                        "for professionals everywhere. In this video, we explore the latest "
                        "innovations in automation and workflow optimization."
                    ),
                    "tags": ["AI", "productivity", "automation", "workflow", "tools"],
                }
                st.session_state.metadata = fallback_meta
                st.info("Step 3 — Using fallback metadata (no Anthropic key).")
                log("Step 3 — Fallback metadata used")

        # ---------------------------------------------------------------
        # Step 4 — FFmpeg assembly (demo mode only; full mode needs poll)
        # ---------------------------------------------------------------
        if DEMO_MODE and st.session_state.audio_path:
            with st.spinner("Step 4/4 — Assembling video with FFmpeg..."):
                # Auto-generate thumbnail if missing
                if not THUMBNAIL_PATH.exists():
                    try:
                        import subprocess as _sp
                        _sp.run(["python3", str(BASE_DIR / "make_thumbnail.py")],
                                capture_output=True, timeout=15)
                    except Exception:
                        pass
                thumb = str(THUMBNAIL_PATH) if THUMBNAIL_PATH.exists() else None
                final_path = str(OUTPUT_DIR / "demo_video.mp4")
                if thumb:
                    try:
                        assemble_demo_mode(
                            st.session_state.audio_path,
                            thumb,
                            final_path,
                        )
                        st.session_state.final_video_path = final_path
                        st.success("Demo video assembled.")
                        log("Step 4 — Demo video assembled (FFmpeg + thumbnail)")
                    except Exception as e:
                        st.error(f"FFmpeg error: {e}")
                        log(f"Step 4 — FFmpeg FAILED: {e}")
                else:
                    st.info("Step 4 — Add `sample_data/thumbnail.jpg` to enable video assembly.")
                    log("Step 4 — Skipped (no thumbnail)")
        elif not DEMO_MODE:
            log("Step 4 — Waiting for HeyGen (use Check Status button)")

    # -------------------------------------------------------------------
    # HeyGen polling section (only when a video_id is stored)
    # -------------------------------------------------------------------
    if st.session_state.video_id and not DEMO_MODE:
        st.divider()
        st.markdown(f"**HeyGen Video ID:** `{st.session_state.video_id}`")

        if st.session_state.heygen_status == "completed":
            st.success("HeyGen avatar video is ready.")
        elif st.session_state.heygen_status == "failed":
            st.error("HeyGen processing failed. Check your avatar_id and API key.")
        else:
            check_btn = st.button("Check HeyGen Status", use_container_width=True)
            if check_btn:
                with st.spinner("Polling HeyGen..."):
                    try:
                        status, video_url = poll_heygen_status(
                            st.session_state.video_id, HEYGEN_KEY
                        )
                        st.session_state.heygen_status = status
                        log(f"HeyGen poll — status={status}")

                        if status == "completed" and video_url:
                            st.success(f"HeyGen complete! Downloading avatar video...")
                            with st.spinner("Downloading HeyGen video..."):
                                avatar_path = download_heygen_video(video_url)
                                st.session_state.avatar_video_path = avatar_path
                                log(f"HeyGen video downloaded: {avatar_path}")

                            # Now assemble if we also have audio
                            if st.session_state.audio_path:
                                with st.spinner("Assembling final video with FFmpeg..."):
                                    final_path = str(OUTPUT_DIR / "final_video.mp4")
                                    try:
                                        assemble_with_ffmpeg(
                                            st.session_state.audio_path,
                                            avatar_path,
                                            final_path,
                                        )
                                        st.session_state.final_video_path = final_path
                                        log("Step 4 — Final video assembled (FFmpeg)")
                                        st.success("Final video assembled.")
                                    except Exception as e:
                                        st.error(f"FFmpeg error: {e}")
                                        log(f"Step 4 — FFmpeg FAILED: {e}")
                            else:
                                # Use avatar video as-is (no TTS overlay)
                                st.session_state.final_video_path = avatar_path
                                log("Step 4 — Using HeyGen video directly (no TTS audio)")

                        elif status in ("pending", "processing"):
                            st.info(
                                f"Still processing (status: **{status}**). "
                                "Check again in ~30 seconds.",
                                icon="⏳",
                            )
                        elif status == "failed":
                            st.error("HeyGen processing failed.")
                        else:
                            st.warning(f"Unknown status: {status}")

                    except Exception as e:
                        st.error(f"Polling error: {e}")
                        log(f"Poll error: {e}")

    # -------------------------------------------------------------------
    # Final output section
    # -------------------------------------------------------------------
    if st.session_state.final_video_path and Path(st.session_state.final_video_path).exists():
        st.divider()
        st.subheader("Output")

        video_path = Path(st.session_state.final_video_path)
        video_bytes = video_path.read_bytes()

        # Playback preview
        st.video(video_bytes)

        # Download button
        st.download_button(
            label="Download MP4",
            data=video_bytes,
            file_name=video_path.name,
            mime="video/mp4",
            use_container_width=True,
            type="primary",
        )

        # YouTube metadata
        if st.session_state.metadata:
            st.markdown("**Suggested YouTube Metadata**")
            meta = st.session_state.metadata
            st.text_input("Title", value=meta.get("title", ""), key="meta_title")
            st.text_area(
                "Description",
                value=meta.get("description", ""),
                height=120,
                key="meta_desc",
            )
            tags = meta.get("tags", [])
            if isinstance(tags, list):
                tags_str = ", ".join(tags)
            else:
                tags_str = str(tags)
            st.text_input("Tags", value=tags_str, key="meta_tags")
