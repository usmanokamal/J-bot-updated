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
from llama_index.agent.openai import OpenAIAssistantAgent
from llm_guard import scan_prompt
from llm_guard.input_scanners import Anonymize, PromptInjection, TokenLimit, Toxicity
from llm_guard.vault import Vault

# Load environment variables
load_dotenv()

vault = Vault()
input_scanners = [Toxicity(), TokenLimit(), PromptInjection()]

# Initialize settings for embeddings and language models
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

# Global conversation history
conversation_history: Optional[List[ChatMessage]] = None

DEFAULT_RESPONSES = [
    "Hello! How can I help you today?",
    "Hi there! What would you like to know?",
    "Greetings! How can I assist you?",
    "Hello! I'm here to answer your questions. What can I help you with?",
]

MAX_MESSAGES = 20
MAX_HISTORY_LENGTH = 2000  # Adjust as needed


def stream_text(text: str, chunk_size: int = 10):
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def get_default_response():
    return random.choice(DEFAULT_RESPONSES)


def preprocess_prompt(prompt: str) -> str:
    prompt = prompt.lower()
    prompt = " ".join(prompt.strip().split())
    allowed_punctuation = ".!?,"
    prompt = "".join(
        char
        for char in prompt
        if char.isalnum() or char in allowed_punctuation or char.isspace()
    )
    return prompt


def truncate_history(
    history: List[ChatMessage], max_messages: int, max_length: int
) -> List[ChatMessage]:
    if len(history) > max_messages:
        history = history[-max_messages:]
    history_str = "\n".join([f"{msg.role.name}: {msg.content}" for msg in history])
    while len(history_str) > max_length and len(history) > 1:
        history.pop(0)
        history_str = "\n".join([f"{msg.role.name}: {msg.content}" for msg in history])
    return history


llm = OpenAI(model="gpt-4o-mini")
Settings.llm = llm

from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    load_index_from_storage,
)

documents = SimpleDirectoryReader("./data").load_data()
persist_dir = Path("main_index")

if not persist_dir.exists():
    print("[bot] main_index not found, building …")
    init_indexes()

index = load_index_from_storage(StorageContext.from_defaults(persist_dir=persist_dir))

from llama_index.core.memory import ChatMemoryBuffer

memory = ChatMemoryBuffer.from_defaults(token_limit=3900)


# --- ROMAN URDU DETECTION ---
def is_roman_urdu(prompt: str) -> bool:
    urdu_words = [
        "kya",
        "kaise",
        "tum",
        "mein",
        "aap",
        "mera",
        "apna",
        "hai",
        "ho",
        "kar",
        "ki",
        "se",
        "ko",
        "ka",
        "raha",
        "rahi",
        "kuch",
        "nahi",
        "haan",
        "acha",
        "theek",
        "batao",
        "kyun",
        "kahan",
        "kon",
        "kaun",
        "par",
        "aur",
        "magar",
    ]
    prompt_lower = prompt.lower()
    words = re.findall(r"\b\w+\b", prompt_lower)
    urdu_count = sum(1 for word in words if word in urdu_words)
    english_count = sum(
        1 for word in words if re.match(r"^[a-z]{3,}$", word) and word not in urdu_words
    )
    if urdu_count >= 2 and urdu_count > english_count:
        return True
    return False


async def translate_to_english(prompt: str):
    """
    Use the LLM itself to translate Roman Urdu to English for retrieval (prompt engineering).
    This avoids needing Google Translate.
    """
    instruction = (
        "Translate the following Roman Urdu (Urdu written in English alphabet) to clear English. "
        "Respond with only the translation and nothing else:\n\n" + prompt
    )
    temp_engine = index.as_chat_engine(
        streaming=False,  # No need to stream translation
        chat_mode="condense_plus_context",
        memory=None,
        context_prompt=instruction,
    )
    response = await temp_engine.achat(prompt)
    return response.strip()


