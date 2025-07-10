import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from app.bot import chat as bot_chat
from app.bot import translate_to_english, index
from pydantic import BaseModel
import json

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str

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
                    return
                
                full_response += chunk
                
                # Send chunk as JSON for easier parsing on frontend
                chunk_data = {
                    "chunk": chunk,
                    "type": "content"
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
            
            # Send completion signal
            completion_data = {
                "type": "complete",
                "full_response": full_response
            }
            yield f"data: {json.dumps(completion_data)}\n\n"
            
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            stop_data = {
                "type": "stopped",
                "message": "Response stopped by user"
            }
            yield f"data: {json.dumps(stop_data)}\n\n"
            return
        except Exception as e:
            # Handle other exceptions
            error_data = {
                "type": "error",
                "message": f"An error occurred: {str(e)}"
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate(), 
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
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
    