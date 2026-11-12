"""Download every ML model the pipeline needs into .venv/models (run once; safe to re-run).

    python -m ingestion.download_models

* BGE embeddings (sentence-transformers)  -> .venv/models/huggingface
* Docling layout + table models + RapidOCR -> .venv/models/docling
After this, parsing and embedding work with HF_HUB_OFFLINE=1 (no network needed for models).
"""
from contracts import constants
from backend.app.core.config import DOCLING_ARTIFACTS_DIR, MODEL_DIR  # sets HF_HOME before any HF import
from ingestion.common import write_json, now_iso


def main() -> None:
    from sentence_transformers import SentenceTransformer
    from docling.utils.model_downloader import download_models

    print(f"model folder: {MODEL_DIR}")
    model = SentenceTransformer(constants.EMBED_MODEL, device="cpu")
    print(f"  BGE ok: {constants.EMBED_MODEL}, {model.get_embedding_dimension()}-d")

    DOCLING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    download_models(output_dir=DOCLING_ARTIFACTS_DIR, progress=False,
                    with_layout=True, with_tableformer=True, with_rapidocr=True,
                    with_code_formula=False, with_picture_classifier=False)   # only what parse.py uses
    write_json(DOCLING_ARTIFACTS_DIR / "model_artifacts_ok", {"downloaded_at": now_iso()})
    print(f"  Docling ok: {sorted(p.name for p in DOCLING_ARTIFACTS_DIR.iterdir())}")


if __name__ == "__main__":
    main()
