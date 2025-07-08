# app/index_generator.py

from pathlib import Path
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Document
import pandas as pd

def get_index(data, index_name):
    index_dir = Path(index_name)
    if not index_dir.exists():
        print(f"[index-generator] building index {index_name}")
        index = VectorStoreIndex.from_documents(data, show_progress=True)
        index.storage_context.persist(persist_dir=index_name)
    else:
        print(f"[index-generator] index {index_name} exists. Rebuilding …")
        # Remove existing files
        for file in index_dir.glob('*'):
            file.unlink()
        index = VectorStoreIndex.from_documents(data, show_progress=True)
        index.storage_context.persist(persist_dir=index_name)
    return index

def csv_to_documents(csv_path):
    """
    Reads a CSV as utf-8 and returns a list of LlamaIndex Document objects.
    """
    df = pd.read_csv(csv_path, encoding='utf-8')
    docs = []
    for i, row in df.iterrows():
        content = row.astype(str).to_dict()
        docs.append(Document(text=str(content), metadata={"source": Path(csv_path).name, "row": i}))
    return docs

def generate_indexes(csv_path):
    """
    Rebuild the index for a single CSV file (called by hot-reload listener).
    """
    path = Path(csv_path)
    if not path.exists() or path.suffix.lower() != ".csv":
        print(f"[index-generator] {csv_path} not found or not a CSV file.")
        return None
    try:
        docs = csv_to_documents(path)
        print(f"[index-generator] loaded: {path.name} ({len(docs)} rows)")
    except Exception as e:
        print(f"[index-generator] warning: failed to read {path.name}: {e}")
        return None
    index_name = path.stem + "_index"
    return get_index(docs, index_name)

def init_indexes() -> None:
    """
    Build a unified index from all cleaned CSVs in the /data/ directory,
    and persist to disk under main_index/.
    """
    script_dir = Path(__file__).resolve().parent
    data_dir = (script_dir / ".." / "data").resolve()
    persist_dir = Path("main_index")

    # Find all CSV files in /data/
    csv_paths = list(data_dir.glob("*.csv"))

    if persist_dir.exists():
        print("[index-generator] index already exists → nothing to rebuild.")
        return

    print(f"[index-generator] building unified index from {len(csv_paths)} CSV files …")
    all_docs = []
    for p in csv_paths:
        try:
            docs = csv_to_documents(p)
            all_docs.extend(docs)
            print(f"[index-generator] loaded: {p.name} ({len(docs)} rows)")
        except Exception as e:
            print(f"[index-generator] warning: failed to read {p.name}: {e}")

    if not all_docs:
        print("[index-generator] No data found in any CSVs, skipping index creation.")
        return

    # Build and persist the index
    index = VectorStoreIndex.from_documents(all_docs, show_progress=True)
    index.storage_context.persist(persist_dir=persist_dir)
    print(f"[index-generator] index saved to {persist_dir}/")

def load_index() -> VectorStoreIndex:
    """
    Load the unified index from disk. Rebuild if missing.
    """
    persist_dir = Path("main_index")
    if not persist_dir.exists():
        print("[index-generator] No index found. Building now …")
        init_indexes()
    return load_index_from_storage(StorageContext.from_defaults(persist_dir=persist_dir))

# For manual CLI use
if __name__ == "__main__":
    init_indexes()
