"""BGE embeddings, loaded once per process (shared by ingestion and the backend)."""
from functools import lru_cache

from contracts import constants
from backend.app.core.config import get_settings


@lru_cache
def get_model():
    from sentence_transformers import SentenceTransformer  # heavy import, only when first needed
    model = SentenceTransformer(get_settings().embed_model, device="cpu")
    dim = model.get_embedding_dimension()
    if dim != constants.VECTOR_SIZE:
        raise RuntimeError(f"EMBED_MODEL gives {dim}-d vectors but contracts say {constants.VECTOR_SIZE}")
    return model


def get_tokenizer():
    """The model's own tokenizer, so chunk token counts match what the model sees."""
    return get_model().tokenizer


def embed_documents(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    vectors = get_model().encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    # BGE v1.5: short queries get an instruction prefix; documents do not.
    return get_model().encode(constants.BGE_QUERY_PREFIX + text, normalize_embeddings=True).tolist()
