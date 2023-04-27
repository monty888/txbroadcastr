import logging
import asyncio
from monstr.client.client import ClientPool
from monstr.encrypt import Keys
from monstr.event.event import Event

file_name = 'test_tx'
relays = 'ws://localhost:8888'.split(',')
account_name = None

def get_keys(account_name) -> Keys:
    ret = None
    if account_name is None:
        ret = Keys()
    return ret
async def main():
    # get the signing keys to use
    keys = get_keys(account_name)
    
    async with ClientPool(clients=relays) as c:
        print('connected, ok load event and publish ')
        n_evt = Event(
            kind=Event.KIND_TEXT_NOTE,
            content='this is a test',
            pub_key=keys.public_key_hex()
        )

        n_evt.sign(keys.private_key_hex())
        c.publish(n_evt)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    asyncio.run(main())