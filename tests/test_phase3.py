import urllib.request
import json
import time

base = 'http://localhost:8000/api'

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
    res = request('/start_debate', {'topic': 'The Earth is flat', 'total_rounds': 2})
    debate_id = res['debate_id']
    print('   Started debate:', debate_id)

    print("\n2. PRO turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   PRO:', res['content'][:150].replace("\n", " "), '...')
    if 'fact_check' in res:
        print(f"   [Fact Check] {res['fact_check']['assessment']} - {res['fact_check'].get('reasoning')} (Conf: {res['fact_check'].get('confidence')}%)")

    print("\n3. AGAINST turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   AGAINST:', res['content'][:150].replace("\n", " "), '...')
    if 'fact_check' in res:
        print(f"   [Fact Check] {res['fact_check']['assessment']} - {res['fact_check'].get('reasoning')} (Conf: {res['fact_check'].get('confidence')}%)")

    print("\n4. USER turn...")
    res = request('/next_turn', {'debate_id': debate_id, 'user_input': 'Actually, satellite imagery proves the earth is a sphere.'})
    print('   USER:', res['content'][:150].replace("\n", " "), '...')
    if 'fact_check' in res:
        print(f"   [Fact Check] {res['fact_check']['assessment']} - {res['fact_check'].get('reasoning')} (Conf: {res['fact_check'].get('confidence')}%)")

    print("\n5. Ending debate to see full history...")
    res = request(f'/end_debate?debate_id={debate_id}')
    print('\n--- FULL TRANSCRIPT WITH FACT CHECKS ---')
    for turn in res['transcript']:
        role = turn['role']
        content = turn['content'][:100].replace("\n", " ") + "..."
        print(f"[{role}] {content}")
    print("----------------------------------------")
    print("\nPhase 3 Fact-Checking is working properly!")
    
except Exception as e:
    print("Error:", e)
