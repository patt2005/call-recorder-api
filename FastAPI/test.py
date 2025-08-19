import requests
url = "http://0.0.0.0:8000/predict"

userdata = {
  "sentsent": "wow amazing"
}

ans = requests.post(url, json=userdata)
print(ans.text)
