import requests

url = 'https://commtech.byu.edu/noauth/classSchedule/ajax/getClasses.php'

headers = {}

data = {
    'searchObject[teaching_areas][]': ['C S'],
    'searchObject[yearterm]': 20251,
    'sessionId': '12345'
}

response = requests.post(url, headers=headers, data=data)

print(response.text)
