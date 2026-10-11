"""
Upload synthetic data ke Astra DB collections.

Requirements:
    pip install astrapy python-dotenv

Setup .env dulu:
    ASTRA_DB_APPLICATION_TOKEN=AstraCS:...
    ASTRA_DB_API_ENDPOINT=https://xxxx-xxxx.apps.astra.datastax.com

Run:
    python data/upload_to_astra.py
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from astrapy import DataAPIClient

load_dotenv()

ASTRA_TOKEN    = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")

if not ASTRA_TOKEN or not ASTRA_ENDPOINT:
    raise SystemExit(
        "❌ ASTRA_DB_APPLICATION_TOKEN dan ASTRA_DB_API_ENDPOINT harus diisi di .env"
    )

# Files to upload: (json_file, collection_name, embedding_field)
UPLOADS = [
    ("prescriptions.json",    "prescriptions",     "prescription_text"),
    ("drug_interactions.json","drug_interactions",  "interaction_text"),
    ("drug_side_effects.json","drug_side_effects",  "side_effect_text"),
]

DATA_DIR = Path(__file__).parent / "sample"


def create_collection_if_not_exists(db, name: str):
    """Create a collection (no vector config — Langflow handles embeddings)."""
    existing = [c.name for c in db.list_collections()]
    if name in existing:
        print(f"  [skip] Collection '{name}' sudah ada.")
        return db.get_collection(name)

    print(f"  [create] Membuat collection '{name}'...")
    return db.create_collection(name)


def upload_file(collection, json_path: Path, embedding_field: str):
    """Load JSON and insert documents into the collection."""
    with open(json_path, encoding="utf-8") as f:
        docs = json.load(f)

    # astrapy expects $vector field for embeddings — we store raw text here.
    # Langflow's Astra DB component will handle embedding generation at query time.
    # Just insert the documents as-is; Langflow will embed on the fly via its retriever node.
    result = collection.insert_many(docs)
    print(f"  ✅ Inserted {len(result.inserted_ids)} docs → '{collection.name}'")


def main():
    print("🔗 Connecting to Astra DB...")
    client = DataAPIClient(ASTRA_TOKEN)
    db     = client.get_database_by_api_endpoint(ASTRA_ENDPOINT)
    print(f"✅ Connected: {ASTRA_ENDPOINT}\n")

    for filename, collection_name, embedding_field in UPLOADS:
        json_path = DATA_DIR / filename
        print(f"Processing {filename} -> collection '{collection_name}'")

        if not json_path.exists():
            print(f"  ⚠️  File tidak ditemukan: {json_path}, skip.\n")
            continue

        collection = create_collection_if_not_exists(db, collection_name)
        upload_file(collection, json_path, embedding_field)
        print()

    print("SELESAI! Semua data berhasil diupload ke Astra DB!")
    print("\nNext step: Sambungkan Astra DB di Langflow menggunakan:")
    print("  - Astra DB component → pilih collection yang sesuai")
    print("  - Embedding model: Gemini text-embedding-004")
    print("  - Search type: Similarity (cosine)")


if __name__ == "__main__":
    main()
