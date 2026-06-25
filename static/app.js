// ==========================================================================
// LOCAL-CORTEX — OPEN-SOURCE LOCAL INTELLIGENCE ENGINE
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    const state = {
        filename: null,
        documents: [], // list of uploaded filenames
        metrics: { chars: 0, words: 0, lines: 0, chunks: 0 },
        documentLines: [],
        chatHistory: [],
        isThinking: false,
        isStreaming: false
    };

    // DOM
    const uploadModal = document.getElementById('uploadModal');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const btnSelectFile = document.getElementById('btnSelectFile');
    const btnOpenUpload = document.getElementById('btnOpenUpload');
    const btnPlaceholderUpload = document.getElementById('btnPlaceholderUpload');
    const uploadProgressContainer = document.getElementById('uploadProgressContainer');
    const uploadProgressBar = document.getElementById('uploadProgressBar');
    const uploadProgressStatus = document.getElementById('uploadProgressStatus');
    const uploadProgressPercent = document.getElementById('uploadProgressPercent');
    const loaderTitle = document.getElementById('loaderTitle');

    const valDocName = document.getElementById('valDocName');
    const valDocStatus = document.getElementById('valDocStatus');
    const valLines = document.getElementById('valLines');
    const valWords = document.getElementById('valWords');
    const valSession = document.getElementById('valSession');
    const valSessionDelta = document.getElementById('valSessionDelta');
    const metricSession = document.getElementById('metricSession');

    const activeDocName = document.getElementById('activeDocName');
    const docScanIndicator = document.getElementById('docScanIndicator');
    const documentViewport = document.getElementById('documentViewport');
    const docSearch = document.getElementById('docSearch');
    const btnScrollToTop = document.getElementById('btnScrollToTop');

    const chatLog = document.getElementById('chatLog');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const btnSubmitChat = document.getElementById('btnSubmitChat');
    const btnPurgeMemory = document.getElementById('btnPurgeMemory');
    const btnExportChat = document.getElementById('btnExportChat');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const agentStatus = document.getElementById('agentStatus');
    const toastContainer = document.getElementById('toastContainer');

    const documentTabsBar = document.getElementById('documentTabsBar');
    const tabsList = document.getElementById('tabsList');
    const btnTabAdd = document.getElementById('btnTabAdd');
    const contextBanner = document.getElementById('contextBanner');
    const contextDocPills = document.getElementById('contextDocPills');

    const bgCanvas = document.getElementById('bgCanvas');
    const loaderCanvas = document.getElementById('loaderCanvas');

    initParticleBackground();
    checkActiveDocument();

    // ==========================================================================
    // AMBIENT PARTICLE BACKGROUND
    // ==========================================================================
    function initParticleBackground() {
        const ctx = bgCanvas.getContext('2d');
        let particles = [];
        let animId = null;

        function resize() {
            bgCanvas.width = window.innerWidth;
            bgCanvas.height = window.innerHeight;
        }

        function createParticles() {
            const count = Math.min(80, Math.floor(window.innerWidth / 20));
            particles = Array.from({ length: count }, () => ({
                x: Math.random() * bgCanvas.width,
                y: Math.random() * bgCanvas.height,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                r: Math.random() * 1.5 + 0.5,
                alpha: Math.random() * 0.4 + 0.1
            }));
        }

        function draw() {
            ctx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);

            particles.forEach((p, i) => {
                p.x += p.vx;
                p.y += p.vy;
                if (p.x < 0) p.x = bgCanvas.width;
                if (p.x > bgCanvas.width) p.x = 0;
                if (p.y < 0) p.y = bgCanvas.height;
                if (p.y > bgCanvas.height) p.y = 0;

                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(139, 92, 246, ${p.alpha})`;
                ctx.fill();

                for (let j = i + 1; j < particles.length; j++) {
                    const q = particles[j];
                    const dx = p.x - q.x;
                    const dy = p.y - q.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 120) {
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(q.x, q.y);
                        ctx.strokeStyle = `rgba(0, 245, 255, ${0.06 * (1 - dist / 120)})`;
                        ctx.lineWidth = 0.5;
                        ctx.stroke();
                    }
                }
            });

            animId = requestAnimationFrame(draw);
        }

        resize();
        createParticles();
        draw();

        window.addEventListener('resize', () => {
            resize();
            createParticles();
        });

        return () => cancelAnimationFrame(animId);
    }

    // Loader particle burst
    let loaderAnimId = null;
    function startLoaderParticles() {
        if (!loaderCanvas) return;
        const ctx = loaderCanvas.getContext('2d');
        const rect = loaderCanvas.parentElement.getBoundingClientRect();
        loaderCanvas.width = rect.width;
        loaderCanvas.height = rect.height;

        const particles = Array.from({ length: 40 }, () => ({
            x: loaderCanvas.width / 2,
            y: loaderCanvas.height / 2,
            vx: (Math.random() - 0.5) * 3,
            vy: (Math.random() - 0.5) * 3,
            life: 1,
            color: Math.random() > 0.5 ? '0, 245, 255' : '139, 92, 246'
        }));

        function drawLoader() {
            ctx.clearRect(0, 0, loaderCanvas.width, loaderCanvas.height);
            let alive = false;

            particles.forEach(p => {
                if (p.life <= 0) return;
                alive = true;
                p.x += p.vx;
                p.y += p.vy;
                p.life -= 0.008;
                p.vx *= 0.99;
                p.vy *= 0.99;

                ctx.beginPath();
                ctx.arc(p.x, p.y, 2 * p.life, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${p.color}, ${p.life * 0.6})`;
                ctx.fill();
            });

            if (alive) {
                loaderAnimId = requestAnimationFrame(drawLoader);
            }
        }

        drawLoader();
    }

    function stopLoaderParticles() {
        if (loaderAnimId) cancelAnimationFrame(loaderAnimId);
        if (loaderCanvas) {
            const ctx = loaderCanvas.getContext('2d');
            ctx.clearRect(0, 0, loaderCanvas.width, loaderCanvas.height);
        }
    }

    // ==========================================================================
    // TOAST
    // ==========================================================================
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icons = { info: 'fa-circle-info', success: 'fa-circle-check', warn: 'fa-triangle-exclamation', error: 'fa-circle-xmark' };
        toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${message}</span>`;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'toastEnter 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.2) reverse forwards';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ==========================================================================
    // AGENT STATUS
    // ==========================================================================
    function setAgentStatus(mode, text) {
        agentStatus.className = 'agent-status' + (mode ? ` ${mode}` : '');
        agentStatus.querySelector('.agent-status-text').textContent = text;
    }

    function setSessionState(value, delta, deltaClass = 'delta-pos') {
        valSession.textContent = value;
        valSessionDelta.textContent = delta;
        valSessionDelta.className = `metric-delta ${deltaClass}`;
        metricSession.classList.toggle('thinking', value === 'THINKING' || value === 'STREAMING');
    }

    function formatTime() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // ==========================================================================
    // DOCUMENT INGESTION
    // ==========================================================================
    async function checkActiveDocument() {
        try {
            const res = await fetch('/api/document');
            const data = await res.json();

            state.documents = data.documents || [];
            if (data.filename) {
                state.filename = data.filename;
                state.metrics = data.metrics;
                state.documentLines = data.content.split('\n');
                renderDocument(data.content, true);
                updateTelemetryUI();
                closeIngestionModal();
                enableChatSystem();
                renderTabs();
                renderContextBanner();
                showToast(`Session restored: ${data.filename}`, 'success');
            } else {
                renderTabs();
                renderContextBanner();
                openIngestionModal();
            }
        } catch (err) {
            console.error(err);
            showToast('Failed to connect to Local-Cortex engine.', 'error');
        }
    }

    function openIngestionModal() {
        if (state.documents.length >= 5) {
            showToast('Maximum limit of 5 documents reached. Please delete an existing file first.', 'warn');
            return;
        }
        uploadModal.classList.remove('hidden');
        // Show the dismiss button only if the user already has documents loaded
        btnCloseModal.hidden = state.documents.length === 0;
        disableChatSystem();
    }

    function closeIngestionModal() {
        uploadModal.classList.add('hidden');
        btnCloseModal.hidden = true;
        if (state.filename) {
            enableChatSystem();
        }
    }

    function enableChatSystem() {
        chatInput.disabled = false;
        btnSubmitChat.disabled = false;
        chatInput.placeholder = 'Ask anything about your document(s)...';
        setAgentStatus('', 'Ready');
    }

    function disableChatSystem() {
        chatInput.disabled = true;
        btnSubmitChat.disabled = true;
        chatInput.placeholder = 'Upload a document first...';
        setAgentStatus('', 'Idle');
    }

    function shortenFilename(name) {
        if (!name) return '';
        if (name.length <= 15) return name;
        return name.substring(0, 10) + '...' + name.substring(name.length - 4);
    }

    function renderTabs() {
        if (!state.documents || state.documents.length === 0) {
            documentTabsBar.style.display = 'none';
            btnOpenUpload.style.opacity = '1';
            btnOpenUpload.disabled = false;
            return;
        }

        documentTabsBar.style.display = 'flex';
        tabsList.innerHTML = '';

        state.documents.forEach(docName => {
            const tab = document.createElement('div');
            tab.className = `doc-tab${docName === state.filename ? ' active' : ''}`;
            tab.setAttribute('data-filename', docName);
            tab.innerHTML = `
                <span class="tab-name" title="${escapeHTML(docName)}">${escapeHTML(shortenFilename(docName))}</span>
                <button class="btn-tab-close" data-filename="${escapeHTML(docName)}" title="Delete document">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            `;

            tab.addEventListener('click', () => {
                if (docName !== state.filename) {
                    selectDocument(docName);
                }
            });

            const btnClose = tab.querySelector('.btn-tab-close');
            btnClose.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteDocument(docName);
            });

            tabsList.appendChild(tab);
        });

        // Disable add button if limit reached
        if (state.documents.length >= 5) {
            btnTabAdd.style.opacity = '0.4';
            btnTabAdd.style.cursor = 'not-allowed';
            btnTabAdd.title = 'Limit of 5 files reached';
            btnOpenUpload.style.opacity = '0.4';
            btnOpenUpload.disabled = true;
            btnOpenUpload.title = 'Limit of 5 files reached';
        } else {
            btnTabAdd.style.opacity = '1';
            btnTabAdd.style.cursor = 'pointer';
            btnTabAdd.title = 'Upload new document';
            btnOpenUpload.style.opacity = '1';
            btnOpenUpload.disabled = false;
            btnOpenUpload.title = 'Upload document';
        }
    }

    function renderContextBanner() {
        if (!state.documents || state.documents.length === 0) {
            contextBanner.style.display = 'none';
            return;
        }
        contextBanner.style.display = 'flex';
        contextDocPills.innerHTML = '';
        state.documents.forEach(docName => {
            const pill = document.createElement('span');
            pill.className = 'context-doc-pill';
            pill.title = docName;
            pill.innerHTML = `<i class="fa-solid fa-circle-check"></i>${escapeHTML(shortenFilename(docName))}`;
            contextDocPills.appendChild(pill);
        });
    }

    async function selectDocument(docName) {
        try {
            const res = await fetch('/api/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: docName })
            });
            const data = await res.json();
            if (data.status === 'success') {
                state.filename = data.active_filename;
                
                const docRes = await fetch('/api/document');
                const docData = await docRes.json();
                state.documentLines = docData.content.split('\n');
                state.metrics = docData.metrics;

                renderDocument(docData.content, true);
                updateTelemetryUI();
                renderTabs();
                renderContextBanner();
                showToast(`Switched context to ${docName}`, 'success');
            }
        } catch (err) {
            console.error(err);
            showToast('Failed to switch document context.', 'error');
        }
    }

    async function deleteDocument(docName) {
        if (!confirm(`Are you sure you want to delete "${docName}" from memory?`)) return;
        try {
            const res = await fetch('/api/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: docName })
            });
            const data = await res.json();
            if (data.status === 'success') {
                state.documents = data.documents;
                state.filename = data.active_filename;

                if (state.filename) {
                    const docRes = await fetch('/api/document');
                    const docData = await docRes.json();
                    state.documentLines = docData.content.split('\n');
                    state.metrics = docData.metrics;
                    renderDocument(docData.content, true);
                    updateTelemetryUI();
                    enableChatSystem();
                } else {
                    state.metrics = { chars: 0, words: 0, lines: 0, chunks: 0 };
                    state.documentLines = [];
                    renderEmptyViewerPlaceholder();
                    updateTelemetryUI();
                    disableChatSystem();
                    openIngestionModal();
                }
                renderTabs();
                renderContextBanner();
                showToast(`Deleted ${docName}`, 'success');
            }
        } catch (err) {
            console.error(err);
            showToast('Failed to delete document.', 'error');
        }
    }

    function renderEmptyViewerPlaceholder() {
        documentViewport.innerHTML = `
            <div class="viewport-placeholder">
                <div class="placeholder-orbit">
                    <div class="orbit-ring"></div>
                    <i class="fa-solid fa-file-arrow-up upload-pulse-icon"></i>
                </div>
                <h3>Drop a document to begin</h3>
                <p>Upload a PDF, DOCX, Markdown, or text file to start chatting with your content.</p>
                <button class="btn-primary btn-sm" id="btnPlaceholderUpload">
                    <i class="fa-solid fa-cloud-arrow-up"></i> Upload Document
                </button>
            </div>
        `;
        document.getElementById('btnPlaceholderUpload').addEventListener('click', openIngestionModal);
    }

    btnOpenUpload.addEventListener('click', openIngestionModal);
    btnPlaceholderUpload.addEventListener('click', openIngestionModal);
    btnTabAdd.addEventListener('click', openIngestionModal);
    btnExportChat.addEventListener('click', exportChatHistory);
    btnCloseModal.addEventListener('click', closeIngestionModal);

    ['dragenter', 'dragover'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', e => {
        if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files[0]);
    });

    btnSelectFile.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) handleFileUpload(fileInput.files[0]);
    });

    function setProgress(pct, status, title) {
        uploadProgressBar.style.width = `${pct}%`;
        uploadProgressPercent.textContent = `${Math.round(pct)}%`;
        if (status) uploadProgressStatus.textContent = status;
        if (title) loaderTitle.textContent = title;
    }

    async function handleFileUpload(file) {
        const allowed = ['.txt', '.pdf', '.docx', '.md', '.markdown'];
        if (!allowed.some(ext => file.name.toLowerCase().endsWith(ext))) {
            showToast('Supported formats: .pdf, .docx, .md, .txt', 'warn');
            return;
        }

        dropzone.hidden = true;
        uploadProgressContainer.hidden = false;
        startLoaderParticles();

        const loaderLog = document.getElementById('loaderLog');
        loaderLog.innerHTML = '';

        function addLog(text, cls = '') {
            const line = document.createElement('div');
            line.className = `log-line${cls ? ' ' + cls : ''}`;
            line.textContent = `> ${text}`;
            loaderLog.appendChild(line);
            loaderLog.scrollTop = loaderLog.scrollHeight;
        }

        const delay = ms => new Promise(r => setTimeout(r, ms));

        setProgress(5, 'Establishing connection...', 'INITIALIZING CORTEX');
        addLog('cortex.init()');
        await delay(200);

        setProgress(15, `Reading ${file.name}...`, 'READING DOCUMENT');
        addLog(`open("${file.name}")`);
        await delay(250);

        addLog('streaming bytes to local engine...');
        setProgress(30, 'Uploading to local engine...', 'UPLOADING');
        await delay(200);

        const formData = new FormData();
        formData.append('file', file);

        try {
            setProgress(45, 'Processing file...', 'PROCESSING');
            addLog('extract_text()');

            const response = await fetch('/api/upload', { method: 'POST', body: formData });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Upload failed');
            }

            const data = await response.json();

            setProgress(65, 'Parsing document structure...', 'PARSING');
            addLog(`parsed ${data.metrics?.lines || '?'} lines`);
            await delay(300);

            setProgress(80, 'Generating semantic embeddings...', 'EMBEDDING');
            addLog('ollama.embeddings() — batch generation');
            await delay(350);

            setProgress(95, 'Integrating into cortex memory...', 'INTEGRATING');
            addLog('load_context()');
            await delay(250);

            setProgress(100, 'Ingestion complete!', 'COMPLETE');
            addLog('cortex.ready = true', 'success');
            addLog('status: ACTIVE', 'accent');
            await delay(500);

            state.filename = data.filename;
            state.metrics = data.metrics;
            state.documents = data.documents;

            const docRes = await fetch('/api/document');
            const docData = await docRes.json();
            state.documentLines = docData.content.split('\n');

            stopLoaderParticles();
            dropzone.hidden = false;
            uploadProgressContainer.hidden = true;

            closeIngestionModal();
            renderTabs();
                renderContextBanner();
            await renderDocumentWithScan(docData.content);
            updateTelemetryUI();
            enableChatSystem();
            showToast(`Document loaded: ${file.name}`, 'success');

        } catch (err) {
            console.error(err);
            showToast(err.message || 'Ingestion failed', 'error');
            stopLoaderParticles();
            dropzone.hidden = false;
            uploadProgressContainer.hidden = true;
        }
    }

    async function renderDocumentWithScan(content) {
        docScanIndicator.hidden = false;
        documentViewport.classList.add('scanning');
        renderDocument(content, false);
        await new Promise(r => setTimeout(r, Math.min(content.split('\n').length * 8, 2000)));
        docScanIndicator.hidden = true;
        documentViewport.classList.remove('scanning');
    }

    function updateTelemetryUI() {
        valLines.textContent = state.metrics.lines.toLocaleString();
        valWords.textContent = state.metrics.words.toLocaleString();
        valDocName.textContent = state.filename || '—';
        valDocStatus.textContent = state.filename ? 'Loaded' : 'Awaiting upload';
        valDocStatus.className = state.filename ? 'metric-delta delta-pos' : 'metric-delta';
    }

    function renderDocument(content, instant = false) {
        activeDocName.textContent = (state.filename || 'NO DOCUMENT').toUpperCase();
        documentViewport.innerHTML = '';

        const lines = content.split('\n');
        lines.forEach((lineText, idx) => {
            const row = document.createElement('div');
            row.className = 'code-line-row';
            row.setAttribute('data-line', idx + 1);

            if (!instant) {
                row.style.animationDelay = `${Math.min(idx * 12, 800)}ms`;
                row.classList.add('revealed');
            } else {
                row.style.opacity = '1';
                row.style.transform = 'none';
            }

            const formatted = lineText === '' ? ' ' : lineText;
            row.innerHTML = `
                <span class="code-line-num">${idx + 1}</span>
                <span class="code-line-content">${escapeHTML(formatted)}</span>
            `;
            documentViewport.appendChild(row);
        });

        docSearch.value = '';
    }

    function escapeHTML(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    btnScrollToTop.addEventListener('click', () => {
        documentViewport.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // ==========================================================================
    // LINE HIGHLIGHTING
    // ==========================================================================
    function highlightDocumentLines(chunks) {
        documentViewport.querySelectorAll('.code-line-row.active-highlight')
            .forEach(r => r.classList.remove('active-highlight'));
        if (!chunks?.length) return;

        let firstLine = null;
        chunks.forEach(chunk => {
            if (firstLine === null || chunk.start_line < firstLine) firstLine = chunk.start_line;
            for (let l = chunk.start_line; l <= chunk.end_line; l++) {
                const row = documentViewport.querySelector(`.code-line-row[data-line="${l}"]`);
                if (row) row.classList.add('active-highlight');
            }
        });

        if (firstLine !== null) {
            const target = documentViewport.querySelector(`.code-line-row[data-line="${firstLine}"]`);
            if (target) {
                documentViewport.scrollTo({
                    top: target.offsetTop - documentViewport.clientHeight / 3,
                    behavior: 'smooth'
                });
            }
        }
    }

    async function selectAndHighlightDocumentLines(chunks) {
        if (!chunks?.length) return;
        const firstChunk = chunks[0];
        const targetFilename = firstChunk.filename;
        
        if (targetFilename && targetFilename !== state.filename) {
            showToast(`Switching context to ${targetFilename}...`, 'info');
            try {
                const res = await fetch('/api/select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: targetFilename })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    state.filename = targetFilename;
                    
                    const docRes = await fetch('/api/document');
                    const docData = await docRes.json();
                    state.documentLines = docData.content.split('\n');
                    state.metrics = docData.metrics;
                    
                    renderDocument(docData.content, true);
                    updateTelemetryUI();
                    renderTabs();
                renderContextBanner();
                }
            } catch (err) {
                console.error(err);
                showToast('Failed to switch document context.', 'error');
                return;
            }
        }
        
        setTimeout(() => {
            highlightDocumentLines(chunks);
            showToast(`Jumped to lines L${firstChunk.start_line}–${firstChunk.end_line}`, 'info');
        }, 50);
    }

    docSearch.addEventListener('input', () => {
        const query = docSearch.value.trim().toLowerCase();
        documentViewport.querySelectorAll('.code-line-row').forEach(row => {
            row.classList.remove('search-matched');
            if (query.length >= 2) {
                const content = row.querySelector('.code-line-content').textContent.toLowerCase();
                if (content.includes(query)) row.classList.add('search-matched');
            }
        });
        if (query.length >= 2) {
            const hit = documentViewport.querySelector('.code-line-row.search-matched');
            if (hit) hit.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }
    });

    // ==========================================================================
    // CHAT SYSTEM
    // ==========================================================================
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = (chatInput.scrollHeight - 8) + 'px';
    });

    chatForm.addEventListener('submit', e => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text || state.isThinking) return;
        submitChatQuery(text);
    });

    chatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.requestSubmit();
        }
    });

    async function submitChatQuery(messageText) {
        state.isThinking = true;
        state.isStreaming = false;
        setChatInputState(true);
        setAgentStatus('thinking', 'Thinking...');
        setSessionState('THINKING', 'Processing query...', 'delta-active');

        chatLog.querySelector('.chat-placeholder')?.remove();
        appendMessage('user', messageText);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        const aiBubbleId = 'ai-' + Date.now();
        const aiBubble = appendMessage('assistant', '', aiBubbleId);
        const textElement = aiBubble.querySelector('.bubble-content-text');
        aiBubble.classList.add('streaming');
        aiBubble.querySelector('.bubble-avatar').classList.add('thinking-pulse');

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: messageText, history: state.chatHistory })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Inference failed');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let rawBuffer = '';
            let generatedAnswer = '';
            let retrievedChunks = [];
            let firstToken = true;

            state.isStreaming = true;
            setAgentStatus('streaming', 'Streaming...');
            setSessionState('STREAMING', 'Receiving response...', 'delta-active');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                rawBuffer += decoder.decode(value, { stream: true });
                const lines = rawBuffer.split('\n\n');
                rawBuffer = lines.pop();

                for (const line of lines) {
                    if (!line.trim().startsWith('data: ')) continue;
                    const dataStr = line.replace(/^data:\s*/, '').trim();
                    if (dataStr === '[DONE]') break;

                    try {
                        const data = JSON.parse(dataStr);
                        if (data.type === 'metadata') {
                            retrievedChunks = data.chunks;
                            highlightDocumentLines(retrievedChunks);
                            addCitationsToBubble(aiBubble, retrievedChunks);
                        } else if (data.type === 'token') {
                            if (firstToken) {
                                aiBubble.querySelector('.bubble-avatar').classList.remove('thinking-pulse');
                                firstToken = false;
                            }
                            generatedAnswer += data.text;
                            renderAIResponse(textElement, generatedAnswer, true);
                            chatLog.scrollTop = chatLog.scrollHeight;
                        } else if (data.type === 'error') {
                            throw new Error(data.detail);
                        }
                    } catch (_) { /* partial SSE chunk */ }
                }
            }

            renderAIResponse(textElement, generatedAnswer, false);
            aiBubble.classList.remove('streaming');

            state.chatHistory.push({ role: 'user', content: messageText });
            state.chatHistory.push({ role: 'assistant', content: generatedAnswer });

            attachSuggestions(aiBubble, generatedAnswer);
            addCopyButton(aiBubble, generatedAnswer);

            setAgentStatus('', 'Ready');
            setSessionState('ACTIVE', `${state.chatHistory.length / 2 | 0} exchanges`, 'delta-pos');

        } catch (err) {
            console.error(err);
            textElement.innerHTML = `<span style="color:var(--accent-error)"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHTML(err.message)}</span>`;
            aiBubble.classList.remove('streaming');
            showToast('Inference failed — check Ollama is running.', 'error');
            setAgentStatus('', 'Error');
            setSessionState('ERROR', 'Check Ollama server', 'delta-neg');
        } finally {
            state.isThinking = false;
            state.isStreaming = false;
            setChatInputState(false);
            aiBubble.querySelector('.bubble-avatar')?.classList.remove('thinking-pulse');
            chatLog.scrollTop = chatLog.scrollHeight;
        }
    }

    function setChatInputState(loading) {
        chatInput.disabled = loading;
        btnSubmitChat.disabled = loading;
        btnSubmitChat.innerHTML = loading
            ? '<i class="fa-solid fa-spinner spinner-icon"></i>'
            : '<i class="fa-solid fa-paper-plane"></i>';
        if (!loading) chatInput.focus();
    }

    function appendMessage(role, text, id = null) {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${role}`;
        if (id) bubble.id = id;

        const avatarIcon = role === 'user' ? 'fa-user' : 'fa-brain';
        const roleLabel = role === 'user' ? 'You' : 'Cortex';
        const time = formatTime();

        if (role === 'user') {
            bubble.innerHTML = `
                <div class="bubble-avatar"><i class="fa-solid ${avatarIcon}"></i></div>
                <div class="bubble-content-wrapper">
                    <div class="bubble-meta">
                        <span class="bubble-role">${roleLabel}</span>
                        <span class="bubble-time">${time}</span>
                    </div>
                    <div class="bubble-content">${escapeHTML(text)}</div>
                </div>
            `;
        } else {
            bubble.innerHTML = `
                <div class="bubble-avatar"><i class="fa-solid ${avatarIcon}"></i></div>
                <div class="bubble-content-wrapper">
                    <div class="bubble-meta">
                        <span class="bubble-role">${roleLabel}</span>
                        <span class="bubble-time">${time}</span>
                    </div>
                    <div class="bubble-content">
                        <div class="bubble-content-text">
                            <div class="typing-indicator">
                                <div class="typing-dots"><span></span><span></span><span></span></div>
                                <span>Cortex is thinking...</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        chatLog.appendChild(bubble);
        chatLog.scrollTop = chatLog.scrollHeight;
        return bubble;
    }

    function renderAIResponse(element, markdownText, streaming = false) {
        let cleaned = markdownText;
        cleaned = cleaned.replace(/💡\s*Suggestion:\s*(.+)$/gm, '');
        cleaned = cleaned.replace(/Suggested Follow-up Questions:?\s*$/i, '');
        cleaned = cleaned.replace(/💡\s*Suggestions:?\s*$/i, '');
        
        // Sometimes the model outputs a header for the questions but no other text.
        cleaned = cleaned.replace(/\*\*Follow-Up Questions:?\*\*\s*/gi, '');
        cleaned = cleaned.replace(/Follow-Up Questions:?\s*/gi, '');

        cleaned = cleaned.trim();
        
        // If the model refused or only outputted suggestions, avoid a hollow empty message
        if (cleaned.length === 0) {
            cleaned = "I cannot find that information in the documents.";
        }

        let html = escapeHTML(cleaned);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
        html = html.replace(/^&gt;\s+(.*)$/gm, '<blockquote>$1</blockquote>');
        html = html.replace(/`(.*?)`/g, '<code class="inline-code">$1</code>');
        html = html.replace(/\n/g, '<br>');
        html = html.replace(/(<br>){2,}/g, '<br><br>');

        if (streaming) html += '<span class="streaming-cursor"></span>';
        element.innerHTML = html;
    }

    function addCopyButton(aiBubble, text) {
        const meta = aiBubble.querySelector('.bubble-meta');
        if (!meta || meta.querySelector('.bubble-action-btn')) return;

        const btn = document.createElement('button');
        btn.className = 'bubble-action-btn';
        btn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
        btn.addEventListener('click', () => {
            navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard', 'success'));
        });
        meta.appendChild(btn);
    }

    function addCitationsToBubble(aiBubble, chunks) {
        if (!chunks?.length) return;
        const wrapper = aiBubble.querySelector('.bubble-content-wrapper');
        let bar = wrapper.querySelector('.citation-meta');
        if (!bar) {
            bar = document.createElement('div');
            bar.className = 'citation-meta';
            bar.innerHTML = '<span><i class="fa-solid fa-link"></i> Sources:</span>';
            wrapper.appendChild(bar);
        }

        chunks.forEach(chunk => {
            const safeName = chunk.filename ? chunk.filename.replace(/[^a-zA-Z0-9]/g, '_') : '';
            const pillId = `pill-${safeName}-${chunk.start_line}-${chunk.end_line}`;
            if (bar.querySelector(`#${pillId}`)) return;
            const pill = document.createElement('span');
            pill.id = pillId;
            pill.className = 'citation-badge';
            
            const shortName = shortenFilename(chunk.filename);
            pill.textContent = `${shortName}: L${chunk.start_line}–${chunk.end_line}`;
            
            pill.addEventListener('click', () => {
                selectAndHighlightDocumentLines([chunk]);
            });
            bar.appendChild(pill);
        });
    }

    function attachSuggestions(aiBubble, fullText) {
        const wrapper = aiBubble.querySelector('.bubble-content-wrapper');
        const suggestions = [];

        fullText.split('\n').forEach(line => {
            if (line.includes('💡 Suggestion:')) {
                let text = line.replace(/.*💡\s*Suggestion:\s*/, '').trim();
                text = text.replace(/\*\*/g, '').replace(/\*/g, '');
                if (text) suggestions.push(text);
            }
        });

        if (!suggestions.length) return;

        const box = document.createElement('div');
        box.className = 'suggestions-box';
        box.innerHTML = '<div class="suggestions-label">Suggested follow-ups</div>';

        suggestions.forEach(q => {
            const btn = document.createElement('button');
            btn.className = 'suggestion-btn';
            btn.innerHTML = `<i class="fa-regular fa-lightbulb"></i> ${escapeHTML(q)}`;
            btn.addEventListener('click', () => {
                if (state.isThinking) return;
                chatInput.value = q;
                chatForm.requestSubmit();
            });
            box.appendChild(btn);
        });

        wrapper.appendChild(box);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    // ==========================================================================
    // EXPORT & PURGE
    // ==========================================================================
    function exportChatHistory() {
        if (!state.chatHistory.length) {
            showToast('No chat history to export.', 'warn');
            return;
        }
        let md = `# Local-Cortex Chat Export\n`;
        md += `*Exported on: ${new Date().toLocaleString()}*\n\n`;
        md += `### Analyzed Documents:\n`;
        state.documents.forEach(doc => {
            md += `- ${doc}\n`;
        });
        md += `\n---\n\n`;
        
        state.chatHistory.forEach((msg, idx) => {
            const roleName = msg.role === 'user' ? '👤 User' : '🤖 Cortex Agent';
            md += `### ${roleName}\n`;
            md += `${msg.content}\n\n`;
            if (idx < state.chatHistory.length - 1) {
                md += `---\n\n`;
            }
        });
        
        const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
        link.href = url;
        link.setAttribute('download', `cortex_chat_export_${timestamp}.md`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        showToast('Chat history exported successfully!', 'success');
    }

    btnPurgeMemory.addEventListener('click', async () => {
        if (!confirm('Clear all documents and chat history?')) return;
        try {
            await fetch('/api/clear', { method: 'POST' });

            state.filename = null;
            state.documents = [];
            state.metrics = { chars: 0, words: 0, lines: 0, chunks: 0 };
            state.documentLines = [];
            state.chatHistory = [];

            renderEmptyViewerPlaceholder();
            renderTabs();
                renderContextBanner();

            chatLog.innerHTML = `
                <div class="chat-placeholder">
                    <div class="agent-avatar-large">
                        <i class="fa-solid fa-brain"></i>
                        <div class="avatar-glow"></div>
                    </div>
                    <h3>Cortex Agent Ready</h3>
                    <p>Upload a document, then ask questions about its content. Answers are grounded in your file with line citations.</p>
                    <div class="placeholder-hints">
                        <span><i class="fa-solid fa-quote-left"></i> Summarize key points</span>
                        <span><i class="fa-solid fa-magnifying-glass"></i> Find specific info</span>
                        <span><i class="fa-solid fa-list"></i> Extract action items</span>
                    </div>
                </div>
            `;

            activeDocName.textContent = 'NO DOCUMENT LOADED';
            valLines.textContent = '0';
            valWords.textContent = '0';
            valDocName.textContent = '—';
            valDocStatus.textContent = 'Awaiting upload';
            valDocStatus.className = 'metric-delta';
            setSessionState('IDLE', 'Ready to chat', 'delta-pos');
            setAgentStatus('', 'Idle');

            openIngestionModal();
            showToast('Session cleared.', 'success');
        } catch (err) {
            showToast('Failed to clear session.', 'error');
        }
    });
});
