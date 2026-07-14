import json
import sys
sys.path.insert(0, 'backend')
import main as m

# 注入用户提供的测试卡片
m.cards['osmanthus'] = [{
    'id': 'test_os_001',
    'card_text': '你在考虑职业变动时，对投资回报率分析有明确需求',
    'category': 'osmanthus',
    'created_at': '2024-01-01T00:00:00',
    'updated_at': '2024-01-01T00:00:00',
    'source_ids': [],
    'facts': []
}]
m.cards['narcissus'] = [{
    'id': 'test_na_001',
    'card_text': '你在面对挫折时能够迅速将情绪转化为动力，并设定新目标，这种快速适应和自我激励的能力显示出你强大的心理韧性',
    'category': 'narcissus',
    'created_at': '2024-01-01T00:00:00',
    'updated_at': '2024-01-01T00:00:00',
    'source_ids': [],
    'facts': []
}]

question = '我最近要不要换工作？'
referenced = [m.cards['osmanthus'][0], m.cards['narcissus'][0]]

prompt = m.build_chat_prompt(question, referenced)
print('=== 构建的提示词 ===')
print(prompt)
print('\n=== LLM 回答 ===')
try:
    result = m.call_llm_text(
        user_prompt=prompt,
        system_prompt=m.CHAT_SYSTEM_PROMPT,
    )
    answer = result.get('answer', '').strip()
    violations = m.detect_chat_forbidden_words(answer)
    if violations:
        print(f'首次回答含禁用词: {violations}，正在重试...')
        cards_summary = "\n".join(
            f"- {m.FLOWER_CATEGORIES.get(card.get('category', ''), {}).get('name', card.get('category', ''))}：{m.clean_card_text_for_chat(card.get('card_text', ''))}"
            for card in referenced
        )
        retry_prompt = (
            "请用完全不同的表达方式重写下面这段回答，严格避免出现抽象评价词。\n\n"
            f"原文：{answer}\n\n"
            "【必须基于的认知卡片】\n"
            f"{cards_summary}\n\n"
            "【重写要求】\n"
            "1. 用具体动作和情境描述卡片内容，例如「你会先算投入产出」「你遇到挫折会把情绪转成新目标」。\n"
            "2. 把多张卡片放在一起综合分析，说明它们之间的关系。\n"
            "3. 最后给出「如果……就……；否则/反之……」形式的具体建议。\n"
            "4. 禁止出现：展现出、显示出、反映出、体现出、说明了、表明、深思熟虑、值得考虑、可以想想等抽象或套话表达；可用「意味着」「放在一起看」替代。\n"
            f'5. 返回严格合法 JSON：{{"answer": "重写后的回答", "referenced_cards": {json.dumps([c["id"] for c in referenced], ensure_ascii=False)}}}'
        )
        result = m.call_llm_text(
            user_prompt=retry_prompt,
            system_prompt=m.CHAT_SYSTEM_PROMPT,
        )
        answer = result.get('answer', '').strip()
        violations = m.detect_chat_forbidden_words(answer)
        if violations:
            print(f'重试后仍含禁用词: {violations}')
    answer = m.sanitize_chat_answer(answer)
    print(answer)
    print('引用卡片:', result.get('referenced_cards'))
except Exception as e:
    print('调用失败:', e)
