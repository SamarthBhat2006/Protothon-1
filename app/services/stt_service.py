"""Speech-to-Text service integrating with Sarvam AI."""
import logging
import aiohttp
import os
import mimetypes

from app.config import settings

logger = logging.getLogger(__name__)

# Sarvam AI STT Endpoint
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text-translate"

async def transcribe_audio(file_path: str, language_code: str = "en-IN") -> dict:
    """
    Sends an audio file to Sarvam AI for transcription.
    
    Args:
        file_path: Absolute path to the saved audio file
        language_code: The source language code
        
    Returns:
        Dictionary with success status, transcript, and mock flag.
    """
    if not settings.SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY is not set. Using mock transcription fallback.")
        return await _mock_transcribe(file_path, language_code)

    if not os.path.exists(file_path):
        logger.error(f"File not found for transcription: {file_path}")
        return {"success": False, "error": "Audio file not found"}

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "audio/mpeg" # Fallback

    logger.info(f"Sending {file_path} to Sarvam AI (Lang: {language_code}, MIME: {mime_type})")

    try:
        # Sarvam expects multipart/form-data
        data = aiohttp.FormData()
        data.add_field('file',
                       open(file_path, 'rb'),
                       filename=os.path.basename(file_path),
                       content_type=mime_type)
        data.add_field('prompt', '')  # Optional prompt
        # Note: The actual endpoint parameters might vary slightly based on Sarvam's latest docs.
        # Ensure we pass the API key in the header.

        headers = {
            "api-subscription-key": settings.SARVAM_API_KEY
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(SARVAM_STT_URL, data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Sarvam AI API Error ({response.status}): {error_text}")
                    return {"success": False, "error": f"API Error {response.status}: {error_text}"}

                result = await response.json()
                transcript = result.get("transcript", "")
                
                if not transcript:
                    logger.warning("Sarvam returned an empty transcript")
                    return {"success": False, "error": "Empty transcript received"}
                
                logger.info("Successfully transcribed audio with Sarvam AI")
                return {
                    "success": True, 
                    "transcript": transcript,
                    "language_code": language_code,
                    "mock": False
                }

    except Exception as e:
        logger.error(f"Failed to communicate with Sarvam AI: {e}")
        return {"success": False, "error": str(e)}

async def _mock_transcribe(file_path: str, language_code: str) -> dict:
    """Fallback mock transcription for testing without API keys."""
    import asyncio
    
    file_name = os.path.basename(file_path)
    logger.info(f"Mock transcribing {file_name}...")
    
    # Simulate processing time based on file size (mock)
    await asyncio.sleep(2.0)
    
    mock_transcript = (
        f"This is a mocked transcript for the file {file_name}. "
        "During this meeting, we discussed the urgent need to refactor the login page to support OAuth. "
        "It was decided that Sarah will handle the backend API integration by next Tuesday. "
        "Also, we saw some latency issues with the database queries that David needs to investigate immediately as a high priority bug."
    )
    
    return {
        "success": True,
        "transcript": mock_transcript,
        "language_code": language_code,
        "mock": True
    }