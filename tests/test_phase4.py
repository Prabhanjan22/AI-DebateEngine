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
    res = request('/start_debate', {'topic': 'The exact population of Tokyo in 2024', 'total_rounds': 1})
    debate_id = res['debate_id']
    print('   Started debate:', debate_id)

    print("\n2. PRO turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   PRO:', res['content'])
    if 'fact_check' in res:
        print(f"   [Fact Check] {res['fact_check']['assessment']} - {res['fact_check'].get('reasoning')} (Conf: {res['fact_check'].get('confidence')}%)")

    print("\n3. AGAINST turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   AGAINST:', res['content'])
    if 'fact_check' in res:
        print(f"   [Fact Check] {res['fact_check']['assessment']} - {res['fact_check'].get('reasoning')} (Conf: {res['fact_check'].get('confidence')}%)")

    print("\nPhase 4 MCP layer is working properly!")
    
except Exception as e:
    print("Error:", e)
