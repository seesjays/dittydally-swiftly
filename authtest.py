import requests
import os
from dotenv import load_dotenv

# TempAuth test, should eventually move to Keystone

load_dotenv()

SWIFT_AUTH_URL = os.environ.get("ST_AUTH")
SWIFT_USER = os.environ.get("ST_USER")
SWIFT_KEY = os.environ.get("ST_KEY")

def get_auth_token():
    headers = {"X-Auth-User": SWIFT_USER, "X-Auth-Key": SWIFT_KEY}
    response = requests.get(SWIFT_AUTH_URL, headers=headers)

    if response.status_code == 200:
        return response.headers["X-Auth-Token"], response.headers["X-Storage-Url"]
    else:
        raise Exception(
            f"Failed to authenticate with Swift. {response.status_code}: {response.text}"
        )

token, storage_url = get_auth_token()
print(f"Auth Token: {token}")
print(f"Storage URL: {storage_url}")
