import urllib.request
import json

data = urllib.request.urlopen('http://127.0.0.1:8000/api/state').read()
state = json.loads(data)

print('Pico connected:', state['pico']['connected'])
print('Temperature:', state['pico']['temperature_c'])
print('Humidity:', state['pico']['humidity'])
print('Distance:', state['pico']['distance_cm'])
print('Armed:', state['pico']['armed'])
print('Alarm:', state['pico']['alarm'])
print('\nRecent logs:')
for log in state['logs'][:5]:
    print(f"  {log['time']} [{log['tone']}] {log['message']}")
