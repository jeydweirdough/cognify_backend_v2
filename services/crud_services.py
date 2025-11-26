from core.firebase import db
from typing import List, Tuple, Any, Dict

# ============================
# CREATE
# ============================
async def create(collection_name: str, model_data: dict, doc_id: str = None):
    collection_ref = db.collection(collection_name)
    
    if doc_id:
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(model_data)
        return {"id": doc_id, "data": model_data}
    
    new_doc_ref = collection_ref.document()
    new_doc_ref.set(model_data)
    return {"id": new_doc_ref.id, "data": model_data}

# ============================
# READ - SINGLE DOCUMENT
# ============================
async def read_one(collection_name: str, doc_id: str):
    doc_ref = db.collection(collection_name).document(doc_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

# ============================
# READ - QUERY
# ============================
async def read_query(
    collection_name: str, 
    filters: List[Tuple[str, str, Any]] = None, 
    limit: int = None
) -> List[Dict[str, Any]]:
    """
    Executes a Firestore query.
    filters format: [("field", "operator", "value")]
    """
    collection_ref = db.collection(collection_name)
    query = collection_ref

    if filters:
        for field, op, value in filters:
            query = query.where(field, op, value)

    if limit:
        query = query.limit(limit)

    # SYNC call (no await here)
    # Firestore's .get() is blocking in the Admin SDK
    results = query.get()

    data = []
    for doc in results:
        data.append({"id": doc.id, "data": doc.to_dict()})
    
    return data

# ============================
# UPDATE
# ============================
async def update(collection_name: str, doc_id: str, update_data: dict):
    doc_ref = db.collection(collection_name).document(doc_id)
    doc_ref.update(update_data)
    return {"id": doc_id, "updated": update_data}

# ============================
# DELETE
# ============================
async def delete(collection_name: str, doc_id: str):
    doc_ref = db.collection(collection_name).document(doc_id)
    doc_ref.delete()
    return {"deleted": doc_id}