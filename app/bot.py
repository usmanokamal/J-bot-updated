#bot.py
from llama_index.core.agent import ReActAgent
from dotenv import load_dotenv
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from pathlib import Path
from llama_index.core import VectorStoreIndex, Settings
import time
import json
from app.index_generator import init_indexes
from app.cacher import retrieve_cache, init_cache, store_cache
import random
import re
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from typing import List, Optional
#from llama_index.agent.openai import OpenAIAssistantAgent
from llama_index.agent.openai import OpenAIAssistantAgent
from llm_guard import scan_prompt
from llm_guard.input_scanners import Anonymize, PromptInjection, TokenLimit, Toxicity
from llm_guard.vault import Vault

# Load environment variablespi
load_dotenv()


vault = Vault()
input_scanners = [ Toxicity(), TokenLimit(), PromptInjection()]


# Initialize settings for embeddings and language models
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)

# Global conversation history
conversation_history: Optional[List[ChatMessage]] = None

# Default responses for generic greetings
DEFAULT_RESPONSES = [
    "Hello! How can I help you today?",
    "Hi there! What would you like to know?",
    "Greetings! How can I assist you?",
    "Hello! I'm here to answer your questions. What can I help you with?"
]

# Define maximum number of messages and maximum length for history
MAX_MESSAGES = 20
MAX_HISTORY_LENGTH = 2000  # Adjust based on model input limits

# Helper function to stream text in smaller chunks
def stream_text(text: str, chunk_size: int = 10):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

# Function to get a random default response
def get_default_response():
    return random.choice(DEFAULT_RESPONSES)

# Function to check if the prompt is a generic greeting
def is_generic_greeting(prompt: str) -> bool:
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "good afternoon"]
    prompt_lower = prompt.lower()
    return any(greeting in prompt_lower for greeting in greetings)

# Heuristic-based gibberish detection
def is_gibberish(prompt: str) -> bool:
    # Require a mix of vowels and consonants
    if not re.search(r"[aeiouAEIOU]", prompt):
        return True  # No vowels, likely gibberish
    if not re.search(r"[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]", prompt):
        return True  # No consonants, likely gibberish

    # Check for at least one valid word of minimum length (three letters)
    if re.search(r"[a-zA-Z]{3,}", prompt):
        return False  # Contains valid word structure

    # High non-letter character ratio
    non_letter_ratio = sum(1 for char in prompt if not char.isalpha()) / len(prompt)
    if non_letter_ratio > 0.6:
        return True  # High proportion of non-letter characters

    # Excessive repetition (more than half the input is repetitive)
    if len(set(prompt)) < len(prompt) * 0.5:
        return True  # Indicates repetitive characters

    return True  # Default to gibberish if no valid structure

# Preprocess the prompt for consistency
def preprocess_prompt(prompt: str) -> str:
    # Convert to lowercase and remove excess spaces
    prompt = prompt.lower()
    prompt = " ".join(prompt.strip().split())

    # Optionally standardize punctuation
    import string
    allowed_punctuation = ".!?,"  # Allow basic punctuation
    prompt = "".join(char for char in prompt if char.isalnum() or char in allowed_punctuation or char.isspace())

    return prompt

# Function to truncate conversation history
def truncate_history(history: List[ChatMessage], max_messages: int, max_length: int) -> List[ChatMessage]:
    # Limit the number of messages
    if len(history) > max_messages:
        history = history[-max_messages:]

    # Limit the total length of the history string
    history_str = "\n".join([f"{msg.role.name}: {msg.content}" for msg in history])
    while len(history_str) > max_length and len(history) > 1:
        history.pop(0)
        history_str = "\n".join([f"{msg.role.name}: {msg.content}" for msg in history])

    return history

# Initialize agent with tools and language model
llm = OpenAI(model="gpt-4o-mini")
Settings.llm = llm

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage

documents = SimpleDirectoryReader("./data").load_data()
persist_dir = Path("main_index")

