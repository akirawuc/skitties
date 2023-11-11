import os
from dotenv import load_dotenv
from farcaster.HubService import HubService
from farcaster.fcproto.message_pb2 import SignatureScheme, HashScheme, Embed
from farcaster import Message

# load_dotenv()
# hub_address = os.getenv("FARCASTER_HUB")
def send_cast(hub_addr, app_signer, user_fid):
    hub = HubService(hub_address, use_async=False)
    message_builder = Message.MessageBuilder(
        HashScheme.HASH_SCHEME_BLAKE3, SignatureScheme.SIGNATURE_SCHEME_ED25519,
        bytes.fromhex(app_signer[2:]))

    # add(self, fid, text, mentions=[], mentions_positions=[], embeds=[]) -> MessageData:
    data = message_builder.cast.add(
        fid=user_fid, text="wowow My first post using farcaster-py.\ncc .")
    msg = message_builder.message(data)

    ret = hub.SubmitMessage(msg)
    print("Message posted!")
    print(ret)
    return ret


