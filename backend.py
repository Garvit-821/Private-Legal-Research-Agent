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

from langchain_ollama import ChatOllama
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
        self.filename: Optional[str] = None
        self.content: Optional[str] = None
        self.lines: List[str] = []
        self.chunks: List[Dict[str, Any]] = []
        self.tfidf: Optional['SimpleTFIDF'] = None
        self.metrics: Dict[str, int] = {"chars": 0, "words": 0, "lines": 0}

doc_state = DocumentState()


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
        
    try:
        contents = await file.read()
        text_content = extract_text_from_bytes(file.filename, contents)
        
        # Ingest state
        doc_state.filename = file.filename
        doc_state.content = text_content
        doc_state.lines = text_content.splitlines()
        
        # Process and index
        doc_state.chunks = chunk_document(text_content)
        doc_state.tfidf = SimpleTFIDF(doc_state.chunks)
        
        # Generate metrics
        doc_state.metrics = {
            "chars": len(text_content),
            "words": len(text_content.split()),
            "lines": len(doc_state.lines),
            "chunks": len(doc_state.chunks)
        }
        
        return {
            "status": "success",
            "filename": file.filename,
            "metrics": doc_state.metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@app.get("/api/document")
async def get_document():
    if doc_state.content is None:
        return {"status": "empty"}
    return {
        "filename": doc_state.filename,
        "content": doc_state.content,
        "metrics": doc_state.metrics
    }


@app.post("/api/clear")
async def clear_document():
    doc_state.filename = None
    doc_state.content = None
    doc_state.lines = []
    doc_state.chunks = []
    doc_state.tfidf = None
    doc_state.metrics = {"chars": 0, "words": 0, "lines": 0}
    return {"status": "cleared"}


@app.post("/api/chat")
async def chat_interaction(payload: ChatRequestSchema):
    if doc_state.content is None:
        raise HTTPException(status_code=400, detail="No document has been ingested yet.")
        
    user_query = payload.message
    
    # 1. Retrieve Context
    # If the document is small (under 6000 chars), pass the entire document to ensure 100% context precision.
    # Otherwise, perform a TF-IDF keyword search to retrieve the top 3 relevant sections.
    is_large_doc = doc_state.metrics["chars"] >= 6000
    
    if is_large_doc:
        retrieved = doc_state.tfidf.search(user_query, top_k=3)
        context_str = "\n\n---\n\n".join([f"[Lines {c['start_line']}-{c['end_line']}]: {c['text']}" for c in retrieved])
        matched_chunks = retrieved
    else:
        # For small documents, we still calculate the top matches for visual UI highlighting,
        # but the LLM receives the full context.
        matched_chunks = doc_state.tfidf.search(user_query, top_k=2) if doc_state.tfidf else []
        context_str = doc_state.content

    # 2. System Instructions
    system_prompt = (
        "You are an interactive local AI Document Assistant.\n\n"
        "--- DOCUMENT CONTEXT START ---\n"
        f"{context_str}\n"
        "--- DOCUMENT CONTEXT END ---\n\n"
        "INSTRUCTIONS:\n"
        "- Answer the user's question using ONLY the provided document context.\n"
        "- If the answer cannot be determined from the document context, say 'I cannot find that in the document.'\n"
        "- Extract metrics, numbers, and risks explicitly.\n"
        "- Formatting requirement: Always format key technical fields, dates, and amounts in **bold** or use clean Markdown block quotes.\n"
        "- CRITICAL: At the very end of your response, you MUST provide exactly 2 relevant, "
        "clickable-style 'Suggested Follow-up Questions' based on what was just discussed or hidden details in the doc. "
        "Format them as bullet points starting with '💡 Suggestion:'."
    )

    # 3. Assemble chat history
    chat_history = []
    # Limit history window to last 6 messages to stay lightweight on system RAM
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
        ("human", "{user_input}")
    ])
    
    # 4. Stream response generator
    async def response_generator():
        try:
            # Initialize Ollama model
            llm = ChatOllama(
                model="qwen2.5:3b",
                temperature=0.3,
                num_predict=512
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
