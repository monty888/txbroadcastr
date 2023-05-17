"""
    The broadcaster monitors a number of relays for raw bitcoin tx events (Kind 28333)
    on seeing a bitcoin tx it will broadcast via a broadcast method -

        mempoolapi          DONE
        blockstraminfo      DONE
        bitcoinrpc          DONE

"""
import logging
from copy import copy
import asyncio
import argparse
from pathlib import Path
from abc import ABC, abstractmethod
from monstr.client.client import ClientPool, Client
from monstr.client.event_handlers import EventHandler
from monstr.event.event import Event
from util import ConfigError, post_hex_tx_api, sendrawtransaction_bitcoind, get_event_network, is_valid_tx,\
    BLOCKSTREAM_URL_MAP, MEMPOOL_URL_MAP, load_toml

# options can be in this file rather than given at command line
CONFIG_FILE = f'{Path.home()}/.nostrpy/tx_broadcaster.toml'

# default relay
DEFAULT_RELAY = 'ws://localhost:8081'

# default network for broadcasting txs on
DEFAULT_NETWORK = 'any'

# default service to use broadcasting txs
DEFAULT_OUTPUT = 'mempool'


class UnsupportedNetwork(Exception):
    pass


class InvalidTxHex(Exception):
    pass


class BroadCaster(ABC):

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_networks(self) -> set:
        return set(self._url_map.keys())

    @abstractmethod
    async def broadcast_hex(self, tx_hex: str, network: str):
        pass


class APIBroadcaster(BroadCaster):
    """
        broadcaster via a webapi where
        url_map is a dict of network<>url endpoints

    """
    def __init__(self, name: str, url_map: dict):
        self._name = name
        self._url_map = url_map

    async def broadcast_hex(self, tx_hex: str, network: str):
        await post_hex_tx_api(to_url=self._url_map[network],
                              tx_hex=tx_hex)


class BitcoindBroadcaster(BroadCaster):
    """
        broadcaster via bitcoind
    """
    def __init__(self, user: str, password: str):
        self._name = 'bitcoind'
        self._user = user
        self._password = password

        # hardcode to to defaults for now
        self._url_map = {
            'mainnet': 'http://localhost:8332',
            'testnet': 'http://localhost:18332',
            'signet': 'http://localhost:38332'
        }

    async def broadcast_hex(self, tx_hex: str, network: str):
        await sendrawtransaction_bitcoind(self._url_map[network],
                                          user=self._user,
                                          password=self._password,
                                          tx_hex=tx_hex)


class BroadcasterHandler(EventHandler):

    def __init__(self, broadcaster: BroadCaster, network: str = 'any'):
        self._broadcaster = broadcaster
        self._network = network

    def do_event(self, the_client: Client, sub_id, evt: Event):
        """
        checks event contains valid tx hex and a network to broadcast then uses the given broadcasters
        broadcast_hex func
        :param the_client:
        :param sub_id:
        :param evt:
        :return:
        """

        try:
            # we could default to a network if not network tag but for now ignore
            network = get_event_network(evt)
            if not network:
                raise ValueError('BroadcasterHandler::do_event - event missing network tag - %s' % evt)

            # are we broadcasting events for this network?
            if self._network == 'any' or self._network == network:
                # is the network one supported by our broadcaster
                if network not in self._broadcaster.supported_networks:
                    raise UnsupportedNetwork('BroadcasterHandler::do_event network %s not supported by %s' % (network,
                                                                                                              self._broadcaster.name))

                # is the content a valid bitcoin tx, note we don't do any other checks (e.g. of set kind)
                tx_hex = evt.content
                if not is_valid_tx(tx_hex):
                    raise InvalidTxHex(
                        'BroadcasterHandler::do_event - event content does\'t look valid bitcoin tx hex - %s' % tx_hex)

                # finally we can attempt to broadcast the tx
                asyncio.create_task(self._broadcaster.broadcast_hex(tx_hex=tx_hex,
                                                                    network=network))

        except (InvalidTxHex, ValueError) as e:
            print(e)


