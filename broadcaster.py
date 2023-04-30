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
from util import post_event_tx_api, APIServiceURLMap


class APIEventHandler(EventHandler):

    def __init__(self, api_name: str, network: str = 'any'):
        self._api_name = api_name
        self._map = APIServiceURLMap(service_name=api_name)
        self._network = network

    def do_event(self, the_client: Client, sub_id, evt: Event):
        post_url, err = self._map.get_url_map_event(evt=evt,
                                                    network=self._network)
        if err:
            logging.info('%s::do_event - unable to broadcast event err - %s' % (self._api_name,
                                                                                err))
        else:
            asyncio.create_task(post_event_tx_api(post_url, evt))


async def main():
    # options this are defaults, TODO: from cmd line and toml file
    # relays to output to
    relays = 'ws://localhost:8081'.split(',')
    # default to main net
    network = 'any'

    # create the tx broadcasters, TODO: which ones enabled should be from cmd line
    mempool_event_handler = APIEventHandler(api_name='mempool',
                                            network=network)

    blockstream_event_handler = APIEventHandler(api_name='blockstream',
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