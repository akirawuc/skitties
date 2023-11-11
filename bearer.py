import os
from farcaster import Warpcast
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

def gen_bearer():
    APP_MNEMONIC = os.environ.get("APP_MNEMONIC")
    APP_FID = os.environ.get("APP_FID")

    client = Warpcast(mnemonic=APP_MNEMONIC)
    return client.create_new_auth_token(expires_in=10)

print(client.get_healthcheck())

print(client.create_new_auth_token(expires_in=10))