"""app/api.py file for FastAPI application handling chat and feedback endpoints."""

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from app.bot import chat as bot_chat
from app.bot import translate_to_english, index
from pydantic import BaseModel
import json
import csv
import os
from datetime import datetime
from pydantic import BaseModel
import re
from deep_translator import GoogleTranslator

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str


class FeedbackRequest(BaseModel):
    message_id: str
    user_message: str
    bot_response: str
    feedback: str  # "good" or "bad"
    session_id: str
    timestamp: str


@router.post("/chat/")
@router.post("/chat")
async def chat_post(request: ChatRequest, http_request: Request):
    """Real-time streaming endpoint that respects abort signals"""

    async def generate():
        try:
            full_response = ""
            async for chunk in bot_chat(request.message):
                # Check if client disconnected
                if await http_request.is_disconnected():
                    print("Client disconnected, stopping response generation")
                    #####################################
                    disconnect_data = {
                        "type": "error",
                        "message": "Client disconnected before completion",
                    }
                    yield f"data: {json.dumps(disconnect_data)}\n\n"
                    ######################################
                    return

                full_response += chunk

                # Send chunk as JSON for easier parsing on frontend
                chunk_data = {"chunk": chunk, "type": "content"}
                yield f"data: {json.dumps(chunk_data)}\n\n"

                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)

            # Send completion signal
            completion_data = {"type": "complete", "full_response": full_response}
            yield f"data: {json.dumps(completion_data)}\n\n"

        except asyncio.CancelledError:
            # Handle cancellation gracefully
            stop_data = {"type": "stopped", "message": "Response stopped by user"}
            yield f"data: {json.dumps(stop_data)}\n\n"
            return
        except Exception as e:
            # Handle other exceptions
            error_data = {"type": "error", "message": f"An error occurred: {str(e)}"}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/chat/")
async def chat_get(prompt: str, request: Request):
    """GET endpoint for streaming (keeping for compatibility)"""

    async def generate():
        try:
            async for text in bot_chat(prompt):
                if await request.is_disconnected():
                    return
                yield text.encode("utf-8")
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            yield b"Response stopped by user"
        except Exception as e:
            yield f"An error occurred: {str(e)}".encode("utf-8")

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Store user feedback in CSV file"""
    try:
        # Define CSV file path
        csv_file_path = "feedback.csv"

        # Check if file exists, if not create it with headers
        file_exists = os.path.isfile(csv_file_path)

        # Prepare data row
        feedback_data = {
            "timestamp": request.timestamp,
            "message_id": request.message_id,
            "session_id": request.session_id,
            "user_message": request.user_message,
            "bot_response": request.bot_response,
            "feedback": request.feedback,
        }

        # Write to CSV file
        with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
            fieldnames = [
                "timestamp",
                "message_id",
                "session_id",
                "user_message",
                "bot_response",
                "feedback",
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            # Write header if file is new
            if not file_exists:
                writer.writeheader()

            writer.writerow(feedback_data)

        return {"status": "success", "message": "Feedback stored successfully"}

    except Exception as e:
        return {"status": "error", "message": f"Failed to store feedback: {str(e)}"}

    """Improved language detection for English vs Roman Urdu"""
    import re

    # Common Roman Urdu words/patterns
    roman_urdu_indicators = [
        "aap",
        "hai",
        "hain",
        "kar",
        "ke",
        "ki",
        "ko",
        "se",
        "me",
        "main",
        "yeh",
        "woh",
        "kya",
        "kyun",
        "kab",
        "kahan",
        "kaisa",
        "kitna",
        "mera",
        "tera",
        "hamara",
        "tumhara",
        "unka",
        "iska",
        "uska",
        "nahi",
        "nahin",
        "bilkul",
        "bohot",
        "bahut",
        "thoda",
        "zyada",
        "paani",
        "pani",
        "khana",
        "ghar",
        "kaam",
        "waqt",
        "time",
        "saal",
        "mahina",
        "din",
        "raat",
        "subah",
        "sham",
        "achha",
        "bura",
        "sundar",
        "khoobsurat",
        "mushkil",
        "aasan",
        "shukriya",
        "maaf",
        "sorry",
        "thanks",
        "please",
        "ji",
        "han",
        "haan",
    ]

    # Convert to lowercase for checking
    text_lower = text.lower()

    # Count Roman Urdu indicators
    roman_urdu_count = sum(1 for word in roman_urdu_indicators if word in text_lower)

    # Check for English patterns
    english_words = re.findall(r"\b[a-zA-Z]+\b", text)
    total_words = len(text.split())

    if total_words == 0:
        return "english"

    # If we found significant Roman Urdu indicators, likely Roman Urdu
    if roman_urdu_count >= 2 or (roman_urdu_count >= 1 and total_words <= 5):
        return "roman_urdu"

    # Otherwise, check English ratio
    english_ratio = len(english_words) / total_words
    return "english" if english_ratio > 0.6 else "roman_urdu"


async def translate_with_openai(text: str, target_language: str) -> str:
    """
    Use OpenAI to translate text to/from Roman Urdu with better quality
    """
    try:
        from llama_index.llms.openai import OpenAI

        # Initialize OpenAI model
        translator_llm = OpenAI(model="gpt-4o-mini", temperature=0.1)

        if target_language == "roman_urdu":
            # English to Roman Urdu
            translation_prompt = f"""
            Translate the following English text to Roman Urdu (Urdu written in English alphabet).
            Use natural, conversational Roman Urdu that Pakistani people commonly use.
            
            Guidelines:
            - Write in English alphabet only (no Urdu script)
            - Use natural Pakistani Roman Urdu style
            - Keep technical terms in English if commonly used
            - Make it sound natural and conversational
            
            English text: {text}
            
            Roman Urdu translation:
            """
        else:
            # Roman Urdu to English
            translation_prompt = f"""
            Translate the following Roman Urdu text to clear, natural English.
            
            Roman Urdu text: {text}
            
            English translation:
            """

        response = await translator_llm.acomplete(translation_prompt)
        translated_text = response.text.strip()

        # Clean up the response (remove any extra formatting)
        if translated_text.startswith('"') and translated_text.endswith('"'):
            translated_text = translated_text[1:-1]

        return translated_text

    except Exception as e:
        print(f"OpenAI translation error: {e}")
        return text  # Return original if translation fails


# Updated translate_text function to use OpenAI
async def translate_text(text, target_language):
    """Enhanced translation using OpenAI for better Roman Urdu quality"""
    try:
        return await translate_with_openai(text, target_language)
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return original if translation fails


# Updated translate endpoint to be async
@router.post("/translate")
async def translate_message(request: dict):
    """Translate message between English and Roman Urdu using OpenAI"""
    try:
        text = request.get("text", "")
        target_language = request.get("target_language", "english")

        translated_text = await translate_text(text, target_language)

        return {
            "status": "success",
            "original_text": text,
            "translated_text": translated_text,
            "target_language": target_language,
        }
    except Exception as e:
        return {"status": "error", "message": f"Translation failed: {str(e)}"}
    """Translate message between English and Roman Urdu"""
    try:
        text = request.get("text", "")
        target_language = request.get("target_language", "english")

        translated_text = translate_text(text, target_language)

        return {
            "status": "success",
            "original_text": text,
            "translated_text": translated_text,
            "target_language": target_language,
        }
    except Exception as e:
        return {"status": "error", "message": f"Translation failed: {str(e)}"}
