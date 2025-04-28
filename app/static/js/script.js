// 全局变量
let currentRound = 0;
let gameInProgress = false;
let activeAIs = [];

// 新增：流程提示信息
let processStage = '';
let processAI = '';
let processRound = 0;

// 开始模拟游戏
function startSimulation() {
    if (gameInProgress) {
        appendLog("游戏已经在进行中！");
        return;
    }
    // 清空日志，重置状态（不直接清空AI面板，后续用renderAIPanels刷新）
    clearLog();
    processStage = '';
    processAI = '';
    processRound = 0;
    gameInProgress = false;
    // 重新请求后端，进入预检
    fetch('/start_game', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            appendLog("错误: " + data.error);
            return;
        }
        gameInProgress = true;
        // 预检阶段显示为第0轮
        appendLog("========== 预检阶段 (第0轮) ==========");
        // 先拉取一次最新状态，确保AI面板和日志同步
        renderGameState();
        // 追加预检发言到AI面板
        data.responses.forEach(response => {
            appendLog(`${response.name}: ${response.response}`);
            updateAIPanel(response.ai_id, response.name, response.response);
        });
        // 预检阶段结束后，自动进入第一轮
        setTimeout(() => {
            appendLog("========== 第1轮开始 ==========");
            nextRound();
        }, 800);
    })
    .catch(error => {
        console.error('Error:', error);
        appendLog("发生错误: " + error);
    });
}

// 进入下一轮
function nextRound() {
    if (!gameInProgress) {
        console.log("游戏尚未开始，请先点击开始模拟！");
        return;
    }
    fetch('/next_round', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            appendLog("错误: " + data.error);
            if (data.is_game_over) gameInProgress = false;
            renderGameState();
            return;
        }
        // 输出本轮所有AI发言
        if (data.responses && data.responses.length > 0) {
            appendLog(`\n========== 第${data.round}轮 ==========`);
            data.responses.forEach(resp => {
                appendLog(`${resp.name}: ${resp.response}`);
            });
        }
        // 输出投票
        if (data.votes && data.votes.length > 0) {
            appendLog("\n----- 投票阶段 -----");
            data.votes.forEach(v => {
                let voter = data.player_map[v.voter_id];
                let target = v.target_id === '0' ? '弃权' : (data.player_map[v.target_id] || v.target_id);
                appendLog(`${voter} 投票给 ${target}`);
            });
        }
        // 淘汰信息
        if (data.eliminated) {
            let eliminatedName = data.player_map && data.eliminated in data.player_map ? data.player_map[data.eliminated] : data.eliminated;
            appendLog(`\n${eliminatedName} 被淘汰了。`);
        }
        // 胜负
        if (data.winner) {
            let winnerName = data.player_map ? data.player_map[data.winner] : data.winner;
            appendLog(`\n游戏结束！胜者是: ${winnerName}`);
            gameInProgress = false;
        }
        renderGameState();
        // 自动进入下一轮
        if (data.has_next_round) {
            setTimeout(() => nextRound(), 1200);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        appendLog("发生错误: " + error);
        renderGameState();
    });
}

