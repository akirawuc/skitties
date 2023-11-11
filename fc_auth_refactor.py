import os
import time
import requests
import logging
from eth_account import Account
from nacl.signing import SigningKey
from eth_account.messages import encode_structured_data
from dotenv import load_dotenv

# Constants
POLL_TRIES = 40
SLEEP_INTERVAL = 2  # seconds
DEADLINE_OFFSET = 86400  # 1 day in seconds
WARPCAST_API = os.environ.get("WARPCAST_API", "https://api.warpcast.com")

# Setup logging
logging.basicConfig(level=logging.INFO)

load_dotenv()

APP_MNEMONIC = os.environ.get("APP_MNEMONIC")
APP_FID = os.environ.get("APP_FID")

def fetch_json(url: str, method: str = 'GET', headers: dict = None, data: dict = None) -> dict:
    """
    Handle HTTP requests and return JSON response.
    """
    try:
        response = requests.request(method, url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Request failed: {e}")
        return {}

def poll_for_signer(token: str) -> None:
    """
    Poll for signer status.
    """
    for _ in range(POLL_TRIES):
        time.sleep(SLEEP_INTERVAL)
        response = fetch_json(f'{WARPCAST_API}/v2/signed-key-request?token={token}')
        logging.info(response)
        state = response.get('result', {}).get('signedKeyRequest', {}).get('state')

        if state == 'completed':
            return

def send_warpcast_request(public_key, fid, signature, deadline) -> tuple:
    """
    Send a request to Warpcast API.
    """
    headers = {'Content-Type': 'application/json'}
    data = {
        "key": f'0x{public_key.hex()}',
        "requestFid": int(fid),
        "signature": signature,
        "deadline": deadline,
    }

    response = requests.post(f"{WARPCAST_API}/v2/signed-key-requests", json=data, headers=headers)
    response.raise_for_status()
    result = response.json().get('result', {}).get('signedKeyRequest', {})
    logging.info(result)
    token = result.get('token')
    deeplinkUrl = result.get('deeplinkUrl')
    logging.info(deeplinkUrl)
    poll_for_signer(token)
    return token, deeplinkUrl

def signer_pub(signer25519) -> bytes:
    """
    Get public key from signer.
    """
    return signer25519.verify_key.encode()

def main():
    """
    Main function to execute the script logic.
    """
    signer = Account.create()
    signer25519 = SigningKey(signer.key)
    key = signer.key
    signer_priv = signer25519.encode()

    signer_public_key = signer_pub(signer25519)

    print(signer_priv)
    print(signer_priv.hex())
    print(key.hex())
    print(signer_public_key.hex())
    print(signer_public_key.hex())
    print(signer_public_key.hex())
    print(signer_public_key.hex())
    print(key.hex())

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
    deadline = int(time.time()) + DEADLINE_OFFSET

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
                'key':  signer_public_key,
                'deadline': deadline,
            },
            'primaryType': "SignedKeyRequest",
        }
    encoded_message = encode_structured_data(data)
    signature = str(account.sign_message(encoded_message).signature.hex())
    logging.info(signature)
    send_warpcast_request(signer_public_key, APP_FID, signature, deadline)
if __name__ == '__main__':
    main()
