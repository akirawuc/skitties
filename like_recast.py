import os
from dotenv import load_dotenv
from farcaster.HubService import HubService
from farcaster.fcproto.message_pb2 import SignatureScheme, HashScheme, Embed
from farcaster import Message


# load_dotenv()
# hub_address = os.getenv("FARCASTER_HUB")
def like_and_recast(hub_addr, app_signer, user_fid):
    # Scenario:
    # - user_fid has approved app_signer.
    # - message with message_hash has been posted by user_fid
    # - we will use the signer to delete the cast

    hub = HubService(hub_address, use_async=False)
    message_builder = Message.MessageBuilder(
        HashScheme.HASH_SCHEME_BLAKE3, SignatureScheme.SIGNATURE_SCHEME_ED25519,
        bytes.fromhex(app_signer[2:]))

    # replace the hash with the actual message hash.
    message_hash = "0x4d113260d9e1e8b8a93fa920cdfcf85590c9a9f9"
    # enum ReactionType {
    #   REACTION_TYPE_NONE = 0;
    #   REACTION_TYPE_LIKE = 1; // Like the target cast
    #   REACTION_TYPE_RECAST = 2; // Share target cast to the user's audience
    # }
    message_data = message_builder.reaction_to_cast.add(fid=user_fid,
                                                        reaction_type=1,
                                                        cast_fid=user_fid,
                                                        cast_hash=message_hash)
    message = message_builder.message(message_data)
    like_ret = hub.SubmitMessage(message)
    print(ret)

    message_data = message_builder.reaction_to_cast.add(fid=user_fid,
                                                        reaction_type=2,
                                                        cast_fid=user_fid,
                                                        cast_hash=message_hash)
    message = message_builder.message(message_data)
    recast_ret = hub.SubmitMessage(message)
    print(ret)
    return (like_ret, recast_ret)

