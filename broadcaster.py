"""
    The broadcaster monitors a number of relays for raw bitcoin tx events (Kind 28333)
    on seeing a bitcoin tx it will broadcast via a broadcast method -

        mempoolapi          DONE
        blockstraminfo      DONE
        bitcoinrpc          TODO

"""
import logging
import asyncio
from monstr.client.client import ClientPool, Client
from monstr.client.event_handlers import EventHandler
from monstr.event.event import Event
from util import post_tx_api

# mappings to post a tx via mempool
mempool_url_map = {
    'mainnet': 'https://mempool.space/api/tx',
    'testnet': 'https://mempool.space/testnet/api/tx',
    'signet': 'https://mempool.space/signet/api/tx"'
}

# and same via blockstream
blockstream_url_map = {
    'mainnet': 'https://blockstream.info/api/tx',
    'testnet': 'https://blockstream.info/testnet/api/tx'
}


def get_event_url_map(evt:Event, network:str, url_map: dict):
    url, err = None, None

    # if any then we'll be getting the network from the network tag on the event
    if network == 'any':
        network_tags = evt.get_tags_value('network')
        if network_tags:
            network = network_tags[0]
        else:
            return None, 'event has no network tag!, id: %s' % evt.id

    if network in url_map:
        ret = url_map[network]
    else:
        err = 'no url mapping found for network - %s' % network

    return ret, err


class APIEventHandler(EventHandler):

    def __init__(self, api_name:str, url_map: dict, network:str = 'any'):
        self._api_name = api_name
        self._url_map = url_map
        self._network = network

    def do_event(self, the_client: Client, sub_id, evt: Event):
        post_url, err = get_event_url_map(evt=evt,
                                          network=self._network,
                                          url_map=self._url_map)
        if err:
            logging.info('%s::do_event - unable to broadcast event err - %s' % (self._api_name,
                                                                                err))
        else:
            asyncio.create_task(post_tx_api(post_url, evt))


async def main():
    # options this are defaults, TODO: from cmd line and toml file
    # relays to output to
    relays = 'ws://localhost:8081'.split(',')
    # default to main net
    network = 'any'

    # create the tx broadcasters, TODO: which ones enabled should be from cmd line
    mempool_event_handler = APIEventHandler(api_name='mempool',
                                            url_map=mempool_url_map,
                                            network=network)
    blockstream_event_handler = APIEventHandler(api_name='blockstream',
                                                url_map=blockstream_url_map,
                                                network=network)

    def on_connect(the_client: Client):
        the_client.subscribe(sub_id='btc_txs',
                             handlers=blockstream_event_handler,
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