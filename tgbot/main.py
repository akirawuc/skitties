import os
from eth_account.messages import encode_defunct
from eth_account import Account
import json
import time
from eth_account import Account
from mnemonic import Mnemonic
import json
import requests
from time import sleep
from web3.auto import w3
from eth_account.messages import encode_defunct


def generate_key_pair():
    # In Python, you would use the web3.py library to generate keys
    Account.enable_unaudited_hdwallet_features()
    acct, mnemonic = Account.create_with_mnemonic()
    print(acct.address)
    return {
        'publicKey': acct.address,
        'privateKey': mnemonic
    }


def fetch_json(url, method='GET', headers=None, data=None):
    # This function will handle the HTTP requests
    response = requests.request(method, url, headers=headers, json=data)
    return response.json()

def initiate_signer_request(public_key, request_fid, signature, deadline):
    # Get app signature
    signed_key_response = fetch_json(
        'https://api.warpcast.com/v2/signed-key-requests',
        method='POST',
        headers={'Content-Type': 'application/json'},
        data={
            'key': f'0x{public_key}',
            'signature': signature,
            'requestFid': request_fid,
            'deadline': deadline
        }
    )
    print(signed_key_response)

    signed_key_result = signed_key_response.get('result')
    if not signed_key_result:
        print('Error generating signed key')
        return

    token = signed_key_result['signedKeyRequest']['token']
    deeplink_url = signed_key_result['signedKeyRequest']['deeplinkUrl']
    print(deeplink_url)

    poll_for_signer(token)

    # Here you would handle the response and the next steps accordingly
    # ...

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
        'Authorization': f'Bearer MK-FLFcFFzH3oVfNzSChbG/XAhteDvBYvp9nGjKrGeQxrQQKAmEohKvS9Ds/MaNjxE2cuhdRhnRCraiOs11Wmp/MQ==',
        'Content-Type': 'application/json',
    }

    # Data to be sent in the POST request
    data = {
        "key": public_key,
        "requestFid": fid,
        "signature": signature,
        "deadline": deadline,
    }

    # Make the POST request
    response = requests.post(f"{warpcast_api}/v2/signed-key-requests", json=data, headers=headers)

    # Extract the token and deeplinkUrl from the response
    if response.status_code == 200:
        result = response.json().get('result', {}).get('signedKeyRequest', {})
        token = result.get('token')
        deeplinkUrl = result.get('deeplinkUrl')
        print(deeplinkUrl)
        poll_for_signer(token)
    else:
        print(f"Error: {response.status_code}")
        return None, None


if __name__ == '__main__':
    keys = generate_key_pair()
    # EIP-712 helper code
    SIGNED_KEY_REQUEST_VALIDATOR_EIP_712_DOMAIN = {
      'name': "Farcaster SignedKeyRequestValidator",
      'version': "1",
      'chainId': 10,
      'verifyingContract': "0x00000000fc700472606ed4fa22623acf62c60553"
    }

    SIGNED_KEY_REQUEST_TYPE = [
      {'name': "requestFid", 'type': "uint256"},
      {'name': "key", 'type': "bytes"},
      {'name': "deadline", 'type': "uint256"},
    ]

    # Generating a keypair
    key = keys['publicKey']
    mnemonic = keys['privateKey']

    # Generating a Signed Key Request signature
    app_fid = 20818
    Account.enable_unaudited_hdwallet_features()
    account = Account.from_mnemonic(mnemonic)
    deadline = int(time.time()) + 86400  # signature is valid for 1 day

    # Prepare the message for signing
    message = {
        'requestFid': int(app_fid),
        'key': key,
        'deadline': deadline,
    }
    # Convert the message to an EIP-712 compatible format
    encoded_message = encode_defunct(text=json.dumps(message))

    # Sign the message
    signature = str(account.sign_message(encoded_message).signature.hex())
    send_warpcast_request(key, app_fid, signature, deadline)

