"""
Transcript service using OpenAI Whisper API.
Accepts a recording URL, downloads the audio, and returns transcription as phrases (segments).
"""
import io
import logging
import requests
from openai import OpenAI

logger = logging.getLogger(__name__)


class TranscriptService:
    def __init__(self, api_key: str | None = None):
        self.client = OpenAI(api_key=api_key)
        self.logger = logger

    def get_transcript(self, recording_url: str, timeout_seconds: int = 120) -> dict:
        """
        Fetch audio from recording_url, transcribe with Whisper, return text by phrases (segments).

        Args:
            recording_url: URL of the audio file (e.g. MP3). Must be publicly reachable or
                          your proxy URL that serves the recording.
            timeout_seconds: Timeout for downloading the recording and for the Whisper request.

        Returns:
            {
                "text": str,           # Full transcript
                "segments": [          # Phrase-level segments (not word-level)
                    {"start": float, "end": float, "text": str},
                    ...
                ],
                "language": str | None,
                "duration": float | None
            }
        """
        if not recording_url or not recording_url.strip():
            return {"text": "", "segments": [], "language": None, "duration": None}

        try:
            self.logger.info("Downloading recording from %s", recording_url)
            resp = requests.get(recording_url, timeout=timeout_seconds)
            resp.raise_for_status()
            audio_bytes = resp.content

            if not audio_bytes:
                self.logger.warning("Empty audio from %s", recording_url)
                return {"text": "", "segments": [], "language": None, "duration": None}

            # Whisper expects a file-like object; use bytes buffer
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "recording.mp3"

            # Request phrase-level (segment) timestamps, not word-level
            transcription = self.client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

            # Build segments as list of { start, end, text }
            segments = []
            raw_segments = getattr(transcription, "segments", None) or []
            for seg in raw_segments:
                segments.append({
                    "start": getattr(seg, "start", 0.0),
                    "end": getattr(seg, "end", 0.0),
                    "text": (getattr(seg, "text", "") or "").strip(),
                })

            full_text = getattr(transcription, "text", "") or ""
            language = getattr(transcription, "language", None)
            duration = getattr(transcription, "duration", None)

            return {
                "text": full_text,
                "segments": segments,
                "language": language,
                "duration": duration,
            }

        except requests.RequestException as e:
            self.logger.error("Failed to download recording from %s: %s", recording_url, e)
            raise
        except Exception as e:
            self.logger.error("Whisper transcription failed for %s: %s", recording_url, e)
            raise
