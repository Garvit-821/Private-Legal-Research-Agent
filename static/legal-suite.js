/**
 * Legal Intelligence Suite Controller for Legal Cortex
 */
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('legalSuiteModal');
    const btnOpen = document.getElementById('btnOpenLegalSuite');
    const btnClose = document.getElementById('btnCloseLegalSuite');
    const tabs = document.querySelectorAll('.legal-tab');
    const panels = document.querySelectorAll('.suite-panel');

    if (!modal || !btnOpen) return;

    // Open & Close
    btnOpen.addEventListener('click', () => modal.classList.remove('hidden'));
    btnClose.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.add('hidden');
    });

    // Tab Switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));

            tab.classList.add('active');
            const targetId = 'panel' + tab.dataset.suiteTab.charAt(0).toUpperCase() + tab.dataset.suiteTab.slice(1);
            const targetPanel = document.getElementById(targetId);
            if (targetPanel) targetPanel.classList.add('active');
        });
    });

    // ----------------------------------------------------------------------
    // 1. DRAFTING ENGINE
    // ----------------------------------------------------------------------
    const selectTemplate = document.getElementById('selectTemplate');
    const templateFactsForm = document.getElementById('templateFactsForm');
    const btnGenerateDraft = document.getElementById('btnGenerateDraft');
    const draftOutputContent = document.getElementById('draftOutputContent');
    const btnCopyDraft = document.getElementById('btnCopyDraft');

    const templateSchemas = {
        bail_application: [
            { id: 'applicant_name', label: 'Applicant / Accused Name', type: 'text', placeholder: 'e.g. Ramesh Kumar' },
            { id: 'court_name', label: 'Court / Forum Name', type: 'text', placeholder: 'e.g. In the Court of Sessions Judge, New Delhi' },
            { id: 'fir_details', label: 'FIR No. & Police Station', type: 'text', placeholder: 'e.g. FIR No. 123/2024, PS Connaught Place' },
            { id: 'sections', label: 'Offence Sections', type: 'text', placeholder: 'e.g. Sec 420, 468, 471 IPC' },
            { id: 'grounds', label: 'Key Grounds for Bail', type: 'textarea', placeholder: 'e.g. False implication, willing to join investigation, clean antecedents...' }
        ],
        legal_notice: [
            { id: 'sender_name', label: 'Sender (Client) Name', type: 'text', placeholder: 'e.g. Apex Tech Solutions Ltd.' },
            { id: 'recipient_details', label: 'Recipient Name & Address', type: 'textarea', placeholder: 'e.g. M/s Zenith Traders, 45 Commercial Complex, Mumbai' },
            { id: 'dispute_summary', label: 'Cause of Action / Dispute Summary', type: 'textarea', placeholder: 'e.g. Non-payment of unpaid invoice #INV-902 amounting to Rs 15,00,000...' },
            { id: 'relief_demanded', label: 'Relief Demanded', type: 'textarea', placeholder: 'e.g. Immediate payment of Rs 15,00,000 along with 18% interest p.a...' },
            { id: 'notice_period', label: 'Demand Deadline (Days)', type: 'text', placeholder: '15' }
        ],
        written_statement: [
            { id: 'defendant_name', label: 'Defendant Name', type: 'text', placeholder: 'e.g. Suresh Verma' },
            { id: 'plaintiff_name', label: 'Plaintiff Name & Suit No.', type: 'text', placeholder: 'e.g. Vikas Sharma (Suit No. CS 405/2023)' },
            { id: 'court_name', label: 'Court Name', type: 'text', placeholder: 'e.g. Civil Judge Senior Division, Saket Courts' },
            { id: 'prelim_objections', label: 'Preliminary Objections', type: 'textarea', placeholder: 'e.g. Suit barred by limitation, lacks cause of action...' },
            { id: 'para_reply', label: 'Factual Defence / Reply', type: 'textarea', placeholder: 'e.g. Plaintiff has concealed material facts; contract was already performed...' }
        ],
        employment_contract: [
            { id: 'employer_name', label: 'Employer Company Name', type: 'text', placeholder: 'e.g. Nexus Innovations Pvt. Ltd.' },
            { id: 'employee_name', label: 'Employee Full Name', type: 'text', placeholder: 'e.g. Ananya Roy' },
            { id: 'role_title', label: 'Designation / Role', type: 'text', placeholder: 'e.g. Senior Legal Counsel' },
            { id: 'compensation', label: 'Annual CTC / Remuneration', type: 'text', placeholder: 'e.g. INR 24,00,000 per annum' },
            { id: 'notice_period', label: 'Notice Period (Months)', type: 'text', placeholder: '2' }
        ],
        rti_request: [
            { id: 'applicant_name', label: 'Applicant Name & Address', type: 'textarea', placeholder: 'e.g. Priya Sharma, Flat 102, Green Enclave, Pune' },
            { id: 'public_authority', label: 'Public Authority / Department', type: 'text', placeholder: 'e.g. Public Information Officer, Municipal Corporation of Pune' },
            { id: 'info_sought', label: 'Specific Information Sought', type: 'textarea', placeholder: 'e.g. Certified copies of tender approval files for Road Project #45...' },
            { id: 'period', label: 'Period of Information', type: 'text', placeholder: 'e.g. FY 2022-23 to FY 2023-24' }
        ]
    };

    function renderFormFields(templateKey) {
        if (!templateFactsForm) return;
        templateFactsForm.innerHTML = '';
        const schema = templateSchemas[templateKey] || [];
        schema.forEach(field => {
            const group = document.createElement('div');
            group.className = 'form-group';
            const label = document.createElement('label');
            label.className = 'form-label-sm';
            label.textContent = field.label;
            group.appendChild(label);

            let input;
            if (field.type === 'textarea') {
                input = document.createElement('textarea');
                input.className = 'form-textarea-sm';
                input.rows = 3;
            } else {
                input = document.createElement('input');
                input.type = 'text';
                input.className = 'form-input-sm';
            }
            input.id = 'field_' + field.id;
            input.placeholder = field.placeholder;
            group.appendChild(input);
            templateFactsForm.appendChild(group);
        });
    }

    if (selectTemplate) {
        selectTemplate.addEventListener('change', (e) => renderFormFields(e.target.value));
        renderFormFields(selectTemplate.value);
    }

    if (btnGenerateDraft) {
        btnGenerateDraft.addEventListener('click', async () => {
            const templateKey = selectTemplate.value;
            const schema = templateSchemas[templateKey] || [];
            const facts = {};
            schema.forEach(field => {
                const input = document.getElementById('field_' + field.id);
                if (input) facts[field.id] = input.value.trim();
            });

            btnGenerateDraft.disabled = true;
            btnGenerateDraft.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating Legal Draft...';
            draftOutputContent.innerHTML = '<div class="loader-placeholder"><i class="fa-solid fa-scale-balanced fa-spin"></i><p>Drafting formal legal document under Indian legal standards...</p></div>';

            try {
                const res = await fetch('/api/legal/draft', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ template_type: templateKey, facts })
                });
                const data = await res.json();
                if (data.status === 'ok' && data.data?.draft) {
                    draftOutputContent.innerHTML = formatLegalMarkdown(data.data.draft);
                } else {
                    draftOutputContent.innerHTML = `<p class="error-text">Failed to generate draft: ${escapeHTML(data.error?.message || 'Unknown error')}</p>`;
                }
            } catch (err) {
                draftOutputContent.innerHTML = `<p class="error-text">Network error: ${escapeHTML(err.message)}</p>`;
            } finally {
                btnGenerateDraft.disabled = false;
                btnGenerateDraft.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Generate Legal Draft';
            }
        });
    }

    if (btnCopyDraft) {
        btnCopyDraft.addEventListener('click', () => {
            const text = draftOutputContent.innerText;
            if (text && !text.includes('Fill in the key facts')) {
                navigator.clipboard.writeText(text);
                window.CortexApp?.showToast('Legal draft copied to clipboard!', 'success');
            }
        });
    }

    // ----------------------------------------------------------------------
    // 2. STATUTE LOOKUP
    // ----------------------------------------------------------------------
    const inputStatuteQuery = document.getElementById('inputStatuteQuery');
    const btnSearchStatute = document.getElementById('btnSearchStatute');
    const statuteOutputContent = document.getElementById('statuteOutputContent');

    if (btnSearchStatute && inputStatuteQuery) {
        const runStatuteLookup = async () => {
            const query = inputStatuteQuery.value.trim();
            if (!query) return;

            btnSearchStatute.disabled = true;
            btnSearchStatute.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
            statuteOutputContent.innerHTML = '<div class="loader-placeholder"><i class="fa-solid fa-book-bookmark fa-spin"></i><p>Cross-referencing statutory databases & Constitution of India...</p></div>';

            try {
                const res = await fetch('/api/legal/statute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                const data = await res.json();
                if (data.status === 'ok' && data.data?.analysis) {
                    statuteOutputContent.innerHTML = formatLegalMarkdown(data.data.analysis);
                } else {
                    statuteOutputContent.innerHTML = `<p class="error-text">Statute lookup failed: ${escapeHTML(data.error?.message || 'Unknown error')}</p>`;
                }
            } catch (err) {
                statuteOutputContent.innerHTML = `<p class="error-text">Network error: ${escapeHTML(err.message)}</p>`;
            } finally {
                btnSearchStatute.disabled = false;
                btnSearchStatute.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Lookup Law';
            }
        };

        btnSearchStatute.addEventListener('click', runStatuteLookup);
        inputStatuteQuery.addEventListener('keydown', (e) => { if (e.key === 'Enter') runStatuteLookup(); });
    }

    // ----------------------------------------------------------------------
    // 3. CONCLUSION PREDICTION
    // ----------------------------------------------------------------------
    const inputPredictFacts = document.getElementById('inputPredictFacts');
    const btnRunPrediction = document.getElementById('btnRunPrediction');
    const predictOutputContent = document.getElementById('predictOutputContent');

    if (btnRunPrediction && inputPredictFacts) {
        btnRunPrediction.addEventListener('click', async () => {
            const facts = inputPredictFacts.value.trim();
            if (!facts) {
                window.CortexApp?.showToast('Please enter factual case scenario details.', 'warn');
                return;
            }

            btnRunPrediction.disabled = true;
            btnRunPrediction.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Evaluating Litigation Risk...';
            predictOutputContent.innerHTML = '<div class="loader-placeholder"><i class="fa-solid fa-crystal-ball fa-spin"></i><p>Evaluating legal precedent matrix and statutory vulnerabilities...</p></div>';

            try {
                const res = await fetch('/api/legal/predict', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ facts })
                });
                const data = await res.json();
                if (data.status === 'ok' && data.data?.prediction) {
                    predictOutputContent.innerHTML = formatLegalMarkdown(data.data.prediction);
                } else {
                    predictOutputContent.innerHTML = `<p class="error-text">Prediction failed: ${escapeHTML(data.error?.message || 'Unknown error')}</p>`;
                }
            } catch (err) {
                predictOutputContent.innerHTML = `<p class="error-text">Network error: ${escapeHTML(err.message)}</p>`;
            } finally {
                btnRunPrediction.disabled = false;
                btnRunPrediction.innerHTML = '<i class="fa-solid fa-chart-line"></i> Predict Case Outcome';
            }
        });
    }

    // ----------------------------------------------------------------------
    // 4. PRECEDENT ANALYSIS
    // ----------------------------------------------------------------------
    const inputPrecedentIssue = document.getElementById('inputPrecedentIssue');
    const btnSearchPrecedents = document.getElementById('btnSearchPrecedents');
    const precedentsOutputContent = document.getElementById('precedentsOutputContent');

    if (btnSearchPrecedents && inputPrecedentIssue) {
        const runPrecedentAnalysis = async () => {
            const issue = inputPrecedentIssue.value.trim();
            if (!issue) return;

            btnSearchPrecedents.disabled = true;
            btnSearchPrecedents.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Synthesizing Case Law...';
            precedentsOutputContent.innerHTML = '<div class="loader-placeholder"><i class="fa-solid fa-scale-balanced fa-spin"></i><p>Synthesizing landmark Supreme Court rulings and ratio decidendi...</p></div>';

            try {
                const res = await fetch('/api/legal/precedents', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ issue })
                });
                const data = await res.json();
                if (data.status === 'ok' && data.data?.precedents) {
                    precedentsOutputContent.innerHTML = formatLegalMarkdown(data.data.precedents);
                } else {
                    precedentsOutputContent.innerHTML = `<p class="error-text">Precedent synthesis failed: ${escapeHTML(data.error?.message || 'Unknown error')}</p>`;
                }
            } catch (err) {
                precedentsOutputContent.innerHTML = `<p class="error-text">Network error: ${escapeHTML(err.message)}</p>`;
            } finally {
                btnSearchPrecedents.disabled = false;
                btnSearchPrecedents.innerHTML = '<i class="fa-solid fa-scale-balanced"></i> Analyze Case Law';
            }
        };

        btnSearchPrecedents.addEventListener('click', runPrecedentAnalysis);
        inputPrecedentIssue.addEventListener('keydown', (e) => { if (e.key === 'Enter') runPrecedentAnalysis(); });
    }

    // Helper functions
    function formatLegalMarkdown(text) {
        if (!text) return '';
        let html = escapeHTML(text);
        // Bold headers
        html = html.replace(/^### (.*$)/gim, '<h3 class="legal-h3">$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2 class="legal-h2">$1</h2>');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        html = html.replace(/\n\n/g, '<br><br>');
        return `<div class="formatted-legal-text">${html}</div>`;
    }

    function escapeHTML(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
});
