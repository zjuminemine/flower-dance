import requests
import json

# 第一次上传
text1 = '我最近工作压力很大，经常加班到凌晨。和男朋友也吵了一架，他觉得我总是把工作放在第一位。我开始怀疑自己是不是太把工作当回事了，但另一方面又觉得现在正是事业的上升期，不能松懈。'
r1 = requests.post('http://localhost:8000/api/upload-content', data={'text': text1}, timeout=120)
data1 = r1.json()
print('第一次分类:', data1['involved_categories'])
for s in data1['suggestions']:
    print(f"  [{s['category']}] {s['type']}: {s['proposed_text']}")

# 确认所有建议
confirm_payload = {'decisions': []}
for sug in data1['suggestions']:
    confirm_payload['decisions'].append({
        'type': sug['type'],
        'category': sug['category'],
        'card_id': sug.get('card_id'),
        'accepted': True,
        'text': sug['proposed_text'],
        'source_ids': sug.get('source_ids', []),
        'facts': sug.get('facts', [])
    })

r_confirm = requests.post('http://localhost:8000/api/confirm-cards', json=confirm_payload, timeout=120)
print('\n确认结果:', r_confirm.json())

# 查看卡片
r_cards = requests.get('http://localhost:8000/api/cards', timeout=120)
print('\n当前卡片数量:')
for k, v in r_cards.json()['categories'].items():
    if v:
        print(f"  {k}: {len(v)} 张")

# 第二次上传
text2 = '昨天和领导提了离职的想法，他挽留我，说下个月给我升职。我犹豫了，一方面舍不得这个机会，另一方面又觉得太累了，想休息一段时间。'
r2 = requests.post('http://localhost:8000/api/upload-content', data={'text': text2}, timeout=120)
data2 = r2.json()
print('\n第二次分类:', data2['involved_categories'])
for s in data2['suggestions']:
    print(f"  [{s['category']}] {s['type']}: {s['proposed_text']}")
    if 'old_text' in s:
        print(f"    原来: {s['old_text']}")
