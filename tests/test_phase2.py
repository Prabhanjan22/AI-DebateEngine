import urllib.request
import json
import time

base = 'http://localhost:8000'

def request(endpoint, payload=None):
    url = base + endpoint
    if payload:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    else:
        req = urllib.request.Request(url)
    res = urllib.request.urlopen(req).read()
    return json.loads(res)

try:
    print("1. Starting debate...")
    res = request('/start_debate', {'topic': 'Remote work is better than office work', 'total_rounds': 2})
    debate_id = res['debate_id']
    print('   Started debate:', debate_id)

    print("2. PRO turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   PRO:', res['content'][:100].replace("\n", " "), '...')

    print("3. AGAINST turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   AGAINST:', res['content'][:100].replace("\n", " "), '...')

    print("4. USER turn...")
    res = request('/next_turn', {'debate_id': debate_id, 'user_input': 'I think hybrid is best.'})
    print('   USER:', res['content'][:100].replace("\n", " "), '...')

    print("5. Checking memory...")
    res = request(f'/memory?debate_id={debate_id}')
    print('\n--- MEMORY STATUS ---')
    for agent in res['agents']:
        print(f"[{agent['name']}] Own: {agent['own_arguments_count']}, Opponent: {agent['opponent_arguments_count']}")
    print(f"Total turns logged: {res['total_turns_recorded']}")
    print("---------------------")
    print("Memory API is working properly!")
    
except Exception as e:
    print("Error:", e)
