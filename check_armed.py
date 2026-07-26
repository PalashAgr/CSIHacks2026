import urllib.request
import json

data = urllib.request.urlopen('http://127.0.0.1:8000/api/state').read()
state = json.loads(data)

print('Armed:', state['pico']['armed'])
print('Alarm:', state['pico']['alarm'])
print('Recent logs:')
for log in state['logs'][:10]:
    print(f"  {log['time']} [{log['tone']}] {log['message']}")
