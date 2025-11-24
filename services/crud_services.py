from core.firebase import db
from google.cloud.firestore_v1 import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter


# ============================
# CREATE
# ============================
async def create(collection_name: str, model_data: dict, doc_id: str = None):
    collection_ref = db.collection(collection_name)
    
    if doc_id:
        # Create with custom ID
        doc_ref = collection_ref.document(doc_id)
        await doc_ref.set(model_data)
        return {"id": doc_id, "data": model_data}
    
    # Auto-generate ID
    new_doc_ref = collection_ref.document()
    await new_doc_ref.set(model_data)
    return {"id": new_doc_ref.id, "data": model_data}


# ============================
# READ - SINGLE DOCUMENT
# ============================
async def read_one(collection_name: str, doc_id: str):
    doc_ref = db.collection(collection_name).document(doc_id)
    doc = await doc_ref.get()

    if doc.exists:
        return doc.to_dict()
    return None


# ============================
# READ - QUERY WITH FILTER + LIMIT
# ============================
async def read_query(
    collection_name: str, 
    filters: list[tuple] = None, 
    limit: int = None
):
    """
    filters example:
      [("role_id", "==", "teacher"), ("is_active", "==", True)]
    
    limit example:
      2
    """
    collection_ref = db.collection(collection_name)
    query = collection_ref

    # Apply filters
    if filters:
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))

    # Apply limit
    if limit:
        query = query.limit(limit)

    results = await query.get()

    return [
        {"id": doc.id, "data": doc.to_dict()}
        for doc in results
    ]


# ============================
# UPDATE
# ============================
async def update(collection_name: str, doc_id: str, update_data: dict):
    doc_ref = db.collection(collection_name).document(doc_id)
    await doc_ref.update(update_data)
    return {"id": doc_id, "updated": update_data}


# ============================
# DELETE
# ============================
async def delete(collection_name: str, doc_id: str):
    doc_ref = db.collection(collection_name).document(doc_id)
    await doc_ref.delete()
    return {"deleted": doc_id}
