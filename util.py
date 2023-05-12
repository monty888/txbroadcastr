import json
import aiohttp
from aiohttp import ClientSession
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


async def post_event_tx_api(to_url: str, evt: Event):
    tx_hex = evt.content
    if is_valid_tx(tx_hex):
        # change to bytes for posting
        await post_hex_tx_api(to_url=to_url,
                              tx_hex=tx_hex)
    else:
        print('ignoring invalid tx hex: %s' % tx_hex)


async def post_hex_tx_api(to_url: str, tx_hex: str):
    tx_hex = tx_hex.encode('utf8')

    print(to_url)
    async with aiohttp.ClientSession() as session:
        async with session.post(to_url, data=tx_hex) as resp:
            if resp.status == 200:
                print(await resp.text())
            else:
                print('post_hex_tx_api::post %s - bad status %s' % (to_url, resp.status))


async def sendrawtransaction_bitcoind(to_url: str, user: str, password: str, tx_hex: str):
    try:
        async with ClientSession() as session:
            async with session.post(
                    url=to_url,
                    data=json.dumps({
                        'method': 'sendrawtransaction',
                        'params': [tx_hex]
                        # probably should send but doesn't cause issue that we don't....
                        # 'jsonrpc': '2.0',
                        # 'id': 1
                    }),
                    auth=aiohttp.BasicAuth(user, password)
            ) as resp:
                if resp.status == 200:
                    print(await resp.text())
                else:
                    print('sendrawtransaction_bitcoind::post %s - bad status %s' % (to_url, resp.status))

    except Exception as e:
        print(e)


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


class ConfigError(Exception):
    pass


class APIServiceURLMap:

    service_maps = {
        # mappings to post a tx via mempool
        'mempool': {
            'mainnet': 'https://mempool.space/api/tx',
            'testnet': 'https://mempool.space/testnet/api/tx',
            'signet': 'https://mempool.space/signet/api/tx"'
        },
        'blockstream': {
            'mainnet': 'https://blockstream.info/api/tx',
            'testnet': 'https://blockstream.info/testnet/api/tx'
        },
        'bitcoind': {
            'mainnet': 'http://localhost:8332',
            'testnet': 'http://localhost:18332',
            'signet': 'http://localhost:38332'
        }

    }

    def __init__(self, service_name: str):
        if service_name not in APIServiceURLMap.service_maps:
            raise ValueError('unknown tx broadcasting service api - %s' % service_name)
        self._service_name = service_name
        self._url_map = APIServiceURLMap.service_maps[service_name]

    def get_url_map(self, network: str):
        if network in self._url_map:
            ret = self._url_map[network]
        else:
            raise ValueError('no url mapping found for network - %s' % network)
        return ret