if not persist_dir.exists():
    print("[bot] main_index not found, building …")
    init_indexes()
    
index = load_index_from_storage(StorageContext.from_defaults(persist_dir=persist_dir))

from llama_index.core.memory import ChatMemoryBuffer

memory = ChatMemoryBuffer.from_defaults(token_limit=3900)

#query_engine = index.as_query_engine(streaming=True, similarity_top_k=1)
chat_engine = index.as_chat_engine(streaming=True, chat_mode='condense_plus_context', memory = memory,
        context_prompt=(
        "You are a chatbot named Ask J-Bot who is able to have normal interactions, as well as talk"
        " about Jazz packages, offers, data offers, complaints, and SOPs."
        "Here are the relevant documents for the context:\n"
        "{context_str}"
        "\nInstruction: Based on the above documents, provide a detailed answer for the user question below."
    ), )
async def chat(prompt: str):
    global conversation_history

    # Ensure conversation_history is initialized
    if conversation_history is None:
        conversation_history = []  # Initialize as an empty list

    try:
        start_timing = time.time()

        # Preprocess the prompt before any operations
        preprocessed_prompt = preprocess_prompt(prompt)

        sanitized_prompt, results_valid, results_score = scan_prompt(input_scanners, prompt)
        print(sanitized_prompt)
        if any(not result for result in results_valid.values()):
            print(f"Prompt {prompt} is not valid, scores: {results_score}")
            response = "We're sorry, but our content safety system has flagged this content as potentially inappropriate or harmful."
            for chunk in stream_text(response):
                yield chunk
            
            return 

        # # Check if the preprocessed prompt is a generic greeting
        # if is_generic_greeting(preprocessed_prompt):
        #     default_response = get_default_response()
        #     chat_message = ChatMessage(role=MessageRole.SYSTEM, content=default_response)
        #     #conversation_history.append(chat_message)

        #     # Stream the default response in smaller chunks
        #     for chunk in stream_text(default_response):
        #         yield chunk

        #     elapsed_timing = time.time() - start_timing
        #     print(f"Elapsed time: {elapsed_timing:.3f} seconds")
        #     return  # Early return with the default response
        
        # # Check if the preprocessed prompt is gibberish
        # if is_gibberish(preprocessed_prompt):
        #     default_response = "I'm not sure I understood that. Could you please rephrase?"
        #     chat_message = ChatMessage(role=MessageRole.SYSTEM, content=default_response)
        #     #conversation_history.append(chat_message)

        #     # Stream the default response in smaller chunks
        #     for chunk in stream_text(default_response):
        #         yield chunk

        #     elapsed_timing = time.time() - start_timing
        #     print(f"Elapsed timing: {elapsed_timing:.3f} seconds")
        #     return
        
        # Append user prompt to the conversation history
        user_message = ChatMessage(role=MessageRole.USER, content=preprocessed_prompt)
        conversation_history.append(user_message)
        
        # Save only the last eight user questions as context if they exist
        if len(conversation_history) > 8:
            conversation_history = conversation_history[-8:]

        # Concatenate conversation history to form the input
        history_content = "\n".join([f"{msg.role.name}: {msg.content}" for msg in conversation_history])
        full_prompt = history_content + "\n" + prompt
        print(full_prompt)
        start_time = time.time()

        # Query the engine asynchronously with the preprocessed prompt
        #response_stream = await query_engine.aquery(prompt)
        response_stream = await chat_engine.astream_chat(prompt)

        # Query end time
        end_time = time.time()

        # Calculate the time taken
        time_taken = end_time - start_time

        # Print the time taken
        print(f"Time taken for query: {time_taken} seconds")

        # Stream the response and append to conversation history
        complete_response_text = ""
        async for text in response_stream.async_response_gen():
            complete_response_text += text
            yield text

        # Append system response to the conversation history
        system_message = ChatMessage(role=MessageRole.SYSTEM, content=complete_response_text.strip())
        conversation_history.append(system_message)

    except Exception as e:
        yield f"Error processing your request: {e}"