// 拉取并渲染当前游戏状态
function renderGameState() {
    fetch('/get_game_state')
        .then(response => response.json())
        .then(state => {
            renderAIPanels(state);
            const logContainer = document.getElementById('log-text');
            logContainer.innerHTML = '';
            if (!state || typeof state.round !== 'number') {
                logContainer.innerHTML = '<div>暂无游戏进行中。</div>';
                return;
            }
            // 轮次
            logContainer.innerHTML += `<h3>第${state.round}轮</h3>`;
            // 不再输出发言历史到主日志区，只在AI面板显示
            // 投票历史
            if (state.votes && state.votes.length > 0) {
                logContainer.innerHTML += '<div><b>投票历史：</b></div>';
                state.votes.forEach(v => {
                    logContainer.innerHTML += `<div>第${v.round}轮：${state.player_map[v.voter_id]} 投票给 ${state.player_map[v.target_id]}</div>`;
                });
            }
            // 淘汰历史
            if (state.eliminated && state.eliminated.length > 0) {
                logContainer.innerHTML += '<div><b>淘汰历史：</b></div>';
                state.eliminated.forEach(e => {
                    logContainer.innerHTML += `<div>第${e.round}轮淘汰：${state.player_map[e.ai_id]}</div>`;
                });
            }
            // 胜负
            if (state.winner) {
                logContainer.innerHTML += `<div style='color:green'><b>胜者：${state.player_map[state.winner]}</b></div>`;
            }
            // 当前活跃AI
            if (state.activeAIs) {
                activeAIs = state.activeAIs.map(id => ({ id, name: state.player_map[id] }));
            }
            // 刷新AI积分
            refreshAIList();
            logContainer.scrollTop = logContainer.scrollHeight;
            renderProcessInfo();
        })
        .catch(error => {
            console.error('Error fetching game state:', error);
        });
}

// 新增：流程提示渲染
function renderProcessInfo() {
    const logContainer = document.getElementById('log-text');
    let info = '';
    if (processRound && processStage && processAI) {
        info = `<div style='color:#1976d2;margin-bottom:8px;'><b>第${processRound}轮，阶段：${processStage}，当前AI：${processAI}</b></div>`;
    }
    // 插入到最前面
    logContainer.innerHTML = info + logContainer.innerHTML;
}

// 打开添加AI弹窗
function openAddAIDialog() {
    document.getElementById('ai-name').value = '';
    document.getElementById('ai-apikey').value = '';
    document.getElementById('ai-apibase').value = '';
    document.getElementById('modal-add-ai').style.display = 'block';
}
// 关闭弹窗
function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}
// 保存新AI
function saveNewAI() {
    const name = document.getElementById('ai-name').value.trim();
    const apikey = document.getElementById('ai-apikey').value.trim();
    const apibase = document.getElementById('ai-apibase').value.trim();
    if (!name || !apikey || !apibase) {
        alert('请填写完整信息');
        return;
    }
    fetch('/add_ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, apikey, apibase })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { alert(data.error); return; }
        closeModal('modal-add-ai');
        refreshAIList();
    });
}
// 编辑AI
function editAI(id) {
    fetch('/get_data').then(r=>r.json()).then(data=>{
        const ai = data.find(a=>a.id===id);
        if (!ai) return;
        document.getElementById('edit-ai-id').value = ai.id;
        document.getElementById('edit-ai-name').value = ai.name;
        document.getElementById('edit-ai-apikey').value = ai.apikey;
        document.getElementById('edit-ai-apibase').value = ai.apibase;
        document.getElementById('modal-edit-ai').style.display = 'block';
    });
}
// 保存编辑AI
function saveEditedAI() {
    const id = document.getElementById('edit-ai-id').value;
    const name = document.getElementById('edit-ai-name').value.trim();
    const apikey = document.getElementById('edit-ai-apikey').value.trim();
    const apibase = document.getElementById('edit-ai-apibase').value.trim();
    if (!name || !apikey || !apibase) {
        alert('请填写完整信息');
        return;
    }
    fetch('/edit_ai/' + id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, apikey, apibase })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { alert(data.error); return; }
        closeModal('modal-edit-ai');
        refreshAIList();
    });
}
// 删除AI
function deleteAI(id) {
    if (!confirm('确定要删除该AI吗？')) return;
    fetch('/delete_ai/' + id, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => { refreshAIList(); });
}
// 保存提示词
function savePrompt() {
    const text = document.getElementById('prompt-text').value;
    fetch('/set_prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
    })
    .then(r => r.json())
    .then(data => { alert('提示词已保存'); });
}

// 清空日志
function clearLog() {
    const logContainer = document.getElementById('log-text');
    if (logContainer) {
    //    logContainer.innerHTML = '';
    }
}

