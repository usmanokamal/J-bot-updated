import faiss
from sentence_transformers import SentenceTransformer
import json

def init_cache():
    # Dimensionality of your embeddings
    d = 768  # Common for models like BERT, GPT-3, etc.

    # Define the parameters for HNSW
    # `M` defines the number of connections each node can have; typical values are 16 or 32.
    # `efConstruction` determines the quality of the graph during construction.
    M = 16
    efConstruction = 100  # Higher values give better graph quality

    # Create an HNSW index
    index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_L2)  # Use L2 (Euclidean distance)

    # Set the `efConstruction` parameter
    index.hnsw.efConstruction = efConstruction

    # Initialize the embedding model
    encoder = SentenceTransformer("all-mpnet-base-v2")

    # Retrieve the cache, or initialize an empty one if needed
    json_file = "cache_file.json"
    cache = {}
    try:
        with open(json_file, "r") as file:
            cache = json.load(file)
    except FileNotFoundError:
        cache = {"questions": [], "embeddings": [], "answers": [], "response_text": []}

    return index, encoder, cache


def retrieve_cache(json_file):
    try:
        with open(json_file, "r") as file:
            cache = json.load(file)
    except FileNotFoundError:
        # If the cache file doesn't exist, initialize an empty cache
        cache = {"questions": [], "embeddings": [], "answers": [], "response_text": []}

    return cache


def store_cache(json_file, cache):
    with open(json_file, "w") as file:
        json.dump(cache, file)
