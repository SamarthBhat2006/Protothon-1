"""Speech-to-Text service integrating with Sarvam AI.
Supports both standard (<30s) and batch (>30s) transcription modes.
"""
import logging
import aiohttp
import asyncio
import os
import mimetypes

from app.config import settings

logger = logging.getLogger(__name__)

# Sarvam AI Endpoints
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text-translate"
SARVAM_BATCH_URL = "https://api.sarvam.ai/speech-to-text-translate/batch"
SARVAM_BATCH_STATUS_URL = "https://api.sarvam.ai/speech-to-text-translate/batch/{job_id}"

# Audio duration threshold for batch mode (seconds)
BATCH_THRESHOLD_SECONDS = 30


def _estimate_duration_seconds(file_path: str) -> float:
    """Rough estimate of audio duration from file size.
    Assumes ~16 KB/s for compressed audio (MP3/AAC) and ~176 KB/s for WAV.
    """
    size_bytes = os.path.getsize(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".wav":
        return size_bytes / (176 * 1024)
    return size_bytes / (16 * 1024)  # MP3/AAC/FLAC estimate


async def transcribe_audio(file_path: str, language_code: str = "en-IN") -> dict:
    """
    Sends an audio file to Sarvam AI for transcription.
    Automatically detects long audio (>30s) and falls back to batch mode.
    """
    if not settings.SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY is not set. Using mock transcription fallback.")
        return await _mock_transcribe(file_path, language_code)

    if not os.path.exists(file_path):
        logger.error(f"File not found for transcription: {file_path}")
        return {"success": False, "error": "Audio file not found"}

    estimated_duration = _estimate_duration_seconds(file_path)
    logger.info(f"Estimated audio duration: {estimated_duration:.1f}s (threshold: {BATCH_THRESHOLD_SECONDS}s)")

    if estimated_duration > BATCH_THRESHOLD_SECONDS:
        logger.info("Audio exceeds 30s — using Sarvam Batch STT mode")
        return await _transcribe_batch(file_path, language_code)
    else:
        return await _transcribe_standard(file_path, language_code)


async def _transcribe_standard(file_path: str, language_code: str) -> dict:
    """Standard STT for short audio (<30s)."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "audio/mpeg"

    logger.info(f"[Standard STT] Sending {file_path} to Sarvam AI")

    try:
        data = aiohttp.FormData()
        data.add_field('file',
                       open(file_path, 'rb'),
                       filename=os.path.basename(file_path),
                       content_type=mime_type)
        data.add_field('prompt', '')

        headers = {"api-subscription-key": settings.SARVAM_API_KEY}

        async with aiohttp.ClientSession() as session:
            async with session.post(SARVAM_STT_URL, data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Sarvam API Error ({response.status}): {error_text}")
                    return {"success": False, "error": f"API Error {response.status}: {error_text}"}

                result = await response.json()
                transcript = result.get("transcript", "")

                if not transcript:
                    return {"success": False, "error": "Empty transcript received"}

                logger.info("Standard STT transcription successful")
                return {
                    "success": True,
                    "transcript": transcript,
                    "language_code": language_code,
                    "mode": "standard",
                    "mock": False
                }

    except Exception as e:
        logger.error(f"Standard STT failed: {e}")
        return {"success": False, "error": str(e)}


async def _transcribe_batch(file_path: str, language_code: str) -> dict:
    """Batch STT for long audio (>30s). Submits a job and polls for completion."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "audio/mpeg"

    logger.info(f"[Batch STT] Submitting {file_path} for background processing")

    try:
        headers = {"api-subscription-key": settings.SARVAM_API_KEY}

        # Step 1: Submit batch job
        data = aiohttp.FormData()
        data.add_field('file',
                       open(file_path, 'rb'),
                       filename=os.path.basename(file_path),
                       content_type=mime_type)

        async with aiohttp.ClientSession() as session:
            async with session.post(SARVAM_BATCH_URL, data=data, headers=headers) as response:
                if response.status not in (200, 201, 202):
                    error_text = await response.text()
                    logger.error(f"Batch submission error ({response.status}): {error_text}")
                    # Fallback to standard mode on batch error
                    logger.info("Falling back to standard STT mode")
                    return await _transcribe_standard(file_path, language_code)

                job_result = await response.json()
                job_id = job_result.get("job_id") or job_result.get("id")

                if not job_id:
                    logger.warning("Batch job returned no job_id — falling back to standard")
                    return await _transcribe_standard(file_path, language_code)

                logger.info(f"Batch job submitted: {job_id}")

            # Step 2: Poll for completion
            max_polls = 60  # Max ~5 minutes
            poll_interval = 5  # seconds

            for attempt in range(max_polls):
                await asyncio.sleep(poll_interval)

                status_url = SARVAM_BATCH_STATUS_URL.format(job_id=job_id)
                async with session.get(status_url, headers=headers) as status_resp:
                    if status_resp.status != 200:
                        continue

                    status_data = await status_resp.json()
                    job_status = status_data.get("status", "").lower()

                    if job_status == "completed":
                        transcript = status_data.get("transcript", "")
                        if transcript:
                            logger.info(f"Batch job {job_id} completed successfully")
                            return {
                                "success": True,
                                "transcript": transcript,
                                "language_code": language_code,
                                "mode": "batch",
                                "mock": False
                            }
                        return {"success": False, "error": "Batch completed but no transcript"}

                    elif job_status in ("failed", "error"):
                        error_msg = status_data.get("error", "Unknown batch error")
                        logger.error(f"Batch job {job_id} failed: {error_msg}")
                        return {"success": False, "error": f"Batch failed: {error_msg}"}

                    logger.info(f"Batch job {job_id} status: {job_status} (poll {attempt+1}/{max_polls})")

            return {"success": False, "error": "Batch job timed out after 5 minutes"}

    except Exception as e:
        logger.error(f"Batch STT failed: {e}")
        return {"success": False, "error": str(e)}


async def _mock_transcribe(file_path: str, language_code: str) -> dict:
    """Fallback mock transcription for testing without API keys."""
    file_name = os.path.basename(file_path)
    logger.info(f"Mock transcribing {file_name}...")

    await asyncio.sleep(2.0)

    mock_transcript = (
        f"This is a mocked transcript for the file {file_name}. "
        "During this meeting, we discussed the urgent need to refactor the login page to support OAuth. "
        "It was decided that Sarah will handle the backend API integration by next Tuesday. "
        "Also, we saw some latency issues with the database queries that David needs to investigate immediately as a high priority bug. "
        "The team agreed to implement API rate limiting before the public launch."
    )

    return {
        "success": True,
        "transcript": mock_transcript,
        "language_code": language_code,
        "mode": "mock",
        "mock": True
    }