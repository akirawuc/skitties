import os
import qrcode
import os
import time
import requests
import asyncio
from telegram.constants import ParseMode
import logging
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import Update
import os
import sqlite3
from eth_account import Account
from nacl.signing import SigningKey
from eth_account.messages import encode_structured_data
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, filters
import sqlite3
import time
import requests
import logging
from eth_account import Account
from nacl.signing import SigningKey
from eth_account.messages import encode_structured_data
from dotenv import load_dotenv
import os
from dotenv import load_dotenv
from farcaster.HubService import HubService
from farcaster.fcproto.message_pb2 import SignatureScheme, HashScheme, Embed
from farcaster import Message

load_dotenv()
hub_address = os.getenv("FARCASTER_HUB")
def send_cast(hub_addr, app_signer, user_fid):
    hub = HubService(hub_address, use_async=False)
    message_builder = Message.MessageBuilder(
        HashScheme.HASH_SCHEME_BLAKE3, SignatureScheme.SIGNATURE_SCHEME_ED25519,
        bytes.fromhex(app_signer[2:]))

    # add(self, fid, text, mentions=[], mentions_positions=[], embeds=[]) -> MessageData:
    data = message_builder.cast.add(
        fid=user_fid, text="Skitties skitties")
    msg = message_builder.message(data)

    ret = hub.SubmitMessage(msg)
    print("Message posted!")
    print(ret)
    return ret

# Constants
POLL_TRIES = 10
SLEEP_INTERVAL = 3  # seconds
DEADLINE_OFFSET = 86400  # 1 day in seconds
WARPCAST_API = os.environ.get("WARPCAST_API", "https://api.warpcast.com")
BOT_TOKEN = os.environ.get("MOCK_BOT_TOKEN")

# Setup logging
logging.basicConfig(level=logging.INFO)


APP_MNEMONIC = os.environ.get("APP_MNEMONIC")
APP_FID = os.environ.get("APP_FID")

def initialize_db():
    """
    Initialize the database by creating necessary tables.
    """
    with sqlite3.connect('bot_users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_keypairss (
            user_id INTEGER PRIMARY KEY,
            public_key TEXT NOT NULL,
            user_fid INTEGER NOT NULL
        )
        ''')
        conn.commit()

def store_keypair(user_id, public_key, user_fid):
    """
    Store a new keypair for a user along with the userFid.
    """
    with sqlite3.connect('bot_users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO user_keypairss (user_id, public_key, user_fid) VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
        public_key=excluded.public_key,
        user_fid=excluded.user_fid
        ''', (user_id, public_key, user_fid))
        conn.commit()


def generate_qr_code(link):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(f"deep_link_qr_{link.split('/')[-1]}.png")
    return f"deep_link_qr_{link.split('/')[-1]}.png"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    print(Update.message)
    print(context)
    print(context.bot)
    url = "https://api.warpcast.com/v2/login"
    chat_id = update.effective_chat.id
    img = generate_qr_code("https://www.google.com")  # Replace with your deep link
    await bot.send_photo(chat_id=chat_id, photo=open(img, 'rb'))
    text = "scan it to login"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def poll_for_signer_async(token: str, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    Asynchronously poll for signer status and notify the user.
    """
    for _ in range(POLL_TRIES):
        await asyncio.sleep(SLEEP_INTERVAL)
        response = fetch_json(f'{WARPCAST_API}/v2/signed-key-request?token={token}')
        state = response.get('result', {}).get('signedKeyRequest', {}).get('state')

        if state == 'completed':
            user_fid = response.get('result', {}).get('signedKeyRequest', {}).get('userFid')
            public_key = response.get('result', {}).get('signedKeyRequest', {}).get('key')
            store_keypair(chat_id, public_key, user_fid)
            await context.bot.send_message(chat_id=chat_id, text="Login completed successfully.")
            return
    await context.bot.send_message(chat_id=chat_id, text="Login process timed out or failed.")


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat_id = update.effective_chat.id
    print(chat_id)
    print(update.effective_chat.id)
    token, deeplinkUrl = main()
    img = generate_qr_code(deeplinkUrl) 
    await bot.send_photo(chat_id=chat_id, photo=open(img, 'rb'))
    await poll_for_signer_async(token, context, chat_id)


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

def retrieve_keypair_as_dict(user_id):
    """
    Retrieve a keypair for a user and return it as a dictionary.
    """
    with sqlite3.connect('bot_users.db') as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT public_key, user_fid FROM user_keypairss WHERE user_id=?', (user_id,))
        result = cursor.fetchone()
    if result:
        keys = ['public_key', 'user_fid']
        return dict(zip(keys, result))
    else:
        return None


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

    try:
        response = requests.post(f"{WARPCAST_API}/v2/signed-key-requests", json=data, headers=headers)
        response.raise_for_status()
        result = response.json().get('result', {}).get('signedKeyRequest', {})
        logging.info(result)
        token = result.get('token')
        deeplinkUrl = result.get('deeplinkUrl')
        logging.info(deeplinkUrl)
        poll_for_signer(token)
        return token, deeplinkUrl
    except requests.RequestException as e:
        logging.error(f"Error: {e}")
        return None, None

def cast(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    keypair = retrieve_keypair_as_dict(user_id)
    if keypair:
        hub_addr = os.getenv("FARCASTER_HUB")
        app_signer = keypair['public_key']
        user_fid = keypair['private_key']  # Assuming you want to use the private key as user_fid

        # Here you can add the logic to perform the "cast" action
        # For example:
        # result = perform_cast(hub_addr, app_signer, user_fid)
        # update.message.reply_text(f"Cast result: {result}")
        send_cast(hub_addr, app_signer, user_fid)

        update.message.reply_text("Cast command received. Processing...")
    else:
        update.message.reply_text("No keypair found for this user.")

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
                'key': signer_public_key,
                'deadline': deadline,
            },
            'primaryType': "SignedKeyRequest",
        }
    encoded_message = encode_structured_data(data)
    signature = str(account.sign_message(encoded_message).signature.hex())
    logging.info(signature)
    return send_warpcast_request(signer_public_key, APP_FID, signature, deadline)

if __name__ == '__main__':
    initialize_db()
    BOT_TOKEN = os.environ.get("MOCK_BOT_TOKEN")
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    login_handler = CommandHandler('login', login)
    application.add_handler(login_handler)

    cast_handler = CommandHandler('cast', cast)
    application.add_handler(cast_handler)

    application.run_polling()
