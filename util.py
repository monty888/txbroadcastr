import aiohttp
from bitcoinlib.transactions import Transaction
from monstr.event.event import Event
from monstr.encrypt import Keys

def is_valid_tx(tx_hex: str) -> bool:
    # if we can parse tx_hex it's valid I guess
    ret = False
    try:
        Transaction.parse_hex(tx_hex)
        ret = True
    except Exception as e:
        pass
    return ret


async def post_tx_api(to_url: str, evt: Event):
    tx_hex = evt.content
    if not is_valid_tx(tx_hex):
        print('ignoring invalid tx hex: %s' % tx_hex)

    # change to bytes for posting
    tx_hex = tx_hex.encode('utf8')

    async with aiohttp.ClientSession() as session:
        async with session.post(to_url, data=tx_hex) as resp:
            print(resp.status)
            print(await resp.text())


def get_nostr_bitcoin_tx_event(tx_hex: str, network: str) -> Event:
    # new keys generated for each event
    keys = Keys()

    ret = Event(
        kind=Event.KIND_BTC_TX,
        content=tx_hex,
        pub_key=keys.public_key_hex(),
        tags=[[
            'network', network
        ]]
    )

    ret.sign(keys.private_key_hex())
    return ret
