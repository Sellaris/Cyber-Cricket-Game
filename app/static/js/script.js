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
    clearLog();
    processStage = '';
    processAI = '';
    processRound = 0;
    gameInProgress = false;

    console.log("[startSimulation] 开始调用start_game");
    fetch('/start_game', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            appendLog("错误: " + data.error);
            return;
        }
        console.log("[startSimulation] start_game返回:", data);
        gameInProgress = true;
        // 预检阶段显示为第0轮
        appendLog("========== 预检阶段 (第0轮) ==========");
        // 输出预检发言
        if (data.responses && data.responses.length > 0) {
            data.responses.forEach(response => {
                appendLog(`${response.name}: ${response.response}`);
            });
        }
        renderGameState();

        // 直接进入发言阶段
        setTimeout(() => {
            processStage = '发言阶段';
            processRound = 1;
            // 显式请求下一轮数据
            fetch('/next_round', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ round: 1 })
            })
            .then(r => r.json())
            .then(() => stepThroughAISpeak(0, 'speak', 1));
        }, 1000);
    })
    .catch(error => {
        console.error('[startSimulation] error:', error);
        appendLog("发生错误: " + error);
        gameInProgress = false;
    });
}

// 统一处理游戏阶段
function handleGameStage(stageType, aiIndex, round=processRound) {
    const totalActiveAIs = activeAIs.length;
    
    fetch('/step_round', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            stage: stageType,
            ai_index: aiIndex,
            round: round
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            appendLog("错误: " + data.error);
            if (data.is_game_over) {
                gameInProgress = false;
            }
            renderGameState();
            
            // 强制推进流程
            if (aiIndex >= totalActiveAIs - 1 && !data.is_game_over) {
                console.log(`[流程推进] 异常恢复：强制进入${stageType === 'vote' ? '新轮次' : '投票阶段'}`);
                setTimeout(() => handleNextStage(stageType, round), 1500);
            }
            return;
        }

        // 显示操作
        if (stageType === 'speak') {
            updateAIPanel(data.ai_id, data.ai_name, data.response);
        } else {
            appendLog(`${data.ai_name} 投票给 ${data.target_name}`);
        }

        if (stageType === 'vote') {
            if (data.skip_elimination) {
                appendLog(`[系统] 本轮投票平局，${data.message}`);
            } else if (data.eliminated_ai) {
                appendLog(`${data.target_name} 被淘汰`);
            }
        }
        
        // 流程推进
        if (aiIndex < totalActiveAIs - 1) {
            setTimeout(() => 
                handleGameStage(stageType, aiIndex + 1, round), 
                stageType === 'speak' ? 800 : 1000
            );
        } else {
            // 阶段转换
            setTimeout(() => {
                if (!gameInProgress) return;
                
                if (stageType === 'speak') {
                    // 进入投票阶段
                    processStage = '投票阶段';
                    stepThroughAIVote(0, round);
                } else {
                    // 完成一轮
                    appendLog(`\n========== 第${round}轮结束 ==========\n`);
                    // 检查游戏状态
                    fetch('/get_game_state')
                        .then(r => r.json())
                        .then(state => {
                            if (state.winner || state.activeAIs.length <= 1) {
                                gameInProgress = false;
                                appendLog(state.winner ? `胜者：${state.player_map[state.winner]}` : '平局！');
                                renderGameState();
                                return;
                            }
                            
                            // 开始新轮次
                            appendLog(`\n========== 第${round+1}轮开始 ==========\n`);
                            processStage = '发言阶段';
                            processRound = round + 1;
                            stepThroughAISpeak(0, 'speak', round + 1);
                        });
                }
            }, stageType === 'speak' ? 1200 : 1500);
        }
    })
    .catch(error => {
        console.error(`[${stageType}] error:`, error);
        appendLog(`${stageType === 'speak' ? '发言' : '投票'}错误: ` + error);
        
        // 降级处理
        if (aiIndex >= totalActiveAIs - 1) {
            console.warn("[降级模式] 网络异常，尝试自动推进到下一阶段");
            setTimeout(() => {
                if (gameInProgress) handleNextStage(stageType, round);
            }, stageType === 'speak' ? 2000 : 2500);
        }
        renderGameState();
    });
}

// 统一流程推进
function handleNextStage(currentStageType, round) {
    if (currentStageType === 'speak') {
        processStage = '投票阶段';
        stepThroughAIVote(0, round);
    } else {
        appendLog(`\n========== 第${round+1}轮开始 ==========\n`);
        processStage = '发言阶段';
        processRound = round + 1;
        stepThroughAISpeak(0, 'speak', round + 1);
    }
}

// 新增逐步处理发言函数
function stepThroughAISpeak(aiIndex, stage='speak', round=processRound) {
    handleGameStage(stage, aiIndex, round);
}

// 新增逐步处理投票的函数
function stepThroughAIVote(aiIndex, round) {
    handleGameStage('vote', aiIndex, round);
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