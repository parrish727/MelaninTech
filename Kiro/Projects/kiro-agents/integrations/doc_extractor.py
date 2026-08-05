"""
Document Extraction Pipeline — Ingest business documents into Qdrant for Darius context.

Supported formats:
  - Markdown (.md)
  - HTML (.html)
  - PDF (.pdf) — via PyMuPDF/fitz
  - DOCX (.docx) — via python-docx
  - Plain text (.txt)

Architecture:
  - Reads from MelaninDocs, LinesOfBusiness, and project docs
  - Chunks documents into 512-token overlapping windows
  - Embeds via Ollama nomic-embed-text
  - Upserts to Qdrant 'business_context' collection with LOB/project metadata
  - LOB onboarding manifests drive targeted ingestion per LOB

Collections:
  - business_context — all business documents (SOPs, proposals, architecture, etc.)

Usage:
    # Ingest all documents from a directory
    python -m integrations.doc_extractor --path /app/MelaninDocs

    # Ingest a specific LOB
    python -m integrations.doc_extractor --lob OrthoFlow

    # Ingest all registered LOBs from manifest
    python -m integrations.doc_extractor --all

    # Dry run (count documents, don't upsert)
    python -m integrations.doc_extractor --all --dry-run

Env vars:
    QDRANT_URL — Qdrant API (default: http://qdrant:6333)
    OLLAMA_URL — Ollama embeddings (default: http://ollama:11434)
    MELANIN_DOCS_PATH — MelaninDocs root (default: /app/MelaninDocs)
    LOB_PATH — Lines of Business root (default: /app/LinesOfBusiness)
"""
import os
import re
import sys
import json
import time
import hashlib
import logging
import argparse
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.qdrant_client import SemanticLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("doc_extractor")

MELANIN_DOCS_PATH = Path(os.environ.get("MELANIN_DOCS_PATH", "/app/MelaninDocs"))
LOB_PATH = Path(os.environ.get("LOB_PATH", "/app/LinesOfBusiness"))
MANIFEST_PATH = Path(__file__).resolve().parent.parent / "config" / "lob_manifest.yaml"

COLLECTION_NAME = "business_context"
CHUNK_SIZE = 512  # tokens (~2048 chars)
CHUNK_OVERLAP = 64  # tokens (~256 chars)
CHARS_PER_TOKEN = 4

# File extensions to process
SUPPORTED_EXTENSIONS = {".md", ".html", ".txt", ".pdf", ".docx"}

# Directories/files to skip
SKIP_PATTERNS = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build", ".DS_Store", "Finance"}


