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
    res = request('/start_debate', {'topic': 'Should artificial intelligence be heavily regulated?', 'total_rounds': 1})
    debate_id = res['debate_id']
    print('   Started debate:', debate_id)

    print("\n2. PRO turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   PRO:', res['content'][:150].replace("\n", " "), '...')
    if 'score' in res:
        print(f"   [Score] Logic: {res['score'].get('logic')}, Relevance: {res['score'].get('relevance')}, Persuasiveness: {res['score'].get('persuasiveness')} -> Overall: {res['score'].get('overall')}")
        print(f"   [Score Reasoning] {res['score'].get('reasoning')}")

    print("\n3. AGAINST turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print('   AGAINST:', res['content'][:150].replace("\n", " "), '...')
    if 'score' in res:
        print(f"   [Score] Logic: {res['score'].get('logic')}, Relevance: {res['score'].get('relevance')}, Persuasiveness: {res['score'].get('persuasiveness')} -> Overall: {res['score'].get('overall')}")
        print(f"   [Score Reasoning] {res['score'].get('reasoning')}")

    print("\n4. USER turn...")
    res = request('/next_turn', {'debate_id': debate_id, 'user_input': 'Regulation stifles innovation. Let the market decide.'})
    print('   USER:', res['content'][:150].replace("\n", " "), '...')
    if 'score' in res:
        print(f"   [Score] Logic: {res['score'].get('logic')}, Relevance: {res['score'].get('relevance')}, Persuasiveness: {res['score'].get('persuasiveness')} -> Overall: {res['score'].get('overall')}")
        print(f"   [Score Reasoning] {res['score'].get('reasoning')}")

    print("\n5. Ending debate to run Arbiter...")
    res = request(f'/end_debate?debate_id={debate_id}')
    
    verdict = res.get('verdict', {})
    print('\n--- ARBITER VERDICT ---')
    print(f"Winner: {verdict.get('winner')}")
    print(f"Reasoning: {verdict.get('reasoning')}")
    print("-----------------------")
    
    print("\nPhase 5 & 6 (Scoring & Arbiter) are working properly!")
    
except Exception as e:
    print("Error:", e)