def get_cmdline_args(args) -> dict:
    parser = argparse.ArgumentParser(
        prog='nostr bitcointx broadcaster',
        description="""
        monitors nostr relays for bitcoin tx events (kind 28333) and broadcasts to any of blockstream,
        mempool, or bitcoind.
        """
    )

    parser.add_argument('-r', '--relay', action='store', default=args['relay'],
                        help=f'comma seperated list of relays to monitor, default[{args["relay"]}]')
    parser.add_argument('-n', '--network', action='store', default='any', choices=['any','mainnet', 'testnet', 'signet'],
                        help=f'broadcast events seen for for this network, default[{args["network"]}]')
    parser.add_argument('-o', '--output', action='store', default=args['output'],
                        help=f"""comma seperated list of outputs to broadcast txs valid values are mempool, blockstream, or
                        bitcoind, default[{args["output"]}]
                        """)
    parser.add_argument('-u', '--user', action='store', default=args['user'],
                        help="""
                        rpc username for bitcoind, required if output bitcoind
                        """)
    parser.add_argument('-p', '--password', action='store', default=args['password'],
                        help="""
                        rpc password for bitcoind, required if output bitcoind
                        """)

    parser.add_argument('--debug', action='store_true', help='enable debug output', default=args['debug'])

    ret = parser.parse_args()

    return vars(ret)


def get_args() -> dict:
    """
    get args to use order is
        default -> toml_file -> cmd_line options

    so command line option is given priority if given

    :return: {}
    """

    # set up the defaults if not overriden
    ret = {
        'relay': DEFAULT_RELAY,
        'network': DEFAULT_NETWORK,
        'output': DEFAULT_OUTPUT,
        'user': None,
        'password': None,
        'debug': False
    }

    # now form config file if any
    ret.update(load_toml(CONFIG_FILE))

    # now from cmd line
    ret.update(get_cmdline_args(ret))

    # if debug flagged enable now
    if ret['debug'] is True:
        logging.getLogger().setLevel(logging.DEBUG)

    # make sure output is valid
    ret['output'] = ret['output'].split(',')
    for o in ret['output']:
        if o not in ('mempool', 'blockstream', 'bitcoind'):
            raise ConfigError('value %s is not a valid output' % o)
        if o == 'bitcoind' and (not ret['user'] or not ret['password']):
            raise ConfigError('--user and --password required when output includes bitcoind')

    ret_out = copy(ret)
    if ret['password']:
        ret_out['password'] = '****'

    logging.debug(f'new_get_args:: running with options - {ret}')

    return ret


async def main(args):
    # options this are defaults, TODO: from cmd line and toml file
    # relays to output to
    relays = args['relay'].split(',')

    # default to main net
    network = args['network']

    # rpc user and password if output via bitcoind
    user = args['user']
    password = args['password']

    # output services, can be more then 1
    output = args['output']

    # create the tx broadcasters, TODO: which ones enabled should be from cmd line
    handlers = []
    if 'mempool' in output:
        handlers.append(
            BroadcasterHandler(APIBroadcaster(name='mempool',
                                              url_map=MEMPOOL_URL_MAP))
        )

    if 'blockstream' in output:
        handlers.append(
            BroadcasterHandler(APIBroadcaster(name='blockstream',
                                              url_map=BLOCKSTREAM_URL_MAP))
        )

    if 'bitcoind' in output:
        handlers.append(BroadcasterHandler(BitcoindBroadcaster(user=user,
                                                               password=password)))

    def on_connect(the_client: Client):
        the_client.subscribe(sub_id='btc_txs',
                             handlers=handlers,
                             filters={
                                 'kinds': [Event.KIND_BTC_TX]
                             })
    print(f'started listening for bitcoin txs to relay at: {relays} network: {network} ')
    print(f'broadcast via: {output} ')
    # wait listening for events
    async with ClientPool(clients=relays,
                          on_connect=on_connect) as c:
        while True:
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.ERROR)

    try:
        asyncio.run(main(get_args()))
    except ConfigError as ce:
        print(ce)