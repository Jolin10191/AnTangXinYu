"""Build the medical knowledge index for the Antang backend.

Stage 1: PDF -> page-accurate chunks -> bge-m3 embeddings -> JSONL.

Run from anywhere:

    py -3 kb_build.py --dry                 # parse only, no embeddings
    py -3 kb_build.py --limit 2             # first two documents
    py -3 kb_build.py                       # everything

The output is a single JSONL file plus a manifest; nothing here touches the
production database.  The loader (`kb_load.py`) does that separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from openai import OpenAI

KNOWLEDGE_DIR = Path(r"D:\python\ProjectT1DMpre\knowledge")
OUT_DIR = Path(r"D:\deepseek-harness\kb")
KEY_FILE = Path(r"D:\deepseek-harness\.kb-key")

BASE_URL = "https://pro.gemai.cc/v1"
EMBED_MODEL = "bge-m3"
EMBED_DIM = 1024

MIN_BYTES = 30_000
CHUNK_CHARS = 900
HARD_MAX_CHARS = 1200
TINY_PAGE_CHARS = 220
MIN_CHUNK_CHARS = 60
BATCH = 16

PAGE_NUMBER_LINE = re.compile(
    r"^[\s\u00b7\u2022\-\u2013\u2014_/]*\d{1,4}[\s\u00b7\u2022\-\u2013\u2014_/]*$"
)
PAGE_LABEL_LINE = re.compile(r"^(绗琝s*\d{1,4}\s*椤祙Page\s*\d{1,4}(\s*of\s*\d{1,4})?)$", re.IGNORECASE)
CODE_NAME = re.compile(r"^dc26s\d+[a-z]*$", re.IGNORECASE)

# A line repeated on at least this share of a document's pages is a running
# header/footer, not content.
RUNNING_MIN_RATIO = 0.40
RUNNING_MIN_LEN = 8
RUNNING_MAX_LEN = 120

FOLIO_LINE = re.compile(r"^[\s\u00b7\u2022\-\u2013\u2014_.]*(\d{1,4})[\s\u00b7\u2022\-\u2013\u2014_.]*$")
FOLIO_MIN_RATIO = 0.50
FOLIO_TOLERANCE = 2


@dataclass
class Doc:
    path: Path
    title: str
    folder: str
    pages: list[str] = field(default_factory=list)
    printed: list[int | None] = field(default_factory=list)
    stripped_lines: int = 0
    printed_offset: int | None = None


@dataclass
class Chunk:
    title: str
    folder: str
    page: int
    ordinal: int
    text: str
    printed_page: int | None = None
    sha256: str = ""

    def finalise(self) -> "Chunk":
        self.sha256 = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        return self

    def as_json(self) -> dict[str, object]:
        return {
            "title": self.title,
            "folder": self.folder,
            "page": self.page,
            "printed_page": self.printed_page,
            "ordinal": self.ordinal,
            "text": self.text,
            "sha256": self.sha256,
        }


def page_lines(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def collect_running_lines(raw_pages: list[str]) -> set[str]:
    """Return lines that repeat on most pages of one document.

    Scans every line, not just the page edges: running heads drift to the
    middle of the text on some layouts, and body prose never repeats a whole
    line verbatim across dozens of pages.
    """
    counts: Counter[str] = Counter()
    useful = 0
    for raw in raw_pages:
        lines = page_lines(raw)
        if not lines:
            continue
        useful += 1
        for line in set(lines):
            if RUNNING_MIN_LEN <= len(line) <= RUNNING_MAX_LEN:
                counts[line] += 1
    if not useful:
        return set()
    threshold = max(2, int(useful * RUNNING_MIN_RATIO))
    return {line for line, count in counts.items() if count >= threshold}


def detect_folio(raw: str) -> int | None:
    """Read the printed page number from a page footer, if one is printed."""
    lines = page_lines(raw)
    for line in reversed(lines[-4:]):
        match = FOLIO_LINE.match(line)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 9999:
                return number
    return None


def printed_offset(folios: list[int | None]) -> int | None:
    """Offset from PDF page index to printed page, or None when unreadable.

    Guides typeset for a journal start at e.g. printed 1143 while the PDF page
    is 1. The offset is constant, so reading it once per document is enough;
    median keeps the occasional stray number (a year, a DOI fragment) out.
    """
    pairs = [
        (index, number)
        for index, number in enumerate(folios, start=1)
        if number is not None
    ]
    if len(pairs) < max(4, int(len(folios) * FOLIO_MIN_RATIO)):
        return None
    offsets = sorted(number - index for index, number in pairs)
    offset = offsets[len(offsets) // 2]
    agreeing = sum(1 for index, number in pairs if abs(number - (index + offset)) <= FOLIO_TOLERANCE)
    if agreeing < len(pairs) * 0.8:
        return None
    return offset


def clean_page(raw: str, running: set[str] | None = None) -> str:
    kept: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if running and stripped in running:
            continue
        if PAGE_NUMBER_LINE.match(stripped) or PAGE_LABEL_LINE.match(stripped):
            continue
        if stripped.startswith("Downloaded from") or stripped.startswith("https://doi.org"):
            continue
        if len(stripped) < 2:
            continue
        kept.append(stripped)
    text = "\n".join(kept)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def guess_title(path: Path, first_page: str) -> str:
    stem = path.stem
    if CODE_NAME.match(stem):
        for line in first_page.splitlines():
            candidate = line.strip()
            if 3 <= len(candidate) <= 120:
                return candidate
        return stem
    return stem


def split_text(text: str) -> list[str]:
    """Split one page of text into <= CHUNK_CHARS pieces on sentence boundaries."""
    if len(text) <= CHUNK_CHARS:
        return [text] if text else []

    sentences = re.split(r"(?<=[\u3002\uff01\uff1f\uff1b!?;\n])", text)
    pieces: list[str] = []
    buffer = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(buffer) + len(sentence) > CHUNK_CHARS and buffer:
            pieces.append(buffer)
            buffer = sentence[-HARD_MAX_CHARS:]
        else:
            buffer += sentence
        while len(buffer) > HARD_MAX_CHARS:
            pieces.append(buffer[:CHUNK_CHARS])
            buffer = buffer[CHUNK_CHARS - 150:]
    if buffer.strip():
        pieces.append(buffer)
    return [p.strip() for p in pieces if len(p.strip()) >= MIN_CHUNK_CHARS]


def load_doc(path: Path) -> Doc:
    relative = path.relative_to(KNOWLEDGE_DIR)
    doc = Doc(path=path, title="", folder=relative.parts[0] if relative.parts else "root")
    with pymupdf.open(path) as pdf:
        raw_pages = [page.get_text("text") for page in pdf]

    running = collect_running_lines(raw_pages)
    offset = printed_offset([detect_folio(raw) for raw in raw_pages])

    for index, raw in enumerate(raw_pages, start=1):
        doc.pages.append(clean_page(raw, running))
        doc.printed.append(index + offset if offset is not None else None)

    doc.title = guess_title(path, doc.pages[0] if doc.pages else "")
    doc.stripped_lines = len(running)
    doc.printed_offset = offset
    return doc


def chunk_doc(doc: Doc) -> list[Chunk]:
    chunks: list[Chunk] = []
    pending = ""
    pending_page = 0
    pending_printed: int | None = None

    for index, page_text in enumerate(doc.pages, start=1):
        if not page_text:
            continue
        merged = f"{pending}\n{page_text}" if pending else page_text
        page_no = pending_page or index
        printed = pending_printed if pending_page else doc.printed[index - 1]
        if len(merged) < TINY_PAGE_CHARS:
            pending = merged
            pending_page = page_no
            pending_printed = printed
            continue
        pending = ""
        pending_page = 0
        pending_printed = None
        for ordinal, piece in enumerate(split_text(merged)):
            chunks.append(
                Chunk(doc.title, doc.folder, page_no, ordinal, piece, printed).finalise()
            )

    if pending.strip():
        chunks.append(
            Chunk(doc.title, doc.folder, pending_page or 1, 0, pending.strip(), pending_printed).finalise()
        )
    return chunks


def read_key() -> str:
    if not KEY_FILE.exists():
        sys.exit(f"missing api key file: {KEY_FILE}")
    key = KEY_FILE.read_text(encoding="ascii").strip()
    if not key:
        sys.exit("api key file is empty")
    return key


class Embedder:
    def __init__(self) -> None:
        self.client = OpenAI(base_url=BASE_URL, api_key=read_key(), timeout=120.0, max_retries=4)

    def embed(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(4):
            try:
                response = self.client.embeddings.create(model=EMBED_MODEL, input=texts)
                vectors = [item.embedding for item in response.data]
                if len(vectors) != len(texts):
                    raise RuntimeError(f"expected {len(texts)} vectors, got {len(vectors)}")
                for vector in vectors:
                    if len(vector) != EMBED_DIM:
                        raise RuntimeError(f"expected {EMBED_DIM} dims, got {len(vector)}")
                return vectors
            except Exception as exc:  # noqa: BLE001 - retried below, then raised
                if attempt == 3:
                    raise
                print(f"    retry {attempt + 1} after: {exc}", flush=True)
                time.sleep(2 * (attempt + 1))
        raise AssertionError("unreachable")


def main() -> None:
    global KNOWLEDGE_DIR, OUT_DIR, KEY_FILE, BASE_URL

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="parse only, skip embeddings")
    parser.add_argument("--limit", type=int, default=0, help="only process the first N documents")
    parser.add_argument("--match", default="", help="only process paths containing this substring")
    parser.add_argument("--max-mb", type=float, default=0.0, help="skip documents larger than N MB")
    parser.add_argument("--source", type=Path, default=KNOWLEDGE_DIR, help="root directory of the PDF corpus")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="directory for the JSONL and manifest")
    parser.add_argument("--key-file", type=Path, default=KEY_FILE, help="file holding the embedding API key")
    parser.add_argument("--base-url", default=BASE_URL, help="OpenAI compatible embedding endpoint")
    args = parser.parse_args()

    KNOWLEDGE_DIR = args.source
    OUT_DIR = args.out
    KEY_FILE = args.key_file
    BASE_URL = args.base_url

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in KNOWLEDGE_DIR.rglob("*.pdf") if p.is_file())
    if args.match:
        pdfs = [p for p in pdfs if args.match in str(p)]
    if args.limit:
        pdfs = pdfs[: args.limit]

    print(f"documents to process: {len(pdfs)}", flush=True)

    skipped: list[dict[str, object]] = []
    all_chunks: list[Chunk] = []
    seen: set[str] = set()
    per_doc: list[dict[str, object]] = []

    for number, path in enumerate(pdfs, start=1):
        size = path.stat().st_size
        label = path.relative_to(KNOWLEDGE_DIR)
        if args.max_mb and size > args.max_mb * 1024 * 1024:
            skipped.append({"path": str(label), "bytes": size, "reason": f"over {args.max_mb} MB"})
            print(f"[{number}/{len(pdfs)}] SKIP {label} ({size / 1e6:.1f} MB, over limit)", flush=True)
            continue
        if size < MIN_BYTES:
            skipped.append({"path": str(label), "bytes": size, "reason": "too small, empty shell"})
            print(f"[{number}/{len(pdfs)}] SKIP {label} ({size} B)", flush=True)
            continue
        try:
            doc = load_doc(path)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            skipped.append({"path": str(label), "bytes": size, "reason": f"parse error: {exc}"})
            print(f"[{number}/{len(pdfs)}] FAIL {label}: {exc}", flush=True)
            continue

        chunks = chunk_doc(doc)
        unique = [c for c in chunks if c.sha256 not in seen]
        duplicates = len(chunks) - len(unique)
        seen.update(c.sha256 for c in unique)
        all_chunks.extend(unique)
        per_doc.append(
            {
                "path": str(label),
                "title": doc.title,
                "folder": doc.folder,
                "bytes": size,
                "pages": len(doc.pages),
                "empty_pages": sum(1 for p in doc.pages if not p),
                "chunks": len(unique),
                "duplicate_chunks_dropped": duplicates,
            }
        )
        print(
            f"[{number}/{len(pdfs)}] {label}: pages={len(doc.pages)} chunks={len(unique)} dup={duplicates}",
            flush=True,
        )

    print(f"\nchunks total: {len(all_chunks)}  documents ok: {len(per_doc)}  skipped: {len(skipped)}")

    if args.dry:
        OUT_DIR.joinpath("manifest-dry.json").write_text(
            json.dumps({"documents": per_doc, "skipped": skipped, "chunks": len(all_chunks)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("dry run: wrote manifest-dry.json, no embeddings computed")
        return

    embedder = Embedder()
    out_path = OUT_DIR / "knowledge_chunks.jsonl"
    started = time.time()
    with out_path.open("w", encoding="utf-8") as handle:
        for start in range(0, len(all_chunks), BATCH):
            batch = all_chunks[start : start + BATCH]
            vectors = embedder.embed([c.text for c in batch])
            for chunk, vector in zip(batch, vectors, strict=True):
                record = {
                    "title": chunk.title,
                    "folder": chunk.folder,
                    "page": chunk.page,
                    "printed_page": chunk.printed_page,
                    "ordinal": chunk.ordinal,
                    "sha256": chunk.sha256,
                    "text": chunk.text,
                    "embedding": vector,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            done = min(start + BATCH, len(all_chunks))
            elapsed = time.time() - started
            rate = done / elapsed if elapsed else 0
            eta = (len(all_chunks) - done) / rate if rate else 0
            print(f"  embedded {done}/{len(all_chunks)}  ({rate:.1f}/s, eta {eta:.0f}s)", flush=True)

    manifest = {
        "model": EMBED_MODEL,
        "dim": EMBED_DIM,
        "chunk_chars": CHUNK_CHARS,
        "documents": per_doc,
        "skipped": skipped,
        "chunks": len(all_chunks),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT_DIR.joinpath("manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