// 追加日志
function appendLog(message) {
    const logContainer = document.getElementById('log-text');
    if (logContainer) {
        const logEntry = document.createElement('div');
        logEntry.innerHTML = message;
        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

// 创建AI面板
function createAIPanel(aiId, aiName, initialMessage) {
    const aiPanels = document.getElementById('ai-panels');
    const panel = document.createElement('div');
    panel.id = `ai-panel-${aiId}`;
    panel.className = 'ai-panel';
    panel.style = 'border:1px solid #ccc;padding:8px;width:260px;min-height:120px;background:#fff;border-radius:8px;box-shadow:0 2px 8px #eee;';
    panel.innerHTML = `
        <b>${aiName}</b>
        <div id="ai-msgs-${aiId}" style="margin-top:6px;font-size:14px;max-height:180px;overflow-y:auto;">
            <div style='margin-bottom:4px;'>${initialMessage}</div>
        </div>
    `;
    aiPanels.appendChild(panel);
}

// 更新AI面板
function updateAIPanel(aiId, aiName, message) {
    const msgDiv = document.getElementById(`ai-msgs-${aiId}`);
    if (msgDiv) {
        msgDiv.innerHTML += `<div style='margin-bottom:4px;'>${message}</div>`;
        msgDiv.scrollTop = msgDiv.scrollHeight;
    }
}

// AI面板渲染
function renderAIPanels(state) {
    const aiPanels = document.getElementById('ai-panels');
    // 每次都清空再重建，保证同步
    aiPanels.innerHTML = '';
    if (!state || !state.player_map) return;
    Object.entries(state.player_map).forEach(([aiId, aiName]) => {
        const panel = document.createElement('div');
        panel.id = `ai-panel-${aiId}`;
        panel.className = 'ai-panel';
        panel.style = 'border:1px solid #ccc;padding:8px;width:260px;min-height:120px;background:#fff;border-radius:8px;box-shadow:0 2px 8px #eee;';
        let status = '';
        if (state.eliminated && state.eliminated.some(e => e.ai_id === aiId)) {
            status = '<span style="color:red">（已淘汰）</span>';
        } else if (state.activeAIs && state.activeAIs.includes(aiId)) {
            status = '<span style="color:green">（存活）</span>';
        }
        panel.innerHTML = `<b>${aiName} ${status}</b><div id="ai-msgs-${aiId}" style="margin-top:6px;font-size:14px;max-height:180px;overflow-y:auto;"></div>`;
        aiPanels.appendChild(panel);
        // 更新消息
        const msgDiv = document.getElementById(`ai-msgs-${aiId}`);
        if (msgDiv && state.history) {
            msgDiv.innerHTML = '';
            state.history.forEach(roundObj => {
                const response = roundObj.responses.find(resp => resp.ai_id === aiId);
                if (response) {
                    msgDiv.innerHTML += `<div style='margin-bottom:4px;'><b>第${roundObj.round}轮:</b> ${response.response}</div>`;
                }
            });
            msgDiv.scrollTop = msgDiv.scrollHeight;
        }
    });
}

// AI列表刷新
function refreshAIList() {
    fetch('/get_data')
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('ai-list-body');
            tbody.innerHTML = '';
            data.forEach(ai => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${ai.id}</td>
                    <td>${ai.name}</td>
                    <td>${ai.apikey}</td>
                    <td>${ai.apibase}</td>
                    <td>${ai.score}</td>
                    <td>
                        <button class="btn" onclick="editAI('${ai.id}')">编辑</button>
                        <button class="btn btn-cancel" onclick="deleteAI('${ai.id}')">删除</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        });
}

// 加载AI列表
function loadAIList() {
    refreshAIList();
}

// 当前投票者ID（可根据实际业务调整，默认第一个AI）
let currentVoterId = '';
window.onload = function() {
    loadAIList();
    renderGameState();
    // 默认设置当前投票者为第一个AI
    fetch('/get_data').then(r=>r.json()).then(data=>{if(data.length>0){currentVoterId=data[0].id;}});
};