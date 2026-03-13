document.addEventListener('DOMContentLoaded', () => {
    // --- Selectors ---
    const tabs = document.querySelectorAll('[data-tab]');
    const sections = document.querySelectorAll('.tab-content');
    
    // Voice elements
    const voiceDropZone = document.getElementById('voice-drop-zone');
    const voiceFileInput = document.getElementById('voice-file-input');
    const voiceTitleInput = document.getElementById('voice-meeting-title');
    const transcribeBtn = document.getElementById('transcribe-btn');
    
    // Text elements
    const textTitleInput = document.getElementById('text-meeting-title');
    const textTranscriptInput = document.getElementById('text-transcript-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    
    // Pipeline elements
    const pipeNodes = {
        input: document.getElementById('pipe-input'),
        stt: document.getElementById('pipe-stt'),
        agent: document.getElementById('pipe-agent'),
        delta: document.getElementById('pipe-delta'),
        board: document.getElementById('pipe-board')
    };
    
    // Board & Meetings
    const kanbanContainer = document.getElementById('kanban-container');
    const meetingsList = document.getElementById('meetings-list');
    
    // Modal
    const modal = document.getElementById('modal-overlay');
    const modalHeader = document.getElementById('modal-header');
    const modalBody = document.getElementById('modal-body');

    // --- Tab Logic ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.getAttribute('data-tab');
            
            // Toggle tabs
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Toggle sections
            sections.forEach(s => {
                if (s.id === `section-${target}`) s.classList.remove('hidden');
                else s.classList.add('hidden');
            });

            if (target === 'board') fetchTasks();
            if (target === 'meetings') fetchMeetings();
        });
    });

    // --- Pipeline Logic ---
    const setPipelineStage = (stage) => {
        const stages = ['input', 'stt', 'agent', 'delta', 'board'];
        const currentIdx = stages.indexOf(stage);
        
        stages.forEach((s, i) => {
            const node = pipeNodes[s];
            node.classList.remove('active', 'completed');
            if (i < currentIdx) node.classList.add('completed');
            else if (i === currentIdx) node.classList.add('active');
        });
    };

    // --- Voice Workflow ---
    voiceDropZone.addEventListener('click', () => voiceFileInput.click());
    
    voiceDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        voiceDropZone.classList.add('border-brand-purple/50', 'bg-white/5');
    });

    voiceDropZone.addEventListener('dragleave', () => {
        voiceDropZone.classList.remove('border-brand-purple/50', 'bg-white/5');
    });

    voiceDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        voiceDropZone.classList.remove('border-brand-purple/50', 'bg-white/5');
        voiceFileInput.files = e.dataTransfer.files;
        if (voiceFileInput.files.length > 0) {
            const file = voiceFileInput.files[0];
            const sizeKB = (file.size / 1024).toFixed(1);
            voiceDropZone.innerHTML = `
                <div class="text-4xl mb-4">🎵</div>
                <p class="text-sm font-semibold text-white">${file.name}</p>
                <p class="text-[11px] text-slate-500 mt-1">${sizeKB} KB</p>
                <p class="text-[11px] text-indigo-400 mt-2">Click to change</p>
            `;
        }
    });

    voiceFileInput.addEventListener('change', () => {
        if (voiceFileInput.files.length > 0) {
            const file = voiceFileInput.files[0];
            const sizeKB = (file.size / 1024).toFixed(1);
            voiceDropZone.innerHTML = `
                <div class="text-4xl mb-4">🎵</div>
                <p class="text-sm font-semibold text-white">${file.name}</p>
                <p class="text-[11px] text-slate-500 mt-1">${sizeKB} KB</p>
                <p class="text-[11px] text-indigo-400 mt-2">Click to change</p>
            `;
        }
    });

    transcribeBtn.addEventListener('click', async () => {
        const file = voiceFileInput.files[0];
        if (!file) {
            alert('Please select an audio file first.');
            return;
        }

        try {
            transcribeBtn.disabled = true;
            transcribeBtn.innerHTML = '<span>⏳</span> Processing...';
            setPipelineStage('stt');

            const formData = new FormData();
            formData.append('file', file);
            formData.append('title', voiceTitleInput.value || file.name.split('.')[0]);
            
            const resp = await fetch('/api/meetings/upload', { method: 'POST', body: formData });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Upload failed');
            }
            const meeting = await resp.json();
            
            await triggerAnalysis(meeting.id);
        } catch (err) {
            console.error(err);
            alert('Upload/Transcription failed: ' + err.message);
        } finally {
            transcribeBtn.disabled = false;
            transcribeBtn.innerHTML = '<span>🚀</span> Transcribe';
        }
    });

    // --- Text Workflow ---
    analyzeBtn.addEventListener('click', async () => {
        const transcript = textTranscriptInput.value;
        if (!transcript) {
            alert('Please enter a transcript.');
            return;
        }

        try {
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<span>⏳</span> Analyzing...';
            setPipelineStage('input');

            const formData = new FormData();
            formData.append('title', textTitleInput.value || 'Text Meeting');
            formData.append('transcript', transcript);
            
            const resp = await fetch('/api/meetings/transcript', { method: 'POST', body: formData });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Submission failed');
            }
            const meeting = await resp.json();
            
            await triggerAnalysis(meeting.id);
        } catch (err) {
            console.error(err);
            alert('Submission failed: ' + err.message);
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = '<span>✈️</span> Submit & Analyze';
        }
    });

    // --- Shared Analysis ---
    async function triggerAnalysis(meetingId) {
        try {
            setPipelineStage('agent');
            const resp = await fetch(`/api/meetings/${meetingId}/analyze`, { method: 'POST' });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Analysis failed');
            }
            const result = await resp.json();
            
            setPipelineStage('delta');
            setTimeout(() => setPipelineStage('board'), 800);
            
            showResultModal(result);
        } catch (err) {
            console.error(err);
            alert('Analysis failed: ' + err.message);
        }
    }

    // --- Data Fetching ---
    async function fetchTasks() {
        try {
            const resp = await fetch('/api/board/tasks');
            const data = await resp.json();
            renderBoard(data.tasks);
        } catch (err) {
            console.error(err);
        }
    }

    function renderBoard(tasks) {
        const columns = {
            todo: { label: '📋 To Do', color: 'slate', items: tasks.filter(t => t.status === 'todo') },
            in_progress: { label: '🔨 In Progress', color: 'amber', items: tasks.filter(t => t.status === 'in_progress') },
            done: { label: '✅ Done', color: 'emerald', items: tasks.filter(t => t.status === 'done') }
        };

        kanbanContainer.innerHTML = Object.entries(columns).map(([status, col]) => `
            <div class="bg-brand-navyLight border border-brand-border rounded-2xl p-6">
                <div class="flex items-center justify-between mb-6">
                    <h3 class="text-sm font-bold text-white">${col.label}</h3>
                    <span class="text-[11px] font-bold bg-white/5 px-2 py-0.5 rounded-full">${col.items.length}</span>
                </div>
                <div class="space-y-3 min-h-[100px]">
                    ${col.items.length === 0
                        ? '<p class="text-[11px] text-slate-600 italic text-center py-8">No tasks</p>'
                        : col.items.map(t => taskCard(t, status)).join('')}
                </div>
            </div>
        `).join('');
    }

    function taskCard(task, currentStatus) {
        const moveButtons = [];
        if (currentStatus !== 'todo') moveButtons.push(`<button onclick="window._moveTask(${task.id}, 'todo')" class="text-[10px] font-bold text-slate-400 hover:text-white px-2 py-1 rounded border border-white/10 hover:bg-white/5">📋 To Do</button>`);
        if (currentStatus !== 'in_progress') moveButtons.push(`<button onclick="window._moveTask(${task.id}, 'in_progress')" class="text-[10px] font-bold text-amber-400 px-2 py-1 rounded border border-amber-500/20 hover:bg-amber-500/10">🔨 WIP</button>`);
        if (currentStatus !== 'done') moveButtons.push(`<button onclick="window._moveTask(${task.id}, 'done')" class="text-[10px] font-bold text-emerald-400 px-2 py-1 rounded border border-emerald-500/20 hover:bg-emerald-500/10">✅ Done</button>`);

        return `
            <div class="bg-brand-navy border border-white/5 rounded-xl p-4 hover:border-brand-purple/30 transition-colors group">
                <div class="flex justify-between mb-2">
                    <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-white/5">${task.priority}</span>
                    <span class="text-[10px] text-slate-500">#${task.id}</span>
                </div>
                <h4 class="text-sm font-bold text-white mb-1">${task.title}</h4>
                <p class="text-xs text-slate-500 mb-3 line-clamp-2">${task.description || ''}</p>
                <div class="text-[10px] text-slate-400 font-semibold mb-3">👤 ${task.assignee || 'Unassigned'}</div>
                <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    ${moveButtons.join('')}
                    <button onclick="window._deleteTask(${task.id})" class="text-[10px] font-bold text-red-400 px-2 py-1 rounded border border-red-500/20 hover:bg-red-500/10">🗑️</button>
                </div>
            </div>
        `;
    }

    // Expose move/delete globally for inline onclick
    window._moveTask = async (taskId, newStatus) => {
        try {
            await fetch(`/api/board/tasks/${taskId}/move`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });
            fetchTasks();
        } catch (err) { console.error(err); }
    };

    window._deleteTask = async (taskId) => {
        if (!confirm('Delete this task?')) return;
        try {
            await fetch(`/api/board/tasks/${taskId}`, { method: 'DELETE' });
            fetchTasks();
        } catch (err) { console.error(err); }
    };

    async function fetchMeetings() {
        try {
            const resp = await fetch('/api/meetings');
            const data = await resp.json();
            renderMeetings(data.meetings);
        } catch (err) {
            console.error(err);
        }
    }

    function renderMeetings(meetings) {
        if (!meetings.length) {
            meetingsList.innerHTML = '<div class="text-center text-slate-500 py-12 italic">No meetings yet.</div>';
            return;
        }
        meetingsList.innerHTML = meetings.map(m => `
            <div class="bg-brand-navyLight border border-brand-border p-6 rounded-2xl flex items-center justify-between hover:border-brand-purple/30 transition-colors">
                <div class="flex items-center gap-4">
                    <div class="w-10 h-10 rounded-full ${m.source_type === 'voice' ? 'bg-indigo-500/10 text-indigo-400' : 'bg-cyan-500/10 text-cyan-400'} flex items-center justify-center text-lg">
                        ${m.source_type === 'voice' ? '🎙️' : '📄'}
                    </div>
                    <div>
                        <h4 class="font-bold text-white">${m.title}</h4>
                        <p class="text-xs text-slate-500">${new Date(m.created_at).toLocaleString()}</p>
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    <span class="text-[11px] font-bold uppercase tracking-widest px-3 py-1 rounded-full bg-brand-purple/10 text-brand-purple border border-brand-purple/20">
                        ${m.status}
                    </span>
                    ${m.status === 'pending' ? `<button onclick="window._analyzeFromList(${m.id})" class="text-xs font-bold text-brand-purple hover:text-white px-3 py-1.5 rounded-lg border border-brand-purple/30 hover:bg-brand-purple/10">⚡ Analyze</button>` : ''}
                    ${m.status === 'analyzed' ? `<button onclick="window._viewResults(${m.id})" class="text-xs font-bold text-emerald-400 hover:text-white px-3 py-1.5 rounded-lg border border-emerald-500/30 hover:bg-emerald-500/10">📊 View</button>` : ''}
                </div>
            </div>
        `).join('');
    }

    window._analyzeFromList = async (meetingId) => {
        await triggerAnalysis(meetingId);
        fetchMeetings();
    };

    window._viewResults = async (meetingId) => {
        try {
            const resp = await fetch(`/api/meetings/${meetingId}/results`);
            const data = await resp.json();
            showDetailModal(data);
        } catch (err) { console.error(err); }
    };

    // --- Modal Logic ---
    function showResultModal(data) {
        modalHeader.innerHTML = `
            <span class="text-brand-purple text-[11px] font-black uppercase tracking-widest block mb-2">Analysis Complete</span>
            <h2 class="text-3xl font-bold text-white">Meeting Insights</h2>
        `;
        
        modalBody.innerHTML = `
            <div class="space-y-6">
                <section>
                    <h3 class="text-sm font-bold text-slate-200 mb-2 uppercase tracking-wide">Summary</h3>
                    <p class="text-sm text-slate-400 leading-relaxed whitespace-pre-line">${data.summary || 'No summary available.'}</p>
                </section>
                <section>
                    <h3 class="text-sm font-bold text-slate-200 mb-3 uppercase tracking-wide">Decisions</h3>
                    <ul class="space-y-2">
                        ${(data.decisions || []).map(d => `<li class="text-sm text-slate-400 flex items-start gap-3"><span class="text-brand-purple">✓</span> ${d}</li>`).join('')}
                    </ul>
                </section>
                <section>
                    <h3 class="text-sm font-bold text-slate-200 mb-3 uppercase tracking-wide">Tasks Created (${data.action_items_count || 0})</h3>
                    <div class="space-y-2">
                        ${(data.tasks || []).map(t => `
                            <div class="bg-brand-navy border border-white/5 rounded-lg p-3">
                                <p class="text-sm font-semibold text-white">${t.title}</p>
                                <div class="flex gap-2 mt-1">
                                    <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-white/5">${t.priority}</span>
                                    <span class="text-[10px] text-slate-500">👤 ${t.assignee || 'Unassigned'}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </section>
                <div class="pt-4 flex justify-end">
                    <button id="view-board-btn" class="bg-brand-purple text-white px-6 py-2 rounded-lg text-sm font-bold">View in Kanban Board</button>
                </div>
            </div>
        `;

        modal.classList.remove('hidden');
        modal.classList.add('flex');

        document.getElementById('view-board-btn').onclick = () => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            document.querySelector('[data-tab="board"]').click();
        };
    }

    function showDetailModal(data) {
        const meeting = data.meeting || {};
        const analysis = data.analysis || {};
        const tasks = data.tasks || [];

        modalHeader.innerHTML = `
            <h2 class="text-xl font-bold text-white">${meeting.title || 'Meeting Details'}</h2>
            <p class="text-[11px] text-slate-500 mt-1">${meeting.source_type === 'voice' ? '🎙️ Voice' : '📄 Text'} · ${new Date(meeting.created_at).toLocaleString()}</p>
        `;

        modalBody.innerHTML = `
            <div class="space-y-6">
                ${analysis.summary ? `<section><h4 class="text-xs font-black uppercase text-slate-500 tracking-widest mb-2">Summary</h4><p class="text-sm text-slate-300 whitespace-pre-line">${analysis.summary}</p></section>` : ''}
                ${(analysis.decisions || []).length ? `<section><h4 class="text-xs font-black uppercase text-slate-500 tracking-widest mb-2">Decisions</h4><ul class="list-disc list-inside space-y-1">${analysis.decisions.map(d => `<li class="text-sm text-slate-300">${d}</li>`).join('')}</ul></section>` : ''}
                <section>
                    <h4 class="text-xs font-black uppercase text-slate-500 tracking-widest mb-2">Action Items (${tasks.length})</h4>
                    <div class="space-y-2">${tasks.map(t => `<div class="bg-brand-navy border border-white/5 rounded-lg p-3"><p class="text-sm font-semibold text-white">${t.title}</p><p class="text-[11px] text-slate-500 mt-1">${t.description || ''}</p></div>`).join('')}</div>
                </section>
            </div>
        `;

        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    document.getElementById('close-modal').onclick = () => {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    };

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }
    });

    // Initial Load
    setPipelineStage('input');
});