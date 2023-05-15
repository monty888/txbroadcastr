import json
import aiohttp
import logging
from aiohttp import ClientSession
import toml
import sys
from pathlib import Path
from toml import TomlDecodeError
from bitcoinlib.transactions import Transaction
from monstr.event.event import Event
from monstr.encrypt import Keys


# url mapping to mempool.space api
MEMPOOL_URL_MAP ={
    'mainnet': 'https://mempool.space/api/tx',
    'testnet': 'https://mempool.space/testnet/api/tx',
    'signet': 'https://mempool.space/signet/api/tx"'
}

# for blockstram api
BLOCKSTREAM_URL_MAP = {
    'mainnet': 'https://blockstream.info/api/tx',
    'testnet': 'https://blockstream.info/testnet/api/tx'
}


def is_valid_tx(tx_hex: str) -> bool:
    # if we can parse tx_hex it's valid I guess
    ret = False
    try:
        Transaction.parse_hex(tx_hex)
        ret = True
    except Exception as e:
        pass
    return ret


def get_event_network(evt: Event) -> str:
    network_tags = evt.get_tags_value('network')
    ret = None
    if network_tags:
        ret = network_tags[0]
    else:
        logging.debug('%s::do_event - event missing network tag: %s' % evt)
    return ret


async def post_hex_tx_api(to_url: str, tx_hex: str):
    tx_hex = tx_hex.encode('utf8')
    async with aiohttp.ClientSession() as session:
        async with session.post(to_url, data=tx_hex) as resp:
            if resp.status == 200:
                print(await resp.text())
            else:
                print('post_hex_tx_api::post %s - bad status %s' % (to_url, resp.status))
                print(await resp.text())


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
                    print(await resp.text())

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

def load_toml(filename):
    ret = {}
    f = Path(filename)
    if f.is_file():
        try:
            ret = toml.load(filename)
        except TomlDecodeError as te:
            print('Error in config file %s - %s ' % (filename, te))
            sys.exit(2)

    else:
        logging.debug('load_toml:: no config file %s' % filename)
    return ret

class ConfigError(Exception):
    pass
