import os
import time
from eth_account import Account
from nacl.signing import SigningKey
from mnemonic import Mnemonic
import json
import requests
from time import sleep
#from web3.auto import w3
from eth_account.messages import encode_typed_data, encode_structured_data

import os
from farcaster import Warpcast
from dotenv import load_dotenv
import pandas as pd

from eth_keys import keys
from eth_account import Account
import eth_utils

load_dotenv()


APP_MNEMONIC = os.environ.get("APP_MNEMONIC")
APP_FID = os.environ.get("APP_FID")

def fetch_json(url, method='GET', headers=None, data=None):
    # This function will handle the HTTP requests
    response = requests.request(method, url, headers=headers, json=data)
    return response.json()


def poll_for_signer(token):
    tries = 0
    while tries < 40:
        tries += 1
        sleep(2)  # Wait for 2 seconds

        response = fetch_json(f'https://api.warpcast.com/v2/signed-key-request?token={token}')
        print(response)
        state = response.get('result', {}).get('signedKeyRequest', {}).get('state')

        if state == 'completed':
            break

def send_warpcast_request(public_key, fid, signature, deadline):
    warpcast_api = "https://api.warpcast.com"

    # Prepare the headers with the bearer token
    headers = {
        'Content-Type': 'application/json',
    }

    # Data to be sent in the POST request
    data = {
        "key": public_key.hex(),
        "requestFid": int(fid),
        "signature": signature,
        "deadline": deadline,
    }

    # Make the POST request
    response = requests.post(f"{warpcast_api}/v2/signed-key-requests", json=data, headers=headers)

    # Extract the token and deeplinkUrl from the response
    if response.status_code == 200:
        result = response.json().get('result', {}).get('signedKeyRequest', {})
        print(result)
        token = result.get('token')
        deeplinkUrl = result.get('deeplinkUrl')
        print(deeplinkUrl)
        poll_for_signer(token)
    else:
        print(f"Error: {response.status_code}")
        return None, None

def signer_pub(signer25519):
    return signer25519.verify_key.encode()

if __name__ == '__main__':
    signer = Account.create()
    signer25519 = SigningKey(signer.key)
    key = signer.key

    # EIP-712 helper code
    SIGNED_KEY_REQUEST_VALIDATOR_EIP_712_DOMAIN = {
      'name': "Farcaster SignedKeyRequestValidator",
      'version': "1",
      'chainId': 10,
      'verifyingContract': "0x00000000fc700472606ed4fa22623acf62c60553"
    }

    signer_public_key = signer_pub(signer25519)
    Account.enable_unaudited_hdwallet_features()
    account = Account.from_mnemonic(APP_MNEMONIC)
    deadline = int(time.time()) + 86400  # signature is valid for 1 day

    data = {
            'domain': SIGNED_KEY_REQUEST_VALIDATOR_EIP_712_DOMAIN,
            'types': {
                'SignedKeyRequest': [
                    {'name': "requestFid", 'type': "uint256"},
                    {'name': "key", 'type': "bytes"},
                    {'name': "deadline", 'type': "uint256"},
                ],
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
                ],
            },
            'message': {
                'requestFid': int(APP_FID),
                'key': key,
                'deadline': deadline,
            },
            'primaryType': "SignedKeyRequest",
        }
    encoded_message = encode_structured_data(data)
    # Sign the message
    # signature = str(account.sign_message(encoded_message).signature.hex())
    signature = str(account.sign_message(encoded_message).signature.hex())
    print(signature)
    send_warpcast_request(key, APP_FID, signature, deadline)
