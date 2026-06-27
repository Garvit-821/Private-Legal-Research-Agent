/**
 * Local-Cortex Spatial Whiteboard & Mind Mapping Engine
 */
window.CortexWhiteboard = (function () {
    let container = null;
    let world = null;
    let svgLayer = null;
    let chatInput = null;

    let scale = 1;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let startX = 0;
    let startY = 0;

    const nodes = new Map();
    const connections = []; // { id, sourceId, targetId }

    let draggedNode = null;
    let dragOffsetX = 0;
    let dragOffsetY = 0;

    function init() {
        container = document.getElementById('whiteboardViewport');
        world = document.getElementById('whiteboardWorld');
        svgLayer = document.getElementById('whiteboardSvg');
        chatInput = document.getElementById('chatInput');

        if (!container || !world || !svgLayer) return;

        setupEvents();
        updateTransform();
    }

    function setupEvents() {
        // Pan canvas
        container.addEventListener('mousedown', (e) => {
            if (e.target === container || e.target === world || e.target === svgLayer) {
                isPanning = true;
                startX = e.clientX - panX;
                startY = e.clientY - panY;
                container.style.cursor = 'grabbing';
            }
        });

        window.addEventListener('mousemove', (e) => {
            if (isPanning) {
                panX = e.clientX - startX;
                panY = e.clientY - startY;
                updateTransform();
            } else if (draggedNode) {
                const worldPos = screenToWorld(e.clientX, e.clientY);
                draggedNode.x = worldPos.x - dragOffsetX;
                draggedNode.y = worldPos.y - dragOffsetY;
                positionNodeElement(draggedNode);
                renderConnections();
            }
        });

        window.addEventListener('mouseup', () => {
            if (isPanning) {
                isPanning = false;
                container.style.cursor = 'grab';
            }
            if (draggedNode) {
                draggedNode.element.classList.remove('dragging');
                draggedNode = null;
            }
        });

        // Zoom canvas
        container.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomFactor = 1.1;
            const mouseX = e.clientX;
            const mouseY = e.clientY;

            const worldBefore = screenToWorld(mouseX, mouseY);

            if (e.deltaY < 0) {
                scale = Math.min(scale * zoomFactor, 3.0);
            } else {
                scale = Math.max(scale / zoomFactor, 0.2);
            }

            const worldAfter = screenToWorld(mouseX, mouseY);

            panX += (worldAfter.x - worldBefore.x) * scale;
            panY += (worldAfter.y - worldBefore.y) * scale;

            updateTransform();
            updateZoomLabel();
        }, { passive: false });
    }

    function screenToWorld(sx, sy) {
        const rect = container.getBoundingClientRect();
        return {
            x: (sx - rect.left - panX) / scale,
            y: (sy - rect.top - panY) / scale
        };
    }

    function updateTransform() {
        if (!world) return;
        world.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
    }

    function updateZoomLabel() {
        const lbl = document.getElementById('wbZoomVal');
        if (lbl) lbl.textContent = `${Math.round(scale * 100)}%`;
    }

    function resetView() {
        scale = 1;
        panX = 100;
        panY = 100;
        updateTransform();
        updateZoomLabel();
    }

    function zoomIn() {
        scale = Math.min(scale * 1.2, 3.0);
        updateTransform();
        updateZoomLabel();
    }

    function zoomOut() {
        scale = Math.max(scale / 1.2, 0.2);
        updateTransform();
        updateZoomLabel();
    }

    let connectingSourceId = null;

    function addCustomNote() {
        const id = `note-${Date.now()}`;
        const note = addNode({
            id,
            type: 'note',
            title: 'Personal Note',
            subtitle: 'User Custom Note',
            content: 'Type your research thoughts or key synthesis here...',
            x: 200 + (nodes.size % 3) * 300,
            y: 200 + Math.floor(nodes.size / 3) * 200
        });
        if (note && note.element) {
            const textarea = note.element.querySelector('.wb-note-textarea');
            if (textarea) textarea.focus();
        }
        return note;
    }

    function addNode({ id, type = 'concept', title, subtitle = '', content = '', x, y, parentId = null }) {
        if (nodes.has(id)) {
            const existing = nodes.get(id);
            existing.title = title;
            existing.content = content;
            updateNodeElement(existing);
            return existing;
        }

        const autoX = x !== undefined ? x : 150 + (nodes.size % 4) * 320;
        const autoY = y !== undefined ? y : 150 + Math.floor(nodes.size / 4) * 220;

        const node = { id, type, title, subtitle, content, x: autoX, y: autoY, parentId, element: null };

        const el = document.createElement('div');
        el.className = `wb-node wb-node-${type}`;
        el.id = `node-${id}`;

        if (type === 'note') {
            el.innerHTML = `
                <div class="wb-node-header">
                    <div class="wb-node-type-badge"><i class="${getNodeIcon(type)}"></i> NOTE</div>
                    <div class="wb-node-actions">
                        <button class="wb-node-connect" title="Connect arrow to another node"><i class="fa-solid fa-arrow-right-long"></i></button>
                        <button class="wb-node-delete" title="Delete Note"><i class="fa-solid fa-trash-can"></i></button>
                    </div>
                </div>
                <input type="text" class="wb-node-title-input" value="${escapeHTML(title)}" placeholder="Note Title..." />
                <textarea class="wb-note-textarea" placeholder="Write custom notes...">${escapeHTML(content)}</textarea>
            `;

            const titleInput = el.querySelector('.wb-node-title-input');
            const textarea = el.querySelector('.wb-note-textarea');
            const delBtn = el.querySelector('.wb-node-delete');
            const connectBtn = el.querySelector('.wb-node-connect');

            titleInput.addEventListener('input', (e) => { node.title = e.target.value; });
            textarea.addEventListener('input', (e) => { node.content = e.target.value; });
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                el.remove();
                nodes.delete(id);
                // remove connections
                for (let i = connections.length - 1; i >= 0; i--) {
                    if (connections[i].sourceId === id || connections[i].targetId === id) {
                        connections.splice(i, 1);
                    }
                }
                renderConnections();
            });

            connectBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                handleConnectClick(node);
            });
        } else {
            el.innerHTML = `
                <div class="wb-node-header">
                    <div class="wb-node-type-badge"><i class="${getNodeIcon(type)}"></i> ${type.toUpperCase()}</div>
                    <div class="wb-node-actions">
                        <button class="wb-node-connect" title="Connect arrow to another node"><i class="fa-solid fa-arrow-right-long"></i></button>
                        <button class="wb-node-pin" title="Ask AI about this concept"><i class="fa-solid fa-sparkles"></i></button>
                    </div>
                </div>
                <div class="wb-node-title">${escapeHTML(title)}</div>
                ${subtitle ? `<div class="wb-node-subtitle">${escapeHTML(subtitle)}</div>` : ''}
                <div class="wb-node-content">${formatNodeContent(content)}</div>
            `;

            el.querySelector('.wb-node-pin')?.addEventListener('click', (e) => {
                e.stopPropagation();
                if (chatInput) {
                    chatInput.value = `Tell me more about "${title}" in context of the active documents.`;
                    chatInput.focus();
                }
            });

            el.querySelector('.wb-node-connect')?.addEventListener('click', (e) => {
                e.stopPropagation();
                handleConnectClick(node);
            });
        }

        // Node Click Target for active connecting
        el.addEventListener('click', (e) => {
            if (connectingSourceId && connectingSourceId !== node.id) {
                e.stopPropagation();
                connections.push({ id: `${connectingSourceId}-${node.id}`, sourceId: connectingSourceId, targetId: node.id });
                clearConnectingState();
                renderConnections();
            }
        });

        // Node Dragging Setup
        el.addEventListener('mousedown', (e) => {
            if (e.target.closest('.wb-node-pin') || e.target.closest('.wb-node-connect') || e.target.closest('.wb-node-delete') || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.closest('button')) return;
            e.stopPropagation();
            draggedNode = node;
            const worldPos = screenToWorld(e.clientX, e.clientY);
            dragOffsetX = worldPos.x - node.x;
            dragOffsetY = worldPos.y - node.y;
            el.classList.add('dragging');
        });

        world.appendChild(el);
        node.element = el;
        nodes.set(id, node);

        positionNodeElement(node);

        if (parentId && nodes.has(parentId)) {
            connections.push({ id: `${parentId}-${id}`, sourceId: parentId, targetId: id });
            renderConnections();
        }

        return node;
    }

    function handleConnectClick(node) {
        if (connectingSourceId === node.id) {
            clearConnectingState();
        } else if (connectingSourceId) {
            // connect connectingSourceId -> node.id
            connections.push({ id: `${connectingSourceId}-${node.id}`, sourceId: connectingSourceId, targetId: node.id });
            clearConnectingState();
            renderConnections();
        } else {
            connectingSourceId = node.id;
            node.element.classList.add('connecting-source');
            document.querySelectorAll('.wb-node').forEach(n => {
                if (n.id !== `node-${node.id}`) n.classList.add('connecting-target-candidate');
            });
        }
    }

    function clearConnectingState() {
        connectingSourceId = null;
        document.querySelectorAll('.wb-node').forEach(n => {
            n.classList.remove('connecting-source', 'connecting-target-candidate');
        });
    }

    function getNodeIcon(type) {
        switch (type) {
            case 'doc': return 'fa-solid fa-file-invoice';
            case 'ai': return 'fa-solid fa-brain';
            case 'chunk': return 'fa-solid fa-quote-left';
            case 'note': return 'fa-solid fa-sticky-note';
            default: return 'fa-solid fa-lightbulb';
        }
    }

    function formatNodeContent(content) {
        if (!content) return '';
        if (content.length > 280) {
            return escapeHTML(content.substring(0, 280)) + '...';
        }
        return escapeHTML(content);
    }

    function updateNodeElement(node) {
        if (!node.element) return;
        const titleEl = node.element.querySelector('.wb-node-title');
        const contentEl = node.element.querySelector('.wb-node-content');
        if (titleEl) titleEl.textContent = node.title;
        if (contentEl) contentEl.innerHTML = formatNodeContent(node.content);
    }

    function positionNodeElement(node) {
        if (!node.element) return;
        node.element.style.transform = `translate(${node.x}px, ${node.y}px)`;
    }

    function renderConnections() {
        if (!svgLayer) return;
        let svgHtml = `
            <defs>
                <marker id="wb-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#00f5ff" />
                </marker>
            </defs>
        `;

        connections.forEach(conn => {
            const src = nodes.get(conn.sourceId);
            const tgt = nodes.get(conn.targetId);
            if (!src || !tgt || !src.element || !tgt.element) return;

            const srcRect = { width: src.element.offsetWidth || 280, height: src.element.offsetHeight || 140 };
            const tgtRect = { width: tgt.element.offsetWidth || 280, height: tgt.element.offsetHeight || 140 };

            const x1 = src.x + srcRect.width / 2;
            const y1 = src.y + srcRect.height / 2;
            const x2 = tgt.x + tgtRect.width / 2;
            const y2 = tgt.y + tgtRect.height / 2;

            const dx = (x2 - x1) * 0.5;
            const path = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;

            svgHtml += `<path d="${path}" class="wb-connector-line" marker-end="url(#wb-arrow)" />`;
            svgHtml += `<circle cx="${x1}" cy="${y1}" r="4" class="wb-connector-dot" />`;
        });

        svgLayer.innerHTML = svgHtml;
    }

    function autoLayout() {
        let docIndex = 0;
        const docNodes = Array.from(nodes.values()).filter(n => n.type === 'doc');
        
        docNodes.forEach((docNode, idx) => {
            docNode.x = 100;
            docNode.y = 150 + idx * 320;
            positionNodeElement(docNode);

            const children = Array.from(nodes.values()).filter(n => n.parentId === docNode.id);
            children.forEach((child, cIdx) => {
                child.x = 450 + (cIdx % 3) * 310;
                child.y = docNode.y + Math.floor(cIdx / 3) * 200 - 50;
                positionNodeElement(child);
            });
        });

        renderConnections();
    }

    function clear() {
        nodes.forEach(n => n.element?.remove());
        nodes.clear();
        connections.length = 0;
        if (svgLayer) svgLayer.innerHTML = '';
    }

    function escapeHTML(str) {
        return (str || '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m]));
    }

    return {
        init,
        resetView,
        zoomIn,
        zoomOut,
        addNode,
        addCustomNote,
        autoLayout,
        clear
    };
})();
