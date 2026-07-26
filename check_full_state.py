import urllib.request
import json

data = urllib.request.urlopen('http://127.0.0.1:8000/api/state').read()
state = json.loads(data)

print('=== PICO STATE ===')
print('Connected:', state['pico']['connected'])
print('Armed:', state['pico']['armed'])
print('Alarm:', state['pico']['alarm'])
print('Alarm reason:', state['pico']['alarm_reason'])
print('Remote alarm:', state['pico'].get('remote_alarm', False))

print('\n=== ALARM STATE ===')
print('Active:', state['alarm']['active'])
print('Reason:', state['alarm']['reason'])
print('Source:', state['alarm']['source'])

print('\n=== SENSOR DATA ===')
print('Temperature:', state['pico']['temperature_c'])
print('Humidity:', state['pico']['humidity'])
print('Distance:', state['pico']['distance_cm'])

print('\n=== RECENT LOGS ===')
for log in state['logs'][:15]:
    print(f"  {log['time']} [{log['tone']}] {log['message']}")