class DocumentExtractor:
    """Extracts, chunks, and ingests documents into Qdrant."""

    def __init__(self, dry_run: bool = False):
        self.sl = SemanticLayer()
        self.dry_run = dry_run
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure the business_context collection exists."""
        if not self.dry_run:
            self.sl._create_collection_if_not_exists(COLLECTION_NAME)

    # ── Document Reading ──────────────────────────────────────────────────────

    def read_document(self, path: Path) -> Optional[str]:
        """Read a document and return plain text content."""
        ext = path.suffix.lower()

        if ext == ".md" or ext == ".txt":
            return self._read_text(path)
        elif ext == ".html":
            return self._read_html(path)
        elif ext == ".pdf":
            return self._read_pdf(path)
        elif ext == ".docx":
            return self._read_docx(path)
        else:
            return None

    def _read_text(self, path: Path) -> Optional[str]:
        """Read plain text/markdown file."""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
            return None

    def _read_html(self, path: Path) -> Optional[str]:
        """Read HTML file, strip tags."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            # Simple HTML tag stripping
            text = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except Exception as e:
            logger.warning(f"Failed to read HTML {path}: {e}")
            return None

    def _read_pdf(self, path: Path) -> Optional[str]:
        """Read PDF file via PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n".join(text_parts).strip()
        except ImportError:
            logger.warning(f"PyMuPDF not installed, skipping PDF: {path.name}")
            return None
        except Exception as e:
            logger.warning(f"Failed to read PDF {path}: {e}")
            return None

    def _read_docx(self, path: Path) -> Optional[str]:
        """Read DOCX file via python-docx."""
        try:
            from docx import Document
            doc = Document(str(path))
            text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(text_parts).strip()
        except ImportError:
            logger.warning(f"python-docx not installed, skipping DOCX: {path.name}")
            return None
        except Exception as e:
            logger.warning(f"Failed to read DOCX {path}: {e}")
            return None

    # ── Chunking ──────────────────────────────────────────────────────────────

    def chunk_text(self, text: str, source_file: str = "") -> list[dict]:
        """Split text into overlapping chunks with metadata."""
        if not text or len(text.strip()) < 50:
            return []

        chunk_chars = CHUNK_SIZE * CHARS_PER_TOKEN
        overlap_chars = CHUNK_OVERLAP * CHARS_PER_TOKEN

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + chunk_chars

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end within last 20% of chunk
                search_start = end - int(chunk_chars * 0.2)
                sentence_end = text.rfind(". ", search_start, end)
                if sentence_end > search_start:
                    end = sentence_end + 1

            chunk_text = text[start:end].strip()
            if len(chunk_text) > 50:  # Skip tiny chunks
                chunk_id = hashlib.sha256(f"{source_file}:{chunk_index}:{chunk_text[:100]}".encode()).hexdigest()[:16]
                chunks.append({
                    "id": f"doc_{chunk_id}",
                    "text": chunk_text,
                    "chunk_index": chunk_index,
                    "source_file": source_file,
                })
                chunk_index += 1

            start = end - overlap_chars
            if start <= 0 and chunk_index > 0:
                break  # Prevent infinite loop on tiny texts

        return chunks

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest_directory(self, path: Path, lob_name: str = "general", project: str = "default") -> dict:
        """Ingest all supported documents from a directory."""
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return {"files": 0, "chunks": 0}

        files_processed = 0
        total_chunks = 0
        batch_points = []

        for file_path in self._walk_files(path):
            content = self.read_document(file_path)
            if not content:
                continue

            # Relative path for metadata
            try:
                rel_path = str(file_path.relative_to(path))
            except ValueError:
                rel_path = file_path.name

            chunks = self.chunk_text(content, source_file=rel_path)
            if not chunks:
                continue

            files_processed += 1
            total_chunks += len(chunks)

            for chunk in chunks:
                batch_points.append({
                    "id": chunk["id"],
                    "text": chunk["text"],
                    "metadata": {
                        "source_file": rel_path,
                        "chunk_index": chunk["chunk_index"],
                        "lob": lob_name,
                        "project": project,
                        "file_type": file_path.suffix.lstrip("."),
                        "doc_title": file_path.stem,
                    },
                })

            # Flush batch every 50 chunks
            if len(batch_points) >= 50 and not self.dry_run:
                self.sl.upsert_batch(COLLECTION_NAME, batch_points)
                logger.info(f"  Upserted batch: {len(batch_points)} chunks")
                batch_points = []
                time.sleep(0.5)

        # Flush remaining
        if batch_points and not self.dry_run:
            self.sl.upsert_batch(COLLECTION_NAME, batch_points)
            logger.info(f"  Upserted final batch: {len(batch_points)} chunks")

        return {"files": files_processed, "chunks": total_chunks}

    def ingest_lob(self, lob_name: str, lob_path: Path, project: str = None) -> dict:
        """Ingest all documents for a Line of Business."""
        logger.info(f"─── Ingesting LOB: {lob_name} ───")
        logger.info(f"  Path: {lob_path}")

        result = self.ingest_directory(
            lob_path,
            lob_name=lob_name,
            project=project or lob_name.lower().replace(" ", "-"),
        )

        logger.info(f"  ✓ {lob_name}: {result['files']} files, {result['chunks']} chunks")
        return result

    def ingest_all_from_manifest(self) -> dict:
        """Ingest all LOBs defined in the manifest."""
        manifest = self._load_manifest()
        if not manifest:
            logger.error("No LOB manifest found or empty")
            return {"lobs": 0, "total_chunks": 0}

        total_results = {"lobs": 0, "total_files": 0, "total_chunks": 0, "details": {}}

        for lob in manifest.get("lines_of_business", []):
            name = lob["name"]
            paths = lob.get("doc_paths", [])
            project = lob.get("project_id", name.lower())
            status = lob.get("status", "active")

            if status == "archived":
                logger.info(f"  Skipping archived LOB: {name}")
                continue

            lob_chunks = 0
            lob_files = 0

            for doc_path_str in paths:
                doc_path = Path(doc_path_str)
                if not doc_path.exists():
                    logger.warning(f"  Path not found for {name}: {doc_path}")
                    continue

                result = self.ingest_directory(doc_path, lob_name=name, project=project)
                lob_chunks += result["chunks"]
                lob_files += result["files"]

            total_results["lobs"] += 1
            total_results["total_files"] += lob_files
            total_results["total_chunks"] += lob_chunks
            total_results["details"][name] = {"files": lob_files, "chunks": lob_chunks}

        return total_results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _walk_files(self, path: Path):
        """Walk directory yielding supported files, skipping excluded patterns."""
        if path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                yield path
            return

        for item in sorted(path.rglob("*")):
            # Skip patterns
            if any(skip in item.parts for skip in SKIP_PATTERNS):
                continue
            if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
                yield item

    def _load_manifest(self) -> dict:
        """Load the LOB onboarding manifest."""
        if not MANIFEST_PATH.exists():
            logger.warning(f"Manifest not found: {MANIFEST_PATH}")
            return {}

        try:
            import yaml
            with open(MANIFEST_PATH) as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            # Try JSON fallback
            json_path = MANIFEST_PATH.with_suffix(".json")
            if json_path.exists():
                with open(json_path) as f:
                    return json.load(f)
            return {}


def main():
    parser = argparse.ArgumentParser(description="Document Extraction Pipeline")
    parser.add_argument("--path", type=str, help="Ingest all documents from a specific directory")
    parser.add_argument("--lob", type=str, help="Ingest a specific LOB by name")
    parser.add_argument("--all", action="store_true", help="Ingest all LOBs from manifest")
    parser.add_argument("--melanin-docs", action="store_true", help="Ingest MelaninDocs")
    parser.add_argument("--dry-run", action="store_true", help="Count documents without upserting")
    args = parser.parse_args()

    extractor = DocumentExtractor(dry_run=args.dry_run)

    if args.dry_run:
        logger.info("MODE: DRY RUN (no writes to Qdrant)")

    start_time = time.time()

    if args.path:
        path = Path(args.path)
        logger.info(f"Ingesting from: {path}")
        result = extractor.ingest_directory(path, lob_name="custom", project="custom")
        logger.info(f"Result: {result['files']} files, {result['chunks']} chunks")

    elif args.lob:
        # Find LOB path from manifest or convention
        lob_path = LOB_PATH / args.lob
        if not lob_path.exists():
            # Try case-insensitive match
            for d in LOB_PATH.iterdir():
                if d.name.lower().replace(" ", "_") == args.lob.lower().replace(" ", "_"):
                    lob_path = d
                    break
        result = extractor.ingest_lob(args.lob, lob_path)
        logger.info(f"Result: {json.dumps(result, indent=2)}")

    elif args.melanin_docs:
        logger.info(f"Ingesting MelaninDocs from: {MELANIN_DOCS_PATH}")
        result = extractor.ingest_directory(MELANIN_DOCS_PATH, lob_name="MelaninTech", project="melanin-core")
        logger.info(f"Result: {result['files']} files, {result['chunks']} chunks")

    elif args.all:
        logger.info("Ingesting all LOBs from manifest...")
        result = extractor.ingest_all_from_manifest()
        logger.info(f"\n{'='*60}")
        logger.info("INGESTION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"  LOBs processed: {result['lobs']}")
        logger.info(f"  Total files: {result['total_files']}")
        logger.info(f"  Total chunks: {result['total_chunks']}")
        for name, detail in result.get("details", {}).items():
            logger.info(f"    {name}: {detail['files']} files, {detail['chunks']} chunks")
        logger.info(f"{'='*60}")

    else:
        parser.print_help()
        sys.exit(1)

    elapsed = time.time() - start_time
    logger.info(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
