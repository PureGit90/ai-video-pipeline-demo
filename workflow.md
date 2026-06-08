# AI Video Pipeline — Architecture

```mermaid
flowchart TD
    A([Script Text Input]) --> B[ElevenLabs TTS API\nvoice_id + text → MP3]
    A --> C{HeyGen API Key\nset?}

    C -->|Yes| D[HeyGen v2\nvideo/generate\nAvatar + script → video_id]
    C -->|No| E[Demo Mode\nstatic thumbnail.jpg]

    D --> F{Poll\nvideo_status.get\nevery ~30s}
    F -->|pending / processing| F
    F -->|completed| G[Download\navatar_video.mp4]
    F -->|failed| H([Error: check avatar_id])

    B --> I[voiceover.mp3]
    G --> J[FFmpeg merge\n-map 0:v:0 -map 1:a:0\nfinal_video.mp4]
    I --> J

    E --> K[FFmpeg demo\n-loop 1 -tune stillimage\ndemo_video.mp4]
    I --> K

    A --> L[Claude API\nclaude-haiku-4-5\nYouTube metadata]
    L --> M[title + description + tags JSON]

    J --> N([Download MP4\n+ Metadata])
    K --> N
```

## Step-by-step

| Step | Service | Endpoint | Async? |
|------|---------|----------|--------|
| 1 | ElevenLabs | `POST /v1/text-to-speech/{voice_id}` | No (sync) |
| 2 | HeyGen | `POST /v2/video/generate` | Yes — poll |
| 2b | HeyGen | `GET /v1/video_status.get?video_id=` | Poll until `completed` |
| 3 | Claude (Haiku) | Anthropic Messages API | No (sync) |
| 4 | FFmpeg (local) | subprocess | No (sync) |

## HeyGen timing notes

- Typical processing time: **2-3 minutes** for a 60-90 second video
- Maximum wait recommended: 10 minutes
- If status stays `pending` after 10 min, re-submit or check HeyGen dashboard
- HeyGen does not push webhooks in the free tier — polling is required
