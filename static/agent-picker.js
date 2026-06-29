/**
 * Agent Picker UI for Local-Cortex
 */
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('agentPickerModal');
    const btnOpen = document.getElementById('btnOpenAgentPicker');
    const btnClose = document.getElementById('btnCloseAgentPicker');
    const listPanel = document.getElementById('agentListPanel');
    const specsText = document.getElementById('agentSpecsText');
    const activeLabel = document.getElementById('activeAgentLabel');
    const embedLabel = document.getElementById('embedModelLabel');
    const tabs = document.querySelectorAll('.agent-tab');

    if (!modal || !btnOpen) return;

    const pickerState = {
        activeTab: 'recommended',
        agents: { recommended: [], installed: [], library: [] },
        current: null,
        system: null,
        isPulling: false,
    };

    btnOpen.addEventListener('click', () => {
        if (window.CortexApp?.state?.isStreaming) {
            window.CortexApp.showToast('Wait for the current response to finish before switching agents.', 'warn');
            return;
        }
        openModal();
    });
    btnClose.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            pickerState.activeTab = tab.dataset.tab;
            renderList();
        });
    });

    async function openModal() {
        modal.classList.remove('hidden');
        await refreshAgents();
    }

    function closeModal() {
        modal.classList.add('hidden');
    }

    async function refreshAgents() {
        try {
            const data = await CortexContracts.apiJson('/api/agents');
            pickerState.agents = {
                recommended: data.recommended || [],
                installed: data.installed || [],
                library: data.library || [],
            };
            pickerState.current = data.current;
            pickerState.system = data.system;
            updateHeader(data.current);
            renderSpecs(data.system);
            renderList();
        } catch (err) {
            specsText.textContent = 'Failed to load agents. Is Ollama running?';
            listPanel.innerHTML = `<p class="agent-empty">${escapeHTML(err.message)}</p>`;
        }
    }

    function updateHeader(current) {
        if (!current) return;
        const name = current.profile?.display_name || current.chat_agent_id || 'qwen2.5:3b';
        activeLabel.textContent = name;
        embedLabel.textContent = current.embed_agent_id || 'nomic-embed-text';
        if (window.CortexApp?.state) {
            window.CortexApp.state.selectedChatModel = current.chat_agent_id;
            window.CortexApp.state.historyCap = current.history_cap || 10;
        }
    }

    function renderSpecs(system) {
        if (!system) {
            specsText.innerHTML = '<span class="spec-chip offline"><i class="fa-solid fa-triangle-exclamation"></i> Specifications unavailable</span>';
            return;
        }
        const vram = system.vram_gb != null ? `${system.vram_gb} GB VRAM` : 'CPU Only';
        const statusClass = system.ollama_reachable ? 'online' : 'offline';
        const statusText = system.ollama_reachable ? 'Ollama Online' : 'Ollama Offline';
        specsText.innerHTML = `
            <span class="spec-chip"><i class="fa-solid fa-memory"></i> ${system.ram_gb} GB RAM</span>
            <span class="spec-chip"><i class="fa-solid fa-microchip"></i> ${vram}</span>
            <span class="spec-chip status-${statusClass}"><span class="spec-dot ${statusClass}"></span> ${statusText}</span>
        `;
    }

    function renderList() {
        const items = pickerState.agents[pickerState.activeTab] || [];
        if (!items.length) {
            listPanel.innerHTML = '<p class="agent-empty"><i class="fa-solid fa-box-open"></i><br>No agents available in this category.</p>';
            return;
        }

        listPanel.innerHTML = '';
        items.forEach(agent => {
            const card = document.createElement('div');
            const isSelected = pickerState.current?.chat_agent_id === agent.id;
            card.className = `agent-card compatibility-${agent.compatibility}${isSelected ? ' selected' : ''}`;

            const disabled = agent.compatibility === 'incompatible' || pickerState.isPulling;
            let actionLabel = agent.installed ? 'Select' : '<i class="fa-solid fa-download"></i> Pull & Select';
            if (isSelected) {
                actionLabel = '<i class="fa-solid fa-check"></i> Active';
            }

            card.innerHTML = `
                <div class="agent-card-main">
                    <div class="agent-card-title">
                        <strong>${escapeHTML(agent.display_name)}</strong>
                        ${agent.default ? '<span class="agent-badge default"><i class="fa-solid fa-star"></i> Default</span>' : ''}
                        <span class="agent-badge tier">${escapeHTML(agent.tier)}</span>
                        <span class="agent-badge compat compat-${agent.compatibility}">${escapeHTML(agent.compatibility)}</span>
                    </div>
                    <p class="agent-card-desc">${escapeHTML(agent.description || '')}</p>
                    <div class="agent-card-meta">
                        <span><i class="fa-solid fa-memory"></i> ${agent.min_ram_gb} GB RAM</span>
                        <span><i class="fa-solid fa-microchip"></i> ${agent.min_vram_gb != null ? agent.min_vram_gb + ' GB VRAM' : 'CPU OK'}</span>
                        <span><i class="fa-solid fa-database"></i> Cap: ${agent.max_history_messages}</span>
                        <span class="meta-status ${agent.installed ? 'installed' : ''}"><i class="fa-solid ${agent.installed ? 'fa-circle-check' : 'fa-circle-arrow-down'}"></i> ${agent.installed ? 'Installed' : 'Not installed'}</span>
                    </div>
                </div>
                <button class="btn-primary btn-sm agent-select-btn${isSelected ? ' btn-active-model' : ''}" ${disabled ? 'disabled' : ''}>
                    ${actionLabel}
                </button>
            `;

            const btn = card.querySelector('.agent-select-btn');
            btn.addEventListener('click', () => selectAgent(agent));
            listPanel.appendChild(card);
        });
    }

    async function selectAgent(agent) {
        if (agent.compatibility === 'incompatible') return;
        try {
            const result = await CortexContracts.apiJson('/api/agents/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ schema_version: '1.0', agent_id: agent.id }),
            });

            if (result.status === 'pull_required') {
                await pullAndSelect(agent);
                return;
            }

            window.CortexApp?.showToast(`Agent switched to ${agent.display_name}`, 'success');
            await refreshAgents();
            closeModal();
        } catch (err) {
            window.CortexApp?.showToast(err.message || 'Failed to select agent', 'error');
        }
    }

    async function pullAndSelect(agent) {
        pickerState.isPulling = true;
        renderList();
        window.CortexApp?.showToast(`Pulling ${agent.display_name}...`, 'info');

        const response = await fetch('/api/agents/pull', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ schema_version: '1.0', agent_id: agent.id }),
        });

        if (!response.ok) {
            pickerState.isPulling = false;
            throw new Error('Pull request failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop();
            for (const part of parts) {
                if (!part.startsWith('data: ')) continue;
                const evt = CortexContracts.parseSsePayload(part.replace(/^data:\s*/, ''));
                if (evt.type === 'agent.pull.progress') {
                    specsText.textContent = `Downloading ${agent.display_name}: ${evt.data?.progress || 0}%`;
                }
                if (evt.type === 'agent.pull.error') {
                    throw new Error(evt.error?.message || 'Pull failed');
                }
            }
        }

        pickerState.isPulling = false;
        window.CortexApp?.showToast(`${agent.display_name} is ready`, 'success');
        await refreshAgents();
        closeModal();
    }

    async function loadCurrentAgent() {
        try {
            const data = await CortexContracts.apiJson('/api/agents/current');
            updateHeader(data);
        } catch (_) {
            activeLabel.textContent = 'qwen2.5:3b';
        }
    }

    function escapeHTML(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    loadCurrentAgent();

    window.CortexAgentPicker = {
        refresh: refreshAgents,
        loadCurrentAgent,
    };
});
