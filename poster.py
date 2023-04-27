import logging
import asyncio
from monstr.client.client import ClientPool
from monstr.encrypt import Keys
from monstr.event.event import Event

file_name = 'test_tx'
relays = 'ws://localhost:8081'.split(',')
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
            kind=Event.KIND_BTC_TX,
            content='02000000000101c58e8a879e48f3302b90f60faa7fa95cd3396be0af58f7333a3daba28701a6da0000000000fdffffff0133a80000000000001600141e7f884433472e53124af2b23729174983b70dd40247304402201d5697a0714a7a08cc2528834b778028ff49d8bf2093713b28e3d6642633879c0220738410a127d28b15dd6104a44f60fce47d282180ec0f0c12d4350b2bb844ee310121022d599254412f35b628a100834cbb2b7e72c0ff0666eb0c5c3de05935f0d332026af40b00',
            pub_key=keys.public_key_hex()
        )

        n_evt.sign(keys.private_key_hex())
        c.publish(n_evt)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    asyncio.run(main())