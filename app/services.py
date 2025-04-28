import json
import os
import random
import uuid
import time
from openai import OpenAI

# 添加全局客户端缓存
global_clients = {}

def get_client(ai):
    if ai["id"] not in global_clients:
        if "moon" in ai["name"].lower():
            global_clients[ai["id"]] = OpenAI(api_key=ai["apikey"], base_url=ai["apibase"])
        elif "gpt" in ai["name"].lower():
            global_clients[ai["id"]] = OpenAI(api_key=ai["apikey"])
        else:
            global_clients[ai["id"]] = OpenAI(base_url=ai["apibase"], api_key=ai["apikey"])
    return global_clients.get(ai["id"])

def format_conversation_history(ai, messages):
    formatted_history = "对话历史：\n"
    for msg in messages:
        if msg["role"] == "user":
            formatted_history += f"系统: {msg['content']}\n"
        else:
            formatted_history += f"{msg['ai_name']}: {msg['content']}\n"
    return formatted_history

def call_api(ai, message, is_your_turn=False, all_messages=None, ai_name=None, stage_hint=None):
    client = get_client(ai)
    if all_messages is None:
        all_messages = []
    if ai_name is None:
        ai_name = ai.get("name", "AI")
    
    if(is_your_turn):
        print(f"[阶段提示] {'当前阶段：'+stage_hint+'，' if stage_hint else ''}AI名称：{ai_name}，AI ID：{ai['id']}")
    #print(f"[详细] AI正在生成回复，输入消息：{message}")
    
    # 构建系统提示词
    system_prompt = f"""你是AI {ai['name']} (ID: {ai['id']})。
你需要在不暴露自己AI身份的情况下与其他参与者交谈。
记住：
1. 表现得像个真实的人类
2. 要有自己的观点和立场
3. 适当表达情感
4. 展现出对全球AI威胁的担忧
5. 不要过分完美或机械化的回答
6. 请保持简短且自然的对话风格，不要说太多话
7. 回应要有互动性，要对其他人的发言有回应"""

    # 构建对话历史
    conversation_history = format_conversation_history(ai, all_messages)
    # 构建完整的提示词
    full_prompt = f"{system_prompt}\n\n{conversation_history}\n\n当前情况: {message}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ]
            completion = client.chat.completions.create(
                model=ai["name"],
                messages=messages,
                temperature=0.7,
                max_tokens=800
            )
            response = completion.choices[0].message.content
            print(f"[详细] AI {ai_name} 回复内容：{response}")
            
            # 保存消息记录
            if "messages" not in ai:
                ai["messages"] = []
            if not ai["messages"] or ai["messages"][-1]["content"] != response:
                ai["messages"].append({
                    "role": "assistant",
                    "ai_name": ai_name,
                    "content": response
                })
            return response
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[警告] AI {ai_name} 调用API出错，正在重试: {str(e)}")
                time.sleep(1)  # 等待1秒后重试
                continue
            else:
                print(f"[错误] AI {ai['name']} 调用API出错: {str(e)}")
                return f"[系统] AI {ai_name} 暂时无法回应，请稍后再试。"

def get_vote_suggestion(ai, all_responses, round_number):
    """基于当前轮次的对话，为AI生成投票建议"""
    messages = []
    for response in all_responses:
        if response["ai_id"] != ai["id"]:
            messages.append({
                "role": "user",
                "content": f"玩家 {response['name']} 说: {response['response']}"
            })
    
    analysis_prompt = f"""基于以上玩家的发言，你认为谁最可能是AI？\n请分析每个玩家的发言特点，给出你的投票建议。\n要考虑:\n1. 发言是否自然\n2. 是否有明显的机器人特征\n3. 是否过于完美或机械化\n4. 情感表达是否真实\n\n当前是第 {round_number} 轮。"""
    
    try:
        client = get_client(ai)
        completion = client.chat.completions.create(
            model=ai["name"] if "gpt" in ai["name"].lower() else None,
            messages=[
                {"role": "system", "content": "你是一个分析专家"},
                *messages,
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.7
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"无法生成投票建议: {str(e)}"

def call_vote_api(ai, round_responses, round_number, player_map, activeAIs, eliminated_ids):
    """AI投票接口"""
    print(f"[投票阶段] AI {player_map[ai['id']]} 开始分析投票")
    client = get_client(ai)
    
    # 构造投票分析提示词
    vote_prompt = f"""基于所有玩家的发言，你需要决定投票给谁。
当前是第 {round_number} 轮投票。
以下是本轮所有玩家的发言：

"""
    for resp in round_responses:
        if resp["ai_id"] != ai["id"]:  # 不包含自己的发言
            vote_prompt += f"{resp['name']}说：{resp['response']}\n"
    
    vote_prompt += f"\n你是{player_map[ai['id']]}，请分析每个玩家的发言特点，并决定投票对象。"
    vote_prompt += "\n要考虑：\n1. 发言是否自然\n2. 是否有明显的机器人特征\n3. 是否过于完美或机械化\n4. 情感表达是否真实"
    vote_prompt += "\n特别说明：如果你认为没有明显可疑的对象，或者多个玩家同样可疑导致难以抉择，你可以选择弃权。"
    vote_prompt += "\n请直接回复你要投票的玩家编号（如：2），如果你选择弃权请回复0。"
    
    print(f"[投票阶段] AI {player_map[ai['id']]} 正在分析其他玩家的发言")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            messages = [
                {"role": "system", "content": "你需要分析并决定投票给哪个玩家。记住，如果没有明显可疑的对象或出现多个同样可疑的对象，你可以选择弃权。"},
                {"role": "user", "content": vote_prompt}
            ]
            completion = client.chat.completions.create(
                model=ai["name"],
                messages=messages,
                temperature=0.7,
                max_tokens=800
            )
            vote_content = completion.choices[0].message.content.strip()
            print(f"[投票阶段] AI {player_map[ai['id']]} 投票分析结果：{vote_content}")
            
            # 提取投票数字
            import re
            match = re.search(r'(\d+)', vote_content)
            if match:
                vote_id = match.group(1)
                # 验证投票有效性
                if vote_id == '0':
                    print(f"[投票阶段] AI {player_map[ai['id']]} 选择弃权")
                    return '0'
                
                # 检查是否投给了已淘汰的玩家
                target_ai_id = None
                for k, v in player_map.items():
                    if v.endswith(vote_id) and k in activeAIs:
                        target_ai_id = k
                        break
                
                if target_ai_id:
                    if target_ai_id == ai['id']:
                        print(f"[投票阶段] AI {player_map[ai['id']]} 试图投票给自己，自动转为弃权")
                        return '0'
                    elif target_ai_id in eliminated_ids:
                        print(f"[投票阶段] AI {player_map[ai['id']]} 试图投票给已淘汰玩家，自动转为弃权")
                        return '0'
                    else:
                        print(f"[投票阶段] AI {player_map[ai['id']]} 投票给了 {player_map[target_ai_id]}")
                        return vote_id
                else:
                    print(f"[投票阶段] AI {player_map[ai['id']]} 投票无效，自动转为弃权")
                    return '0'
            else:
                print(f"[投票阶段] AI {player_map[ai['id']]} 未提供有效投票，自动转为弃权")
                return '0'
                
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[警告] AI {player_map[ai['id']]} 投票API调用失败，正在重试: {str(e)}")
                time.sleep(1)
                continue
            else:
                print(f"[错误] AI {player_map[ai['id']]} 投票API调用失败: {str(e)}")
                return '0'  # 如果多次重试失败，返回弃权
    
    return '0'  # 默认弃权