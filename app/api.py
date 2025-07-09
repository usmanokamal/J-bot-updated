import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.bot import chat as bot_chat
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str  # You can ignore or use this as needed

@router.post("/chat/")
@router.post("/chat")
async def chat_post(request: ChatRequest):
    # Get the full reply as a string (not streamed for UI)
    response = ""
    async for chunk in bot_chat(request.message):
        response += chunk
    return {"response": response}


@router.get("/chat/")
async def chat(prompt: str):
    # Asynchronous generator to yield streaming data
    async def generate():
        try:
            # # Ensure single iteration over the asynchronous generator
            # stream_response = bot_chat(prompt)  # Create a new instance for each iteration

            # async for response in stream_response:
            #     yield response.encode("utf-8")
            #     await asyncio.sleep(0.1)  # Simulate processing time
            async for text in bot_chat(prompt):
                yield text.encode("utf-8")  # Yield each response as it comes
                
        except Exception as e:
            # Handle exceptions gracefully
            yield f"An error occurred: {str(e)}".encode("utf-8")

    return StreamingResponse(generate(), media_type="text/plain")
