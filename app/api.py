import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.bot import chat as bot_chat

router = APIRouter()

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
