from flask import Blueprint, request, jsonify, render_template
from app.models import load_data, save_data, load_prompt, save_prompt
from app.services import get_client, call_api, call_vote_api
import os
import uuid
import json
import random
import logging
api_bp = Blueprint('api', __name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'ai_data.json')
PROMPT_FILE = os.path.join(os.path.dirname(__file__), '..', 'prompt.txt')
GAME_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'game_state.json')

# game_state 读写

def load_game_state():
    if os.path.exists(GAME_STATE_FILE):
        with open(GAME_STATE_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return None
    return None

def save_game_state(state):
    with open(GAME_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# 日志记录
logging.basicConfig(filename='cyber_cricket.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

@api_bp.route('/')
def index():
    prompt = load_prompt()
    return render_template('index.html', prompt=prompt)

@api_bp.route('/get_data', methods=['GET'])
def get_data():
    data = load_data()
    return jsonify(data)

@api_bp.route('/add_ai', methods=['POST','GET'])
def add_ai():
    data = load_data()
    name = request.json.get('name')
    apikey = request.json.get('apikey')
    apibase = request.json.get('apibase')
    # 唯一性校验
    if not name or not apikey or not apibase:
        return jsonify({"error": "名称和 API 均不能为空！"}), 400
    if any(ai['name'] == name for ai in data):
        return jsonify({"error": "AI 名称已存在！"}), 400
    if any(ai['apikey'] == apikey for ai in data):
        return jsonify({"error": "API Key 已存在！"}), 400
    if any(ai['apibase'] == apibase for ai in data):
        return jsonify({"error": "API Base 已存在！"}), 400
    new_ai = {
        "id": str(uuid.uuid4()),
        "name": name,
        "apikey": apikey,
        "apibase": apibase,
        "score": 0,
        "messages": []
    }
    data.append(new_ai)
    save_data(data)
    return jsonify(new_ai)

@api_bp.route('/edit_ai/<ai_id>', methods=['PUT'])
def edit_ai(ai_id):
    data = load_data()
    name = request.json.get('name')
    apikey = request.json.get('apikey')
    apibase = request.json.get('apibase')
    if not name or not apikey or not apibase:
        return jsonify({"error": "名称和 API 均不能为空！"}), 400
    ai = next((item for item in data if item["id"] == ai_id), None)
    if not ai:
        return jsonify({"error": "AI 未找到"}), 404
    ai["name"] = name
    ai["apikey"] = apikey
    ai["apibase"] = apibase
    save_data(data)
    return jsonify(ai)

@api_bp.route('/delete_ai/<ai_id>', methods=['DELETE'])
def delete_ai(ai_id):
    data = load_data()
    data = [ai for ai in data if ai["id"] != ai_id]
    save_data(data)
    return jsonify({"message": "AI 已删除"})

@api_bp.route('/get_prompt', methods=['GET'])
def get_prompt():
    prompt = load_prompt()
    return jsonify({"prompt": prompt})

@api_bp.route('/set_prompt', methods=['POST','GET'])
def set_prompt():
    text = request.json.get('text')
    save_prompt(text)
    return jsonify({"message": "提示词已保存"})

@api_bp.route('/call_ai/<ai_id>', methods=['POST','GET'])
def call_ai(ai_id):
    data = load_data()
    ai = next((item for item in data if item["id"] == ai_id), None)
    if not ai:
        return jsonify({"error": "AI 未找到"}), 404
    message = request.json.get('message')
    if not message:
        return jsonify({"error": "消息不能为空"}), 400
    response = call_api(ai, message, is_your_turn=True)
    return jsonify({"response": response})

@api_bp.route('/start_game', methods=['POST','GET'])
def start_game():
    print("[阶段提示] 游戏初始化，准备分配玩家编号和清空历史消息。")
    data = load_data()
    if len(data) < 2:
        return jsonify({"error": "需要至少2个AI才能开始游戏"}), 400
    # 只清空 messages，不清零 score
    for ai in data:
        ai["messages"] = []
    save_data(data)
    # 分配玩家序号
    player_map = {}
    for idx, ai in enumerate(data):
        player_map[ai['id']] = f"玩家{idx+1}"
    print(f"[详细] 玩家编号分配完成：{player_map}")
    # 初始化 game_state
    state = {
        "round": 0,  # 预检阶段为第0轮
        "activeAIs": [ai['id'] for ai in data],
        "player_map": player_map,  # id->玩家序号
        "history": [],  # 每轮发言
        "votes": [],    # 每轮投票
        "eliminated": [],
        "last_vote": {},
        "winner": None
    }
    save_game_state(state)
    print("[阶段提示] 进入预检阶段，每个AI进行自我介绍。")
    prompt = load_prompt()
    responses = []
    for ai in data:
        try:
            ai_name = player_map[ai['id']]
            print(f"[详细] 预检自我介绍，AI：{ai_name} (ID: {ai['id']})")
            response = call_api(ai, prompt, is_your_turn=True, all_messages=[], ai_name=ai_name)
            responses.append({
                "ai_id": ai["id"],
                "name": ai_name,
                "response": response
            })
            # 查重写入messages
            if not ai["messages"] or ai["messages"][-1]["content"] != response:
                ai["messages"].append({
                    "role": "assistant",
                    "ai_name": ai_name,
                    "content": response
                })
        except Exception as e:
            logging.error(f"AI {ai['name']} 响应错误: {str(e)}")
            print(f"[错误] AI {ai['name']} 预检自我介绍出错: {str(e)}")
            return jsonify({"error": f"AI {ai['name']} 响应错误: {str(e)}"}), 500
    save_data(data)
    # 预检阶段 history 只写 round=0
    state['history'] = [{"round": 0, "responses": responses}]
    save_game_state(state)
    print("[阶段提示] 预检阶段结束，进入第1轮正式发言。")
    # 新增：自动推进到第一轮
    try:
        # 初始化第一轮数据结构
        new_round = {
            "round": 1,
            "responses": []
        }
        state['history'].append(new_round)
        state['round'] = 1
        save_game_state(state)
        return jsonify({"responses": responses, "round": 0, "player_map": player_map})
    except Exception as e:
        logging.error(f"推进到第一轮失败: {str(e)}")
        return jsonify({"error": f"初始化第一轮失败: {str(e)}"}), 500

@api_bp.route('/next_round', methods=['POST','GET'])
def next_round():
    print("[DEBUG] 开始执行next_round")
    data = load_data()
    state = load_game_state()
    
    if not state or not state.get('activeAIs'):
        print("[错误] 游戏未开始或未找到活跃AI")
        return jsonify({"error": "请先开始游戏"}), 400

    # 当前轮次
    current_round = state['round']
    print(f"[DEBUG] 当前轮次：{current_round}")
    
    # 确保当前轮次状态正确
    if not state['history']:
        print("[错误] 未找到历史记录")
        return jsonify({"error": "游戏状态异常"}), 400
    
    # 获取当前轮次的历史记录
    current_round_history = next((h for h in state['history'] if h['round'] == current_round), None)
    if not current_round_history:
        print(f"[错误] 未找到当前轮次 {current_round} 的历史记录")
        return jsonify({"error": "游戏状态异常"}), 400

    # 发言阶段
    if not current_round_history.get('responses'):
        print(f"[DEBUG] 第{current_round}轮发言阶段开始")
        # 组装历史消息
        all_history = []
        for round_obj in state['history']:
            if round_obj['round'] < current_round:
                all_history.extend([
                    {"role": "assistant", "ai_name": resp['name'], "content": resp['response']} 
                    for resp in round_obj.get('responses', [])
                ])

        # 收集本轮所有AI的回复
        responses = []
        for ai in data:
            if ai['id'] not in state['activeAIs']:
                continue
            ai_name = state['player_map'][ai['id']]
            print(f"[阶段提示] AI {ai_name} (ID: {ai['id']}) 开始发言")
            try:
                response = call_api(
                    ai, 
                    f"现在是第{current_round}轮发言，请继续发言，记住要回应其他人的话题。", 
                    is_your_turn=True,
                    all_messages=all_history,
                    ai_name=ai_name,
                )
                responses.append({
                    "ai_id": ai["id"],
                    "name": ai_name,
                    "response": response
                })
                print(f"[阶段提示] AI {ai_name} 发言完成")
                
                # 记录AI消息
                if not ai.get('messages'):
                    ai['messages'] = []
                if not ai['messages'] or ai['messages'][-1]['content'] != response:
                    ai['messages'].append({
                        "role": "assistant",
                        "ai_name": ai_name,
                        "content": response
                    })
            except Exception as e:
                print(f"[错误] AI {ai_name} 发言失败: {str(e)}")
                return jsonify({"error": f"AI {ai_name} 响应错误: {str(e)}"}), 500

        # 更新游戏状态
        current_round_history['responses'] = responses
        save_data(data)
        save_game_state(state)
        print(f"[阶段提示] 第{current_round}轮发言阶段结束，等待进入投票阶段")

        return jsonify({
            "responses": responses,
            "round": current_round,
            "player_map": state['player_map'],
            "votes": [],
            "eliminated": None,
            "winner": None,
            "is_vote_stage": False,
            "has_next_round": True
        })

@api_bp.route('/get_game_state', methods=['GET'])
def get_game_state():
    state = load_game_state()
    return jsonify(state or {})

@api_bp.route('/step_round', methods=['POST','GET'])
def step_round():
    """
    分步推进接口：每次只推进一个AI的发言或投票。
    前端需传递参数：
      - stage: 'speak' 或 'vote'
      - ai_index: 当前activeAIs中的索引（int）
    返回：
      - 当前AI发言/投票内容
      - 阶段、AI名、AI编号、轮次、是否阶段结束、是否游戏结束等
    """
    data = load_data()
    state = load_game_state()
    if not state or not state.get('activeAIs'):
        print("[分步推进] 未找到活跃AI或未开始游戏")
        return jsonify({"error": "请先开始游戏"}), 400
    if state.get('winner'):
        print(f"[分步推进] 游戏已结束，胜者: {state['winner']}")
        return jsonify({"error": "游戏已结束，胜者: " + state['winner'], "is_game_over": True}), 400
    req = request.get_json(force=True)
    stage = req.get('stage', 'speak')  # 'speak' or 'vote'
    ai_index = int(req.get('ai_index', 0))
    activeAIs = state['activeAIs']
    player_map = state['player_map']
    round_num = state['round']
    # 修正：只要进入发言阶段且还在预检，自动推进到第1轮
    if round_num == 0 and stage == 'speak':
        round_num = 1
        state['round'] = 1
        save_game_state(state)
    # 组装历史
    all_history = []
    for round_obj in state['history']:
        if round_obj['round'] < round_num:
            all_history.extend([
                {"role": "assistant", "ai_name": resp['name'], "content": resp['response']} for resp in round_obj['responses']
            ])
    # 阶段推进
    if stage == 'speak':
        if ai_index >= len(activeAIs):
            print(f"[分步推进] 发言阶段结束，轮次：{round_num}")
            return jsonify({"error": "发言阶段已全部完成", "is_stage_end": True, "stage": "speak", "round": round_num})
        ai_id = activeAIs[ai_index]
        ai = next((a for a in data if a['id'] == ai_id), None)
        ai_name = player_map[ai_id]
        print(f"[分步推进] 发言开始，AI：{ai_name} (ID: {ai_id})，轮次：{round_num}")
        response = call_api(
            ai, 
            f"第{round_num}轮发言，请继续本轮发言。", 
            is_your_turn=True, 
            all_messages=all_history, 
            ai_name=ai_name
        )
        print(f"[分步推进] 发言结束，AI：{ai_name} (ID: {ai_id})，内容：{response}")
        # 查重写入messages
        if not ai['messages'] or ai['messages'][-1]['content'] != response:
            ai['messages'].append({
                "role": "assistant",
                "ai_name": ai_name,
                "content": response
            })
        save_data(data)
        # 查重写入history
        if not state['history'] or state['history'][-1]['round'] != round_num:
            state['history'].append({"round": round_num, "responses": []})
        if not any(r['ai_id'] == ai_id for r in state['history'][-1]['responses']):
            state['history'][-1]['responses'].append({
                "ai_id": ai_id,
                "name": ai_name,
                "response": response
            })
        save_game_state(state)
        is_stage_end = (ai_index == len(activeAIs) - 1)
        if is_stage_end:
            print(f"[分步推进] 发言阶段全部完成，轮次：{round_num}")
        return jsonify({
            "stage": "speak",
            "ai_index": ai_index,
            "ai_id": ai_id,
            "ai_name": ai_name,
            "round": round_num,
            "response": response,
            "is_stage_end": is_stage_end,
            "is_game_over": False
        })
    elif stage == 'vote':
        # 新增：从state中获取当前投票记录（修复未定义错误）
        votes_step = state.get('votes_step', [])
        
        # 统计有效投票
        valid_votes = [v for v in votes_step if v.get('target_id') != '0']
        
        # 处理同票情况
        from collections import Counter
        # 修正：使用target_id作为计数键（防止字典不可哈希问题）
        vote_targets = [v['target_id'] for v in valid_votes]
        vote_counts = Counter(vote_targets)
        
        # 获取最大票数
        max_votes = max(vote_counts.values(), default=0)
        
        # 找出最高票者
        top_candidates = [k for k,v in vote_counts.items() if v == max_votes]
        
        # 同票或无投票时处理
        if len(top_candidates) > 1 or max_votes == 0:
            # 设置空淘汰者并记录日志
            state['eliminated'].append({
                'round': round_num,
                'ai_id': None,
                'reason': '同票或无人投票' if len(top_candidates) > 1 else '全体弃权'
            })
            # 返回特殊状态码提示前端
            return jsonify({
                **state,
                'skip_elimination': True,
                'message': '本轮投票平局，无人被淘汰'
            })

        # 正常淘汰最高票者
        eliminated = top_candidates[0]
        state['eliminated'].append({
            'round': round_num,
            'ai_id': eliminated
        })
        
        # 修正：每轮投票阶段开始时初始化votes_step
        if ai_index == 0 or 'votes_step' not in state or not isinstance(state['votes_step'], list):
            state['votes_step'] = []
            save_game_state(state)
        if ai_index >= len(activeAIs):
            print(f"[分步推进] 投票阶段结束，轮次：{round_num}")
            # 统计得票
            vote_count = {}
            for v in state['votes_step']:
                if v['target_id'] != '0':
                    vote_count[v['target_id']] = vote_count.get(v['target_id'], 0) + 1
            eliminated = None
            winner = None
            if len(vote_count) > 0:
                max_votes = max(vote_count.values())
                eliminated_ids = [k for k, v in vote_count.items() if v == max_votes]
                eliminated = random.choice(eliminated_ids)
                if eliminated in state['activeAIs']:
                    state['activeAIs'].remove(eliminated)
                    state['eliminated'].append({"round": round_num, "ai_id": eliminated})
                    print(f"[淘汰信息] 本轮淘汰：{player_map.get(eliminated, eliminated)} (AI真实ID: {eliminated})")
            else:
                print("[详细] 本轮无人被淘汰。")
            # 判断胜者或只剩2人提前结束
            if len(state['activeAIs']) == 2:
                for ai_item in data:
                    if ai_item['id'] in state['activeAIs']:
                        ai_item['score'] += 1
                eliminated_ids = [e['ai_id'] for e in state.get('eliminated', [])]
                for ai_item in data:
                    if ai_item['id'] in eliminated_ids:
                        ai_item['score'] -= 1
                state['winner'] = '|'.join(state['activeAIs'])
                winner = state['winner']
                save_data(data)
            elif len(state['activeAIs']) == 1:
                winner = state['activeAIs'][0]
                state['winner'] = winner
                for ai_item in data:
                    if ai_item['id'] == winner:
                        ai_item['score'] += 1
                save_data(data)
            print(f"[胜负信息] 游戏结束，胜者：{player_map.get(winner, winner) if winner else ''} (AI真实ID: {winner if winner else ''})")
            for v in state['votes_step']:
                state['votes'].append(v)
                state['last_vote'][v['voter_id']] = v['target_id']
            state['votes_step'] = []
            save_game_state(state)
            return jsonify({
                "stage": "vote",
                "ai_index": ai_index,
                "ai_id": None,
                "ai_name": None,
                "round": round_num,
                "vote": None,
                "is_stage_end": True,
                "eliminated": eliminated,
                "winner": state.get('winner'),
                "is_game_over": state.get('winner') is not None,
                "player_map": player_map
            })
        ai_id = activeAIs[ai_index]
        ai = next((a for a in data if a['id'] == ai_id), None)
        ai_name = player_map[ai_id]
        print(f"[分步推进] 投票开始，AI：{ai_name} (ID: {ai_id})，轮次：{round_num}")
        # 本轮responses
        if not state['history'] or state['history'][-1]['round'] != round_num:
            print("[分步推进] 投票阶段未找到本轮发言历史")
            return jsonify({"error": "请先完成发言阶段"}), 400
        responses = state['history'][-1]['responses']
        eliminated_ids = [e['ai_id'] for e in state['eliminated']]
        vote_id = call_vote_api(
            ai,
            responses,
            round_num,
            player_map,
            activeAIs,
            eliminated_ids
        )
        if vote_id == str(player_map[ai['id']])[-1]:
            vote_id = '0'
        vote_obj = {
            "round": round_num,
            "voter_id": ai['id'],
            "target_id": get_ai_id_by_player_num(player_map, vote_id, activeAIs) if vote_id != '0' else '0'
        }
        print(f"[分步推进] 投票结束，AI：{ai_name} (ID: {ai_id})，投票对象：{vote_obj['target_id'] if vote_obj['target_id'] != '0' else '弃权'}")
        # 初始化 votes_step
        if 'votes_step' not in state or not isinstance(state['votes_step'], list):
            state['votes_step'] = []
        state['votes_step'].append(vote_obj)
        save_game_state(state)
        is_stage_end = (ai_index == len(activeAIs) - 1)
        eliminated = None
        winner = None
        # 结算逻辑已在ai_index>=len(activeAIs)时处理
        if is_stage_end:
            print(f"[分步推进] 投票阶段全部完成，轮次：{round_num}")
        return jsonify({
            "stage": "vote",
            "ai_index": ai_index,
            "ai_id": ai_id,
            "ai_name": ai_name,
            "round": round_num,
            "vote": vote_obj,
            "is_stage_end": is_stage_end,
            "eliminated": eliminated,
            "winner": state.get('winner'),
            "is_game_over": state.get('winner') is not None,
            "player_map": player_map
        })
    else:
        print(f"[分步推进] 未知阶段: {stage}")
        return jsonify({"error": "未知阶段"}), 400

def get_ai_id_by_player_num(player_map, num, activeAIs):
    for k, v in player_map.items():
        if v.endswith(str(num)) and k in activeAIs:
            return k
    return '0'