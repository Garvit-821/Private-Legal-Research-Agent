import os
import json
import math
import re
from collections import Counter
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

app = FastAPI(title="Local-Cortex API")

# Enable CORS for easy local developments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory storage for the uploaded document
# In a production environment, this would be a database or session-based store,
# but for a local single-user utility, global state is fast and reliable.
class DocumentState:
    def __init__(self):
        # A dictionary mapping filename to document data:
        # {
        #     "filename": str,
        #     "content": str,
        #     "lines": List[str],
        #     "chunks": List[Dict[str, Any]],
        #     "metrics": Dict[str, int]
        # }
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.active_filename: Optional[str] = None

doc_state = DocumentState()

# Initialize Ollama embeddings globally
embeddings = OllamaEmbeddings(model="qwen2.5:3b")

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(x * y for x, y in zip(v1, v2))
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(x * x for x in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class SimpleTFIDF:
    def __init__(self, chunks: List[Dict[str, Any]]):
        self.chunks = chunks
        self.doc_term_freqs = []
        self.vocab = set()
        
        # Tokenize and build frequency count for each chunk
        for chunk in chunks:
            tokens = self.tokenize(chunk["text"])
            self.doc_term_freqs.append(Counter(tokens))
            self.vocab.update(tokens)
            
        self.num_docs = len(chunks)
        self.idf = {}
        for term in self.vocab:
            doc_count = sum(1 for tf in self.doc_term_freqs if term in tf)
            # Standard IDF with smoothing
            self.idf[term] = math.log((1 + self.num_docs) / (1 + doc_count)) + 1

    def tokenize(self, text: str) -> List[str]:
        # Lowercase and extract alphanumeric words
        return re.findall(r'\b\w+\b', text.lower())

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        query_tokens = self.tokenize(query)
        if not query_tokens or not self.chunks:
            return self.chunks[:top_k]
            
        query_counter = Counter(query_tokens)
        
        scores = []
        for idx, doc_tf in enumerate(self.doc_term_freqs):
            dot_product = 0.0
            for term, q_count in query_counter.items():
                if term in doc_tf:
                    # Query TF-IDF * Doc TF-IDF
                    dot_product += (q_count * self.idf.get(term, 0)) * (doc_tf[term] * self.idf.get(term, 0))
            
            # Compute document vector length (TF-IDF weighted)
            doc_len_tfidf = math.sqrt(sum((count * self.idf.get(term, 0))**2 for term, count in doc_tf.items()))
            query_len_tfidf = math.sqrt(sum((count * self.idf.get(term, 0))**2 for term, count in query_counter.items()))
            
            similarity = 0.0
            if doc_len_tfidf > 0 and query_len_tfidf > 0:
                similarity = dot_product / (doc_len_tfidf * query_len_tfidf)
                
            scores.append((similarity, idx))
            
        # Sort by similarity descending
        scores.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for sim, idx in scores[:top_k]:
            chunk_data = self.chunks[idx].copy()
            chunk_data["score"] = round(sim, 4)
            results.append(chunk_data)
            
        return results


def chunk_document(content: str, target_size: int = 1000, overlap_size: int = 200) -> List[Dict[str, Any]]:
    """
    Chunks a document line-by-line to maintain line-level traceability.
    Each chunk retains its starting and ending line numbers (1-indexed).
    """
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
        
        # Accumulate lines up to target size
        while i < n and (curr_size < target_size or len(chunk_lines) < 3):
            line = lines[i]
            chunk_lines.append(line)
            curr_size += len(line) + 1  # +1 for newline character
            i += 1
            
        end_line = i
        chunk_text = "\n".join(chunk_lines)
        chunks.append({
            "text": chunk_text,
            "start_line": start_line,
            "end_line": end_line
        })
        
        if i >= n:
            break
            
        # Walk back line pointer for overlap
        back_size = 0
        back_lines = 0
        # Go backwards from i-1 to start_line (exclusive of start_line to guarantee loop progress)
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

class ChatRequestSchema(BaseModel):
    message: str
    history: List[ChatMessageSchema]


def extract_text_from_bytes(filename: str, contents: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext == '.txt':
        return contents.decode("utf-8", errors="replace")
    elif ext in ('.md', '.markdown'):
        return contents.decode("utf-8", errors="replace")
    elif ext == '.docx':
        import io
        import docx
        doc = docx.Document(io.BytesIO(contents))
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs)
    elif ext == '.pdf':
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(contents))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    filename_lower = file.filename.lower()
    allowed_extensions = ('.txt', '.pdf', '.docx', '.md', '.markdown')
    if not filename_lower.endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .pdf, .docx, .md, or .txt files.")
        
    if len(doc_state.documents) >= 5 and file.filename not in doc_state.documents:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 documents reached. Please delete an existing file first.")
        
    try:
        contents = await file.read()
        text_content = extract_text_from_bytes(file.filename, contents)
        
        # Parse structure and chunk
        lines = text_content.splitlines()
        chunks = chunk_document(text_content)
        
        # Inject filename into chunks
        for c in chunks:
            c["filename"] = file.filename
            
        # Generate embeddings in batch via Ollama
        if chunks:
            texts = [c["text"] for c in chunks]
            embeddings_list = embeddings.embed_documents(texts)
            for chunk, emb in zip(chunks, embeddings_list):
                chunk["embedding"] = emb
        
        # Generate metrics
        metrics = {
            "chars": len(text_content),
            "words": len(text_content.split()),
            "lines": len(lines),
            "chunks": len(chunks)
        }
        
        doc_state.documents[file.filename] = {
            "content": text_content,
            "lines": lines,
            "chunks": chunks,
            "metrics": metrics
        }
        doc_state.active_filename = file.filename
        
        return {
            "status": "success",
            "filename": file.filename,
            "metrics": metrics,
            "documents": list(doc_state.documents.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@app.get("/api/document")
async def get_document():
    if not doc_state.active_filename or doc_state.active_filename not in doc_state.documents:
        return {
            "status": "empty",
            "documents": list(doc_state.documents.keys())
        }
        
    active_doc = doc_state.documents[doc_state.active_filename]
    return {
        "filename": doc_state.active_filename,
        "content": active_doc["content"],
        "metrics": active_doc["metrics"],
        "documents": list(doc_state.documents.keys())
    }


@app.post("/api/select")
async def select_document(payload: dict = Body(...)):
    filename = payload.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
        
    if filename in doc_state.documents:
        doc_state.active_filename = filename
        return {
            "status": "success",
            "active_filename": doc_state.active_filename
        }
    else:
        raise HTTPException(status_code=404, detail="Document not found.")


@app.post("/api/delete")
async def delete_document(payload: dict = Body(...)):
    filename = payload.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
        
    if filename in doc_state.documents:
        del doc_state.documents[filename]
        
        # Update active filename if the active document was deleted
        if doc_state.active_filename == filename:
            if doc_state.documents:
                doc_state.active_filename = list(doc_state.documents.keys())[0]
            else:
                doc_state.active_filename = None
                
        return {
            "status": "success",
            "active_filename": doc_state.active_filename,
            "documents": list(doc_state.documents.keys())
        }
    else:
        raise HTTPException(status_code=404, detail="Document not found.")


@app.post("/api/clear")
async def clear_document():
    doc_state.documents = {}
    doc_state.active_filename = None
    return {"status": "cleared"}


@app.post("/api/chat")
async def chat_interaction(payload: ChatRequestSchema):
    if not doc_state.documents:
        raise HTTPException(status_code=400, detail="No documents have been uploaded yet.")
        
    user_query = payload.message
    
    try:
        # 1. Detect whether this is a comparison / overview / meta query.
        # For these we ignore similarity scores and instead take the top N
        # chunks from EVERY document directly (full-scan mode), so abstract
        # phrases like "differentiate", "compare", "summarize all" never miss
        # relevant content due to low embedding similarity.
        COMPARISON_TRIGGERS = {
            "compare", "comparison", "differentiate", "difference", "differences",
            "contrast", "versus", "vs", "both", "all documents", "all files",
            "summarize all", "overview", "which is better", "what are the differences",
            "how do they differ", "what's the difference", "tell me about both",
            "explain both", "analyze both", "review both"
        }
        query_lower = user_query.lower()
        is_comparison = any(trigger in query_lower for trigger in COMPARISON_TRIGGERS)

        num_docs = len(doc_state.documents)

        if is_comparison:
            # Full-scan mode: take top 3 chunks per document, ordered by score
            # but guaranteed to span every file.
            query_emb = embeddings.embed_query(user_query)
            SCAN_PER_DOC = 3
            matched_chunks: List[Dict[str, Any]] = []
            for fname, doc in doc_state.documents.items():
                doc_scored = []
                for chunk in doc["chunks"]:
                    if "embedding" not in chunk:
                        continue
                    sim = cosine_similarity(query_emb, chunk["embedding"])
                    c = chunk.copy()
                    c["score"] = round(sim, 4)
                    del c["embedding"]
                    doc_scored.append(c)
                doc_scored.sort(key=lambda x: x["score"], reverse=True)
                matched_chunks.extend(doc_scored[:SCAN_PER_DOC])
            # Re-sort the combined set by score for prompt clarity
            matched_chunks.sort(key=lambda x: x["score"], reverse=True)
        else:
            # Standard balanced retrieval: embed the query, guarantee 2 chunks
            # per doc, then pad remaining slots with globally best chunks.
            query_emb = embeddings.embed_query(user_query)
            SLOTS_PER_DOC = 2
            TOTAL_SLOTS = max(num_docs * SLOTS_PER_DOC, 6)

            per_doc_best: Dict[str, List[Dict[str, Any]]] = {}
            all_scored: List[Dict[str, Any]] = []

            for fname, doc in doc_state.documents.items():
                doc_scored = []
                for chunk in doc["chunks"]:
                    if "embedding" not in chunk:
                        continue
                    sim = cosine_similarity(query_emb, chunk["embedding"])
                    c = chunk.copy()
                    c["score"] = round(sim, 4)
                    del c["embedding"]
                    doc_scored.append(c)
                    all_scored.append(c)
                doc_scored.sort(key=lambda x: x["score"], reverse=True)
                per_doc_best[fname] = doc_scored[:SLOTS_PER_DOC]

            guaranteed: List[Dict[str, Any]] = []
            seen_ids: set = set()
            for fname, chunks in per_doc_best.items():
                for c in chunks:
                    key = (c["filename"], c["start_line"])
                    if key not in seen_ids:
                        guaranteed.append(c)
                        seen_ids.add(key)

            all_scored.sort(key=lambda x: x["score"], reverse=True)
            for c in all_scored:
                if len(guaranteed) >= TOTAL_SLOTS:
                    break
                key = (c["filename"], c["start_line"])
                if key not in seen_ids:
                    guaranteed.append(c)
                    seen_ids.add(key)

            matched_chunks = sorted(guaranteed, key=lambda x: x["score"], reverse=True)

        # Format context — clearly label each document section
        context_parts = []
        for c in matched_chunks:
            context_parts.append(
                f"[Document: {c['filename']}, Lines {c['start_line']}-{c['end_line']}]:\n{c['text']}"
            )
        context_str = "\n\n---\n\n".join(context_parts)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve context: {str(e)}")

    # Build a clear document list for the system prompt header
    doc_names = ", ".join(doc_state.documents.keys())

    # 6. System Instructions
    system_prompt = (
        f"You are an interactive local AI Document Assistant currently analyzing {num_docs} document(s): {doc_names}.\n\n"
        "--- DOCUMENT CONTEXT START ---\n"
        f"{context_str}\n"
        "--- DOCUMENT CONTEXT END ---\n\n"
        "INSTRUCTIONS:\n"
        "- Answer the user's question using ONLY the provided document context.\n"
        "- IMPORTANT: When asked to compare, differentiate, contrast, or summarize across documents, you MUST do so using the context provided. Never refuse a comparison request — always answer using the document excerpts above.\n"
        "- Always explicitly name the source document (e.g. 'According to test_diet_a.txt...', 'In test_diet_b.txt...') so the user knows which file each fact came from.\n"
        "- Only say 'I cannot find that in the documents' when the specific fact is genuinely absent from ALL provided context excerpts.\n"
        "- Extract metrics, numbers, and risks explicitly.\n"
        "- Format key fields, dates, and amounts in **bold** or use Markdown block quotes.\n"
        "- CRITICAL SUGGESTION REQUIREMENT: At the very end of your response, provide exactly 2 relevant follow-up questions.\n"
        "  Format each on its own line starting exactly with '💡 Suggestion: ' followed by the question.\n"
        "  Example:\n"
        "  💡 Suggestion: What is the protein target in test_diet_a.txt?\n"
        "  💡 Suggestion: Which plan has lower carbohydrate intake?"
    )

    # 7. Assemble chat history
    chat_history = []
    trimmed_history = payload.history[-6:]
    for msg in trimmed_history:
        if msg.role == "user":
            chat_history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            chat_history.append(AIMessage(content=msg.content))

    # Create LangChain template
    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}\n\nIMPORTANT: At the end of your response, you MUST provide exactly 2 relevant suggested follow-up questions for the user. Format each on a new line starting exactly with '💡 Suggestion: ' followed by the question. Do not wrap them in bullets or headers.")
    ])
    
    # 8. Stream response generator
    async def response_generator():
        try:
            # Initialize Ollama model
            llm = ChatOllama(
                model="qwen2.5:3b",
                temperature=0.3,
                num_predict=768
            )
            
            formatted_prompt = prompt_template.format_messages(
                chat_history=chat_history,
                user_input=user_query
            )
            
            # Send matched chunks metadata first so the frontend can immediately highlight lines
            yield f"data: {json.dumps({'type': 'metadata', 'chunks': matched_chunks})}\n\n"
            
            # Stream the generated content
            async for chunk in llm.astream(formatted_prompt):
                if chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'text': chunk.content})}\n\n"
                    
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            # Send error details via stream
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(response_generator(), media_type="text/event-stream")

# Mount the static web resources folder at root
# It must be mounted after API routes to avoid routing conflicts
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, reload=True)
