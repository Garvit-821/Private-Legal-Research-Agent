import os
import json
import math
import re
from collections import Counter
from typing import List, Dict, Any, Optional, Set, Tuple

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from session import runtime, MAX_DOCUMENTS
from schemas.v1 import (
    ChatRequest,
    AgentSelectRequest,
    AgentPullRequest,
    envelope_ok,
    envelope_error,
    sse_line,
    ApiError,
)
from agents.registry import (
    load_catalog,
    get_chat_profile,
    get_embed_profile,
    fetch_installed_tags,
    is_installed,
    build_agent_list,
)
from agents.compatibility import compatibility_label
from agents.pull_jobs import create_pull_job, stream_ollama_pull, get_pull_job
from system.profiler import collect_system_specs
from chat.budget import (
    trim_history,
    to_langchain_messages,
    apply_chunk_budget,
    shrink_history_for_budget,
    history_cap_for_profile,
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHUNK_TARGET_SIZE = int(os.getenv("CORTEX_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP_SIZE = int(os.getenv("CORTEX_CHUNK_OVERLAP", "200"))
ALLOWED_EXTENSIONS = (".txt", ".pdf", ".docx", ".md", ".markdown")

COMPARISON_TRIGGERS: Set[str] = {
    "compare", "comparison", "differentiate", "difference", "differences",
    "contrast", "versus", "vs", "both", "all documents", "all files",
    "summarize all", "overview", "which is better", "what are the differences",
    "how do they differ", "what's the difference", "tell me about both",
    "explain both", "analyze both", "review both",
}

SUGGESTION_DELIMITER = "---"
_embeddings_client: Optional[OllamaEmbeddings] = None
_embeddings_model: Optional[str] = None

app = FastAPI(title="Local-Cortex API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def json_ok(event_type: str, data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=envelope_ok(event_type, data))


def json_fail(event_type: str, code: str, message: str, status_code: int = 400, details=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=envelope_error(event_type, code, message, details),
    )


def get_embeddings() -> OllamaEmbeddings:
    global _embeddings_client, _embeddings_model
    model = runtime.embed_agent_id
    if _embeddings_client is None or _embeddings_model != model:
        _embeddings_client = OllamaEmbeddings(model=model, base_url=OLLAMA_BASE_URL)
        _embeddings_model = model
    return _embeddings_client


def get_chat_llm(profile) -> ChatOllama:
    return ChatOllama(
        model=profile.ollama_tag,
        temperature=profile.temperature,
        num_predict=profile.num_predict,
        base_url=OLLAMA_BASE_URL,
    )


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(x * y for x, y in zip(v1, v2))
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(x * x for x in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def extract_suggestions(text: str) -> List[str]:
    suggestions: List[str] = []
    for line in text.splitlines():
        match = re.match(r"^(?:SUGGESTION:|💡\s*Suggestion:)\s*(.+)$", line.strip(), re.IGNORECASE)
        if match:
            question = match.group(1).strip().strip("'\"")
            if question:
                suggestions.append(question)
        if len(suggestions) >= 2:
            break
    return suggestions[:2]


def split_answer_and_suggestions(text: str) -> Tuple[str, List[str]]:
    if not text:
        return "", []
    working = text.split(SUGGESTION_DELIMITER, 1)[0] if SUGGESTION_DELIMITER in text else text
    lines = []
    for line in working.splitlines():
        if re.match(r"^(?:SUGGESTION:|💡\s*Suggestion:)", line.strip(), re.IGNORECASE):
            continue
        lines.append(line)
    return "\n".join(lines).strip(), extract_suggestions(text)


def chunk_document(content: str, target_size: int = CHUNK_TARGET_SIZE, overlap_size: int = CHUNK_OVERLAP_SIZE) -> List[Dict[str, Any]]:
    lines = content.splitlines()
    chunks = []
    if not lines:
        return chunks
    i = 0
    n = len(lines)
    while i < n:
        chunk_lines = []
        curr_size = 0
        start_line = i + 1
        while i < n and (curr_size < target_size or len(chunk_lines) < 3):
            line = lines[i]
            chunk_lines.append(line)
            curr_size += len(line) + 1
            i += 1
        chunk_text = "\n".join(chunk_lines)
        chunks.append({"text": chunk_text, "start_line": start_line, "end_line": i})
        if i >= n:
            break
        back_size = 0
        back_lines = 0
        for j in range(i - 1, start_line - 1, -1):
            line_len = len(lines[j]) + 1
            if back_size + line_len <= overlap_size:
                back_size += line_len
                back_lines += 1
            else:
                break
        if back_lines > 0:
            i -= back_lines
    return chunks


class ChatMessageSchema(BaseModel):
    role: str
    content: str


class ChatRequestLegacy(BaseModel):
    message: str
    history: List[ChatMessageSchema] = []


def extract_text_from_bytes(filename: str, contents: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".txt":
        return contents.decode("utf-8", errors="replace")
    if ext in (".md", ".markdown"):
        return contents.decode("utf-8", errors="replace")
    if ext == ".docx":
        import io
        import docx
        doc = docx.Document(io.BytesIO(contents))
        return "\n".join(p.text for p in doc.paragraphs)
    if ext == ".pdf":
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(contents))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(f"Unsupported file format: {ext}")


def _embed_chunks(chunks: List[Dict[str, Any]]) -> None:
    if not chunks:
        return
    texts = [c["text"] for c in chunks]
    try:
        vectors = get_embeddings().embed_documents(texts)
    except Exception:
        fallback = "qwen2.5:3b"
        if runtime.embed_agent_id != fallback:
            runtime.embed_agent_id = fallback
            global _embeddings_client, _embeddings_model
            _embeddings_client = None
            _embeddings_model = None
            vectors = get_embeddings().embed_documents(texts)
        else:
            raise
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector


def retrieve_matched_chunks(user_query: str, profile) -> List[Dict[str, Any]]:
    query_lower = user_query.lower()
    is_comparison = any(trigger in query_lower for trigger in COMPARISON_TRIGGERS)
    num_docs = len(runtime.documents)
    slots = profile.retrieval.comparison_slots_per_doc if is_comparison else profile.retrieval.slots_per_doc
    total_cap = profile.retrieval.max_total_chunks

    query_emb = get_embeddings().embed_query(user_query)
    matched: List[Dict[str, Any]] = []

    if is_comparison:
        for _, doc in runtime.documents.items():
            doc_scored = []
            for chunk in doc.get("chunks", []):
                if "embedding" not in chunk:
                    continue
                c = {k: v for k, v in chunk.items() if k != "embedding"}
                c["score"] = round(cosine_similarity(query_emb, chunk["embedding"]), 4)
                doc_scored.append(c)
            doc_scored.sort(key=lambda x: x["score"], reverse=True)
            matched.extend(doc_scored[:slots])
    else:
        per_doc_best: Dict[str, List[Dict[str, Any]]] = {}
        all_scored: List[Dict[str, Any]] = []
        for fname, doc in runtime.documents.items():
            doc_scored = []
            for chunk in doc.get("chunks", []):
                if "embedding" not in chunk:
                    continue
                c = {k: v for k, v in chunk.items() if k != "embedding"}
                c["score"] = round(cosine_similarity(query_emb, chunk["embedding"]), 4)
                doc_scored.append(c)
                all_scored.append(c)
            doc_scored.sort(key=lambda x: x["score"], reverse=True)
            per_doc_best[fname] = doc_scored[:slots]

        seen: Set[Tuple[str, int]] = set()
        for chunks in per_doc_best.values():
            for c in chunks:
                key = (c["filename"], c["start_line"])
                if key not in seen:
                    matched.append(c)
                    seen.add(key)
        all_scored.sort(key=lambda x: x["score"], reverse=True)
        for c in all_scored:
            if len(matched) >= max(num_docs * slots, 6):
                break
            key = (c["filename"], c["start_line"])
            if key not in seen:
                matched.append(c)
                seen.add(key)

    matched.sort(key=lambda x: x.get("score", 0), reverse=True)
    return matched[:total_cap]


async def reindex_all_documents() -> Dict[str, Any]:
    global _embeddings_client, _embeddings_model
    _embeddings_client = None
    _embeddings_model = None
    count = 0
    for doc in runtime.documents.values():
        chunks = doc.get("chunks", [])
        for chunk in chunks:
            chunk.pop("embedding", None)
        _embed_chunks(chunks)
        count += len(chunks)
    return {"documents": len(runtime.documents), "chunks_reindexed": count, "embed_model": runtime.embed_agent_id}


@app.get("/api/system/specs")
async def system_specs():
    specs = await collect_system_specs()
    return json_ok("system.specs", specs.model_dump())


@app.get("/api/agents")
async def list_agents():
    specs = await collect_system_specs()
    installed = await fetch_installed_tags()
    groups = build_agent_list(specs, installed)
    profile = get_chat_profile(runtime.chat_agent_id)
    return json_ok(
        "agent.list",
        {
            "system": specs.model_dump(),
            "current": {
                "chat_agent_id": runtime.chat_agent_id,
                "embed_agent_id": runtime.embed_agent_id,
                "profile": profile.model_dump() if profile else None,
                "history_cap": history_cap_for_profile(profile) if profile else runtime.max_history_messages,
            },
            **{k: [item.model_dump() for item in v] for k, v in groups.items()},
            "installed_tags": sorted(installed),
        },
    )


@app.get("/api/agents/current")
async def current_agent():
    profile = get_chat_profile(runtime.chat_agent_id)
    if not profile:
        return json_fail("agent.current", "AGENT_NOT_FOUND", "Active agent profile not found", 404)
    return json_ok(
        "agent.current",
        {
            "chat_agent_id": runtime.chat_agent_id,
            "embed_agent_id": runtime.embed_agent_id,
            "profile": profile.model_dump(),
            "history_cap": history_cap_for_profile(profile),
        },
    )


@app.post("/api/agents/select")
async def select_agent(payload: AgentSelectRequest):
    profile = get_chat_profile(payload.agent_id)
    if not profile:
        return json_fail("agent.select", "AGENT_NOT_FOUND", f"Unknown agent: {payload.agent_id}", 404)

    specs = await collect_system_specs()
    label = compatibility_label(specs, profile)
    if label == "incompatible":
        return json_fail(
            "agent.select",
            "INCOMPATIBLE_AGENT",
            "This agent exceeds your system specifications.",
            400,
            {"compatibility": label, "agent_id": payload.agent_id},
        )

    installed = await fetch_installed_tags()
    if not is_installed(profile.ollama_tag, installed):
        return json_ok(
            "agent.select",
            {
                "status": "pull_required",
                "agent_id": profile.id,
                "ollama_tag": profile.ollama_tag,
            },
        )

    runtime.chat_agent_id = profile.id
    return json_ok(
        "agent.select",
        {
            "status": "ok",
            "chat_agent_id": runtime.chat_agent_id,
            "profile": profile.model_dump(),
            "history_cap": history_cap_for_profile(profile),
        },
    )


@app.post("/api/agents/pull")
async def pull_agent(payload: AgentPullRequest):
    profile = get_chat_profile(payload.agent_id)
    if not profile:
        return json_fail("agent.pull", "AGENT_NOT_FOUND", f"Unknown agent: {payload.agent_id}", 404)

    job_id = create_pull_job(profile.id, profile.ollama_tag)

    async def pull_stream():
        async for line in stream_ollama_pull(profile.ollama_tag, job_id):
            yield line
        runtime.chat_agent_id = profile.id
        yield sse_line("agent.pull.selected", {"agent_id": profile.id, "ollama_tag": profile.ollama_tag})

    return StreamingResponse(pull_stream(), media_type="text/event-stream")


@app.get("/api/agents/pull/{job_id}")
async def pull_status(job_id: str):
    job = get_pull_job(job_id)
    if not job:
        return json_fail("agent.pull.status", "JOB_NOT_FOUND", "Pull job not found", 404)
    return json_ok("agent.pull.status", job)


@app.post("/api/agents/reindex")
async def reindex_documents():
    if not runtime.documents:
        return json_fail("agent.reindex", "NO_DOCUMENTS", "No documents loaded to reindex", 400)
    try:
        result = await reindex_all_documents()
        return json_ok("agent.reindex", result)
    except Exception as exc:
        return json_fail("agent.reindex", "REINDEX_FAILED", str(exc), 500)


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        return json_fail("document.upload", "INVALID_FORMAT", "Unsupported file format", 400)

    if len(runtime.documents) >= MAX_DOCUMENTS and filename not in runtime.documents:
        return json_fail("document.upload", "DOCUMENT_LIMIT", f"Maximum of {MAX_DOCUMENTS} documents reached", 400)

    try:
        contents = await file.read()
        text_content = extract_text_from_bytes(filename, contents)
        lines = text_content.splitlines()
        chunks = chunk_document(text_content)
        for c in chunks:
            c["filename"] = filename
        _embed_chunks(chunks)
        metrics = {
            "chars": len(text_content),
            "words": len(text_content.split()),
            "lines": len(lines),
            "chunks": len(chunks),
        }
        runtime.documents[filename] = {
            "content": text_content,
            "lines": lines,
            "chunks": chunks,
            "metrics": metrics,
        }
        runtime.active_filename = filename
        return json_ok(
            "document.uploaded",
            {"status": "success", "filename": filename, "metrics": metrics, "documents": list(runtime.documents.keys())},
        )
    except Exception as exc:
        return json_fail("document.upload", "UPLOAD_FAILED", str(exc), 500)


@app.get("/api/document")
async def get_document():
    if not runtime.active_filename or runtime.active_filename not in runtime.documents:
        return json_ok("document.state", {"status": "empty", "documents": list(runtime.documents.keys())})
    active_doc = runtime.documents[runtime.active_filename]
    return json_ok(
        "document.state",
        {
            "filename": runtime.active_filename,
            "content": active_doc["content"],
            "metrics": active_doc["metrics"],
            "documents": list(runtime.documents.keys()),
        },
    )


@app.post("/api/select")
async def select_document(payload: dict = Body(...)):
    filename = payload.get("filename")
    if not filename or filename not in runtime.documents:
        return json_fail("document.select", "NOT_FOUND", "Document not found", 404)
    runtime.active_filename = filename
    return json_ok("document.selected", {"status": "success", "active_filename": runtime.active_filename})


@app.post("/api/delete")
async def delete_document(payload: dict = Body(...)):
    filename = payload.get("filename")
    if not filename or filename not in runtime.documents:
        return json_fail("document.delete", "NOT_FOUND", "Document not found", 404)
    del runtime.documents[filename]
    if runtime.active_filename == filename:
        runtime.active_filename = next(iter(runtime.documents), None)
    return json_ok(
        "document.deleted",
        {
            "status": "success",
            "active_filename": runtime.active_filename,
            "documents": list(runtime.documents.keys()),
        },
    )


@app.post("/api/clear")
async def clear_document():
    runtime.documents = {}
    runtime.active_filename = None
    return json_ok("document.cleared", {"status": "cleared"})


@app.post("/api/chat")
async def chat_interaction(payload: ChatRequestLegacy):
    if not runtime.documents:
        raise HTTPException(status_code=400, detail="No documents have been uploaded yet.")

    profile = get_chat_profile(runtime.chat_agent_id)
    if not profile:
        raise HTTPException(status_code=500, detail="Active chat agent profile is not configured.")

    user_query = payload.message.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    raw_history = [{"role": m.role, "content": m.content} for m in payload.history]
    trimmed = trim_history(raw_history, profile)

    try:
        matched_chunks = retrieve_matched_chunks(user_query, profile)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve context: {exc}") from exc

    context_parts = [
        f"[Document: {c['filename']}, Lines {c['start_line']}-{c['end_line']}]:\n{c['text']}"
        for c in matched_chunks
    ]
    context_str = "\n\n---\n\n".join(context_parts)
    matched_chunks, budget = apply_chunk_budget(matched_chunks, profile, context_str, trimmed)
    trimmed = shrink_history_for_budget(trimmed, profile, context_str, profile.context_window_tokens)

    doc_names = ", ".join(runtime.documents.keys())
    num_docs = len(runtime.documents)
    system_prompt = (
        f"You are a strict, fact-based AI Document Assistant analyzing {num_docs} document(s): {doc_names}.\n"
        f"Active agent: {profile.display_name}.\n\n"
        "--- DOCUMENT CONTEXT START ---\n"
        f"{context_str}\n"
        "--- DOCUMENT CONTEXT END ---\n\n"
        "INSTRUCTIONS:\n"
        "- Answer using ONLY the provided document context.\n"
        "- Never repeat or restate the user's question.\n"
        "- Name source files when citing facts.\n"
        "- If the answer is not in the documents, say: I cannot find that in the documents.\n"
        "- After your answer, output a line with exactly three dashes (---), then two follow-up questions.\n"
        "- Each follow-up on its own line starting with SUGGESTION:"
    )

    chat_history = to_langchain_messages(trimmed)
    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}"),
    ])

    async def response_generator():
        try:
            llm = get_chat_llm(profile)
            formatted_prompt = prompt_template.format_messages(chat_history=chat_history, user_input=user_query)

            yield sse_line(
                "chat.metadata",
                {
                    "agent_id": profile.id,
                    "chunks": matched_chunks,
                    "budget": budget.model_dump(),
                },
            )

            full_text = ""
            suggestion_started = False
            pending = ""
            holdback = 24

            async for chunk in llm.astream(formatted_prompt):
                piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content or "")
                if not piece:
                    continue
                full_text += piece
                if suggestion_started:
                    continue

                combined = pending + piece
                boundary = combined.find(f"\n{SUGGESTION_DELIMITER}")
                if boundary == -1:
                    boundary = combined.find("\nSUGGESTION:")

                if boundary != -1:
                    to_emit = combined[:boundary]
                    if to_emit:
                        yield sse_line("chat.token", {"text": to_emit})
                    pending = ""
                    suggestion_started = True
                    continue

                if len(combined) > holdback:
                    yield sse_line("chat.token", {"text": combined[:-holdback]})
                    pending = combined[-holdback:]
                else:
                    pending = combined

            if pending and not suggestion_started:
                yield sse_line("chat.token", {"text": pending})

            answer, suggestions = split_answer_and_suggestions(full_text)
            if suggestions:
                yield sse_line("chat.suggestions", {"items": suggestions})

            yield sse_line("chat.done", {"agent_id": profile.id, "answer_preview": answer[:200]})
        except Exception as exc:
            yield sse_line("chat.error", error=ApiError(code="INFERENCE_FAILED", message=str(exc)))

    return StreamingResponse(response_generator(), media_type="text/event-stream")


# Backward-compatible document responses for legacy frontend fields
@app.get("/api/document/legacy")
async def get_document_legacy():
    response = await get_document()
    return response


if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, reload=True)
