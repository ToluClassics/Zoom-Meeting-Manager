import datetime
import json
import os
from zoomus import ZoomClient


API_KEY = os.environ.get('API_KEY')
API_SECRET = os.environ.get('API_SECRET')
EMAIL_ADDRESS = os.environ.get('USER_EMAIL')

client = ZoomClient(API_KEY,API_SECRET)

response = client.user.get(id="ogundepoodunayo@gmail.com")

if response.status_code == 200:
    Print("The API Credentials are valid")
else:
    Print("The API Credentials are invalid")
