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


class TranslateRequest(BaseModel):
    text: str
    from_lang: str
    to_lang: str

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
                        "message": "Client disconnected before completion"
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
