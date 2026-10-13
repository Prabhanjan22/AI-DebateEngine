"""
tests/test_phase2.py

Tests Phase 2 features:
  - Debate session creation and turn execution
  - RAG trace endpoint (replaces the old /memory endpoint)
  - Analytics endpoint showing persisted debate records
  - History endpoint showing completed debates
"""

import urllib.request
import json

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
    res = request('/start_debate', {'topic': 'Remote work is better than office work', 'total_rounds': 1})
    debate_id = res['debate_id']
    print(f"   Started debate: {debate_id}")

    print("2. PRO turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print(f"   PRO: {res['content'][:100].replace(chr(10), ' ')} ...")
    if res.get('score'):
        print(f"   [Score] Overall: {res['score'].get('overall')}/10")

    print("3. AGAINST turn...")
    res = request('/next_turn', {'debate_id': debate_id})
    print(f"   AGAINST: {res['content'][:100].replace(chr(10), ' ')} ...")
    if res.get('score'):
        print(f"   [Score] Overall: {res['score'].get('overall')}/10")

    print("4. USER turn...")
    res = request('/next_turn', {'debate_id': debate_id, 'user_input': 'I think hybrid is best.'})
    print(f"   USER: {res['content'][:100].replace(chr(10), ' ')} ...")

    print("5. Ending debate (triggers Arbiter + persistence)...")
    res = request(f'/end_debate?debate_id={debate_id}')
    verdict = res.get('verdict', {})
    print(f"   Winner: {verdict.get('winner')} | Reasoning: {verdict.get('reasoning', '')[:80]}...")

    print("\n6. Checking RAG trace...")
    res = request(f'/trace?debate_id={debate_id}')
    print(f"   Debate ID: {res['debate_id']}")
    print(f"   Total embedded docs: {res['total_turns_recorded']}")
    if res['docs']:
        print(f"   Sample doc: [{res['docs'][0]['speaker']} R{res['docs'][0]['round_num']}] {res['docs'][0]['raw_content'][:80]}...")

    print("\n7. Checking analytics endpoint...")
    res = request('/analytics')
    print(f"   Total debates persisted: {res['total_debates']}")
    print(f"   Verdict distribution: {res['verdict_distribution']}")
    print(f"   Avg PRO score: {res.get('avg_pro_score')}")
    print(f"   Avg AGAINST score: {res.get('avg_against_score')}")

    print("\n8. Checking history endpoint...")
    res = request('/history?limit=5')
    print(f"   Total saved: {res['total_saved']}, showing: {res['showing']}")
    if res['records']:
        r = res['records'][0]
        print(f"   Latest debate: '{r['topic']}' → Winner: {r['winner']}")

    print("\n✓ Phase 2 (Persistence + RAG + Analytics) is working properly!")

except Exception as e:
    import traceback
    print("Error:", e)
    traceback.print_exc()
