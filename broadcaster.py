"""
    The broadcaster monitors a number of relays for raw bitcoin tx events (Kind 28333)
    on seeing a bitcoin tx it will broadcast via a broadcast method -

        mempoolapi          DONE
        blockstraminfo      DONE
        bitcoinrpc          TODO

"""
import logging
import asyncio
import argparse
from monstr.client.client import ClientPool, Client
from monstr.client.event_handlers import EventHandler
from monstr.event.event import Event
from util import post_event_tx_api, APIServiceURLMap, ConfigError


class APIEventHandler(EventHandler):

    def __init__(self, api_name: str, network: str = 'any'):
        self._api_name = api_name
        self._map = APIServiceURLMap(service_name=api_name)
        self._network = network

    def do_event(self, the_client: Client, sub_id, evt: Event):
        network_tags = evt.get_tags_value('network')
        if network_tags is None:
            logging.debug('%s::do_event - event missing network tag: %s' % evt)
            return

        network = network_tags[0]
        if self._network != 'any' and network != self._network:
            logging.debug('%s::do_event - ignore event: %s for network %s' % (evt,
                                                                              network))
            return

        try:
            asyncio.create_task(post_event_tx_api(evt=evt,
                                                  to_url=self._map.get_url_map(network)))
        except ValueError as ve:
            logging.info('%s::do_event - unable to broadcast event err - %s' % (self._api_name,
                                                                                ve))


def get_args():
    parser = argparse.ArgumentParser(
        prog='nostr bitcointx broadcaster',
        description="""
        monitors nostr relays for bitcoin tx events (kind 28333) and broadcasts to any of blockstream,
        mempool, or bitcoind.
        """
    )

    parser.add_argument('-r', '--relay', action='store', default='ws://localhost:8081',
                        help='comma seperated list of relays to monitor')
    parser.add_argument('-n', '--network', action='store', default='any', choices=['any','mainnet', 'testnet', 'signet'],
                        help='broadcast events seen for for this network')
    parser.add_argument('-o', '--output', action='store', default='mempool',
                        help="""comma seperated list of outputs to broadcast txs valid values are mempool, blockstream, or
                        bitcoind
                        """)


    parser.add_argument('--debug', action='store_true', help='enable debug output')

    ret = parser.parse_args()
    if ret.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    ret.output = ret.output.split(',')
    for o in ret.output:
        if o not in ('mempool', 'blockstream', 'bitcoind'):
            raise ConfigError('value %s is not a valid output' % o)
        if o in ('bitcoind'):
            raise ConfigError('output %s not yet implemented' % o)

    return ret


async def main(args):
    # options this are defaults, TODO: from cmd line and toml file
    # relays to output to
    relays = args.relay.split(',')
    # default to main net
    network = args.network

    # create the tx broadcasters, TODO: which ones enabled should be from cmd line
    handlers = []
    if 'mempool' in args.output:
        handlers.append(
            APIEventHandler(api_name='mempool',
                            network=network)
        )
    if 'blockstream' in args.output:
        handlers.append(APIEventHandler(api_name='blockstream',
                                        network=network))

    def on_connect(the_client: Client):
        the_client.subscribe(sub_id='btc_txs',
                             handlers=handlers,
                             filters={
                                 'kinds': [Event.KIND_BTC_TX]
                             })
    print('started listening for bitcoin txs to relay at: %s network: %s ' % (relays, network))
    print('broadcast via: %s ' % ','.join(args.output))
    # wait listening for events
    async with ClientPool(clients=relays,
                          on_connect=on_connect) as c:
        while True:
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.ERROR)
    asyncio.run(main(get_args()))