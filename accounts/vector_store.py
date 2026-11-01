from pathlib import Path
import chromadb
from django.conf import settings
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

db_path = Path(settings.BASE_DIR) / "chroma_db"

client = chromadb.PersistentClient(path=str(db_path))

collection = client.get_or_create_collection(
    name="course_materials"
)


def save_chunks(material, chunks):

    if not chunks:
        return 0

    embeddings = model.encode(chunks).tolist()

    ids = [
        f"material_{material.id}_chunk_{i}"
        for i in range(len(chunks))
    ]

    metadatas = [
        {
            "material_id": material.id,
            "teacher_id": material.teacher_id,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]

    existing = collection.get(
        where={"material_id": material.id}
    )

    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return len(chunks)

def search_chunks(material, question, n_results=3):

    if not question.strip():
        return []

    total = collection.count()

    if total == 0:
        return []

    question_embedding = model.encode(
        [question]
    ).tolist()

    results = collection.query(
        query_embeddings=question_embedding,
        n_results=min(n_results, total),
        where={
            "$and": [
                {"material_id": material.id},
                {"teacher_id": material.teacher_id}
            ]
        }
    )

    return results["documents"][0]
