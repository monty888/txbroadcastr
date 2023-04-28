"""
    The broadcaster monitors a number of relays for raw bitcoin tx events (Kind 28333)
    on seeing a bitcoin tx it will broadcast via a broadcast method -

        mempoolapi          DONE
        blockstraminfo      DONE
        bitcoinrpc          TODO

"""
import logging
import asyncio
import aiohttp
from monstr.client.client import ClientPool, Client
from monstr.client.event_handlers import EventHandler
from monstr.event.event import Event
from util import is_valid_tx


async def do_event_post_api(to_url:str, evt: Event):
    tx_hex = evt.content
    if not is_valid_tx(tx_hex):
        print('ignoring invalid tx hex: %s' % tx_hex)

    # change to bytes for posting
    tx_hex = tx_hex.encode('utf8')

    async with aiohttp.ClientSession() as session:
        async with session.post(to_url, data=tx_hex) as resp:
            print(resp.status)
            print(await resp.text())


class MempoolEventHandler(EventHandler):

    url_map = {
        'main': 'https://mempool.space/api/tx',
        'test': 'https://mempool.space/testnet/api/tx',
        'signet': 'https://mempool.space/signet/api/tx"'
    }

    def __init__(self, network='main'):
        if network not in MempoolEventHandler.url_map:
            raise ValueError('unsupported network for Mempool rebroadcaster - %s' % network)

        self._post_url = MempoolEventHandler.url_map[network]

    def do_event(self, the_client: Client, sub_id, evt: Event):
        asyncio.create_task(do_event_post_api(self._post_url, evt))


class BlockstreamEventHandler(EventHandler):

    url_map = {
        'main': 'https://blockstream.info/api/tx',
        'test': 'https://blockstream.info/testnet/api/tx'
    }

    def __init__(self, network='main'):
        if network not in MempoolEventHandler.url_map:
            raise ValueError('unsupported network for Blockstream rebroadcaster - %s' % network)

        self._post_url = BlockstreamEventHandler.url_map[network]

    def do_event(self, the_client: Client, sub_id, evt: Event):
        asyncio.create_task(do_event_post_api(self._post_url, evt))


async def main():
    # options this are defaults, TODO: from cmd line and toml file
    # relays to output to
    relays = 'ws://localhost:8081'.split(',')
    # default to main net
    network = 'test'

    def on_connect(the_client: Client):
        the_client.subscribe(sub_id='btc_txs',
                             handlers=BlockstreamEventHandler(network),
                             filters={
                                 'kinds': [Event.KIND_BTC_TX]
                             })
    print('started listening for bitcoin txs to relay at: %s' % relays)
    # wait listening for events
    async with ClientPool(clients=relays,
                          on_connect=on_connect) as c:
        while True:
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    asyncio.run(main())