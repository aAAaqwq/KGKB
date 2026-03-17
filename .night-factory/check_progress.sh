#!/bin/bash
# KGKB Night Factory - Progress Tracker
# Reads task file and returns next uncompleted task info

TASK_FILE="/home/aa/clawd/projects/knowledge-graph-kb/.night-factory/tasks.json"

# Get completed count
COMPLETED=$(python3 -c "
import json
with open('$TASK_FILE') as f:
    data = json.load(f)
done = sum(1 for t in data['tasks'] if t['done'])
total = len(data['tasks'])
print(f'{done}/{total}')
")

# Get next task
NEXT=$(python3 -c "
import json
with open('$TASK_FILE') as f:
    data = json.load(f)
for t in data['tasks']:
    if not t['done']:
        print(f\"Task {t['id']}: [{t['phase']}] {t['title']}\")
        print(f\"Description: {t['description']}\")
        print(f\"Files: {', '.join(t['files'])}\")
        break
else:
    print('ALL_DONE')
")

echo "Progress: $COMPLETED"
echo "---"
echo "$NEXT"
