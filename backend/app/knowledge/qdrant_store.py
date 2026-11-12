"""The ONE Qdrant client factory + collection setup + upsert/search helpers."""
import uuid
from functools import lru_cache

from qdrant_client import QdrantClient, models

from contracts import constants
from contracts.schemas import Evidence
from backend.app.core.config import get_settings

UPSERT_TIMEOUT_S = 60
UPSERT_BATCH = 32          # small batches: each point carries chunk text, uploads must fit the timeout
UPSERT_RETRIES = 3

PAYLOAD_INDEXES = {
    "scheme_id": models.PayloadSchemaType.KEYWORD,
    "doc_id": models.PayloadSchemaType.KEYWORD,
    "section": models.PayloadSchemaType.KEYWORD,
    "is_current": models.PayloadSchemaType.BOOL,
}


@lru_cache
def get_client() -> QdrantClient:
    s = get_settings()
    if s.qdrant_url:
        key = s.qdrant_api_key.get_secret_value() if s.qdrant_api_key else None
        return QdrantClient(url=s.qdrant_url, api_key=key, timeout=UPSERT_TIMEOUT_S)
    if s.qdrant_path:                                   # offline tests only
        return QdrantClient(path=str(s.qdrant_path))
    raise RuntimeError("QDRANT_URL is not set in .env")


def close_client() -> None:
    """Close the cached client (local mode holds a file lock; closing at interpreter exit errors)."""
    if get_client.cache_info().currsize:
        get_client().close()
        get_client.cache_clear()


def collection_name() -> str:
    return get_settings().qdrant_collection


def point_id(chunk_id: str) -> str:
    """Deterministic: re-indexing the same chunk overwrites it instead of duplicating it."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def ensure_collection(client: QdrantClient | None = None) -> None:
    client = client or get_client()
    name = collection_name()
    if client.collection_exists(name):
        params = client.get_collection(name).config.params.vectors
        if params.size != constants.VECTOR_SIZE or params.distance != models.Distance.COSINE:
            raise RuntimeError(f"Collection {name!r} exists with {params.size}-d/{params.distance}; "
                               f"expected {constants.VECTOR_SIZE}-d/Cosine")
    else:
        client.create_collection(name, vectors_config=models.VectorParams(
            size=constants.VECTOR_SIZE, distance=models.Distance.COSINE))
    for field, schema in PAYLOAD_INDEXES.items():
        client.create_payload_index(name, field_name=field, field_schema=schema)  # no-op if it exists


def upsert_evidence(items: list[tuple[Evidence, list[float]]], is_current: bool = True) -> None:
    """Upload in small batches; a batch that times out is retried with backoff (idempotent ids)."""
    import time
    from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
    points = [models.PointStruct(id=point_id(ev.chunk_id), vector=vec,
                                 payload={**ev.model_dump(exclude={"score"}), "is_current": is_current})
              for ev, vec in items]
    for start in range(0, len(points), UPSERT_BATCH):
        batch = points[start:start + UPSERT_BATCH]
        for attempt in range(1, UPSERT_RETRIES + 1):
            try:
                get_client().upsert(collection_name(), points=batch, wait=True)
                break
            except (ResponseHandlingException, UnexpectedResponse) as e:
                status = getattr(e, "status_code", None)
                if attempt == UPSERT_RETRIES or (status is not None and status < 500 and status != 429):
                    raise
                time.sleep(2 ** attempt)


def delete_document(doc_id: str) -> None:
    """Remove every point of one document (before re-indexing it, so stale chunks never linger)."""
    get_client().delete(collection_name(), wait=True, points_selector=models.FilterSelector(filter=models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])))


def set_is_current(doc_id: str, is_current: bool) -> None:
    """Flip the retrieval flag on every point of one document (used when a newer version is indexed)."""
    get_client().set_payload(collection_name(), payload={"is_current": is_current}, wait=True,
                             points=models.Filter(must=[models.FieldCondition(
                                 key="doc_id", match=models.MatchValue(value=doc_id))]))


def search(vector: list[float], limit: int, scheme_ids: list[str] | None = None) -> list[Evidence]:
    must = [models.FieldCondition(key="is_current", match=models.MatchValue(value=True))]
    if scheme_ids:
        must.append(models.FieldCondition(key="scheme_id", match=models.MatchAny(any=scheme_ids)))
    hits = get_client().query_points(collection_name(), query=vector, limit=limit,
                                     query_filter=models.Filter(must=must), with_payload=True).points
    return [Evidence(**{**h.payload, "score": h.score}) for h in hits]