# --- MAIN CHAT ENGINE (ENGLISH) ---
chat_engine = index.as_chat_engine(
    streaming=True,
    chat_mode="condense_plus_context",
    memory=memory,
    context_prompt=(
        "You are a chatbot named JazzBot, an expert assistant, specially designed for KMS to help jazz agents in franchises"
        " Guide user about Jazz packages, offers, data offers, complaints, and SOPs."
        "When someone ask you that: 'Who are you or/and what can you do?' give your introduction and capabilities."
        " Here are the relevant documents for the context:\n"
        "{context_str}"
        "\nInstruction: Based on the above documents, provide a detailed answer for the user question below from the documents."
        "\nIf user question is not related to Jazz or the documents, respond with: 'Sorry, I don't have that information.'"
        "\nIf user gives a USSD code, respond with the service name and details for that USSD code from the context/knowledgebase."
    ),
)


# --- MAIN CHAT FUNCTION WITH ROMAN URDU SUPPORT ---
async def chat(prompt: str):
    global conversation_history

    if conversation_history is None:
        conversation_history = []

    try:
        start_timing = time.time()
        preprocessed_prompt = preprocess_prompt(prompt)
        sanitized_prompt, results_valid, results_score = scan_prompt(
            input_scanners, prompt
        )
        print(sanitized_prompt)
        if any(not result for result in results_valid.values()):
            print(f"Prompt {prompt} is not valid, scores: {results_score}")
            response = "We're sorry, but our content safety system has flagged this content as potentially inappropriate or harmful."
            for chunk in stream_text(response):
                yield chunk
            return

        user_message = ChatMessage(role=MessageRole.USER, content=preprocessed_prompt)
        conversation_history.append(user_message)
        if len(conversation_history) > 8:
            conversation_history = conversation_history[-8:]

        # --- ROMAN URDU HANDLING ---
        if is_roman_urdu(preprocessed_prompt):
            # 1. Translate Roman Urdu to English for retrieval (using LLM itself)
            translated_query = await translate_to_english(preprocessed_prompt)

            # 2. Retrieve context with translated English query
            nodes = index.as_query_engine(similarity_top_k=2).retrieve(translated_query)
            if not nodes or all(not n.get_content().strip() for n in nodes):
                response = "Maazrat chahta hoon, mujhay yeh maloomat nahi mili."
                for chunk in stream_text(response):
                    yield chunk
                conversation_history.append(
                    ChatMessage(role=MessageRole.SYSTEM, content=response)
                )
                return

            # 3. Custom context prompt to instruct LLM to respond in Roman Urdu
            roman_urdu_context_prompt = (
                "You are a chatbot named JazzBot, an expert assistant. User has asked in Roman Urdu (Urdu written in English alphabet). "
                "Use ONLY the following context to answer. If answer not found, reply: 'Maazrat chahta hoon, mujhay yeh maloomat nahi mili.' "
                "Respond in Roman Urdu. \nContext:\n{context_str}\nInstruction: Provide a detailed answer in Roman Urdu."
            )
            roman_urdu_engine = index.as_chat_engine(
                streaming=True,
                chat_mode="condense_plus_context",
                memory=memory,
                context_prompt=roman_urdu_context_prompt,
            )
            response_stream = await roman_urdu_engine.astream_chat(preprocessed_prompt)
            complete_response_text = ""
            async for text in response_stream.async_response_gen():
                complete_response_text += text
                yield text
            conversation_history.append(
                ChatMessage(
                    role=MessageRole.SYSTEM, content=complete_response_text.strip()
                )
            )
            return

        # --- ENGLISH HANDLING ---
        else:
            nodes = index.as_query_engine(similarity_top_k=2).retrieve(
                preprocessed_prompt
            )
            if not nodes or all(not n.get_content().strip() for n in nodes):
                response = "Sorry, I don't have that information."
                for chunk in stream_text(response):
                    yield chunk
                conversation_history.append(
                    ChatMessage(role=MessageRole.SYSTEM, content=response)
                )
                return

            response_stream = await chat_engine.astream_chat(prompt)
            complete_response_text = ""
            async for text in response_stream.async_response_gen():
                complete_response_text += text
                yield text
            conversation_history.append(
                ChatMessage(
                    role=MessageRole.SYSTEM, content=complete_response_text.strip()
                )
            )

    except Exception as e:
        yield f"Error processing your request: {e}"
