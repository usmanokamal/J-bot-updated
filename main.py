# app/main.py
from fastapi import FastAPI
from app.index_generator import generate_indexes, init_indexes
from app.index_listener import start_listener
from typing import Dict
from app.api import router as api_router
from llama_index.core import VectorStoreIndex
import cProfile
import pstats
import io

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
indexes: Dict[str, VectorStoreIndex] = {}


# Allow requests from your React application's domain
origins = ["http://10.173.2.223:9991"]

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
# profiler = cProfile.Profile()

# def update_indexes(csv_path):
#     global indexes
#     indexes = generate_indexes(csv_path=csv_path)
#     print("Indexes updated")

@app.on_event("startup")
def startup_event():
    init_indexes()
    
#     # profiler.enable()
#     # update_indexes()
#     start_listener(update_indexes)
#     # profiler.disable()
#     # Display results in a readable format
#     # output = io.StringIO()  # Create a stream to hold the profile output
#     # stats = pstats.Stats(profiler, stream=output).sort_stats("cumulative")  # Sort by cumulative time
#     # stats.print_stats(10)  # Display the top 10 results
#     # print(output.getvalue())
app.include_router(api_router)

