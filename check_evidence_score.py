import json

with open('/mnt/d/ZYY Project/Phoenix-Evo/skills/skill_index.json') as f:
    idx = json.load(f)

active = [(sid, e) for sid, e in idx.items() if e.get('status') == 'active']
missing = [(sid, e.get('evidence_score')) for sid, e in active if e.get('evidence_score') is None]

print(f'Total active: {len(active)}, Missing evidence_score: {len(missing)}')
print()
print('=== Active skills with evidence_score ===')
for sid, e in active:
    score = e.get('evidence_score', 'MISSING')
    print(f'  {sid}: {score}')

print()
print('=== MISSING evidence_score entries ===')
for sid, val in missing:
    print(f'  MISSING: {sid} = {val}')