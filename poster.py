import logging
import asyncio
import os
import glob
import shutil
import argparse
from pathlib import Path
from argparse import Namespace
from util import is_valid_tx
from monstr.client.client import ClientPool
from util import get_nostr_bitcoin_tx_event, post_hex_tx_api, ConfigError, \
    BLOCKSTREAM_URL_MAP, MEMPOOL_URL_MAP,load_toml

# options can be in this file rather than given at command line
CONFIG_FILE = f'{Path.home()}/.nostrpy/tx_poster.toml'

# default relay
DEFAULT_RELAY = 'ws://localhost:8081'

# default network for broadcasting txs on
DEFAULT_NETWORK = 'mainnet'

# default service to use broadcasting txs
DEFAULT_OUTPUT = 'mempool'


class InvalidTxHex(Exception):
    pass


def load_tx(filename):
    with open(filename) as f:
        tx_data = f.read().strip()
        if not is_valid_tx(tx_data):
            raise InvalidTxHex('data from file does not look like bitcoin tx: %s' % tx_data[:20])
        return tx_data


def get_cmdline_args(args):
    parser = argparse.ArgumentParser(
        prog='bitcoin transaction poster',
        description='post raw bitcoin txs to nostr or direct to mempool, blockstreaminfo, or via local bitcoin node'
    )

    parser.add_argument('-r', '--relay', action='store', default=args['relay'],
                        help=f'when --output includes nostr this is a comma seperated list of relays to post to, default [{args["relay"]}]')
    parser.add_argument('-n', '--network', action='store', default=args['network'],  choices=['mainnet', 'testnet', 'signet'],
                        help=f'bitcoin network for the bitcoin transactions to be posted on,  default [{args["network"]}]')
    parser.add_argument('-e', '--hex', action='store', default=None,
                        help='raw bitcoin tx hex')
    parser.add_argument('-f', '--filename', action='store', default=None,
                        help='filename for file containing raw bitcoin tx hex')
    parser.add_argument('-d', '--dir', action='store', default=args['dir'],
                        help=f'directory containing *.txn raw bitcoin tx files, default[{args["dir"]}]')
    parser.add_argument('-w', '--watch', action='store_true', default=args["watch"],
                        help=f"""with -d option keep running and monitor directory broadcasting txs as they are created.
                        A subdir ./done will be created and txn files will be moved there after being broadcast.
                        default [{args["watch"]}]
                        """)
    parser.add_argument('-o', '--output', action='store', default=args["output"],
                        help=f"""comma seperated list of outputs to broadcast txs valid values are nostr, mempool, blockstream, or
                        bitcoind - default {args["output"]}
                        """)

    parser.add_argument('--debug', action='store_true', help='enable debug output')

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
        'hex': None,
        'filename': None,
        'file_data': None,
        'dir': None,
        'watch': False,
        'debug': False
    }

    # now form config file if any
    ret.update(load_toml(CONFIG_FILE))

    # now from cmd line
    ret.update(get_cmdline_args(ret))

    # if debug flagged enable now
    if ret['debug'] is True:
        logging.getLogger().setLevel(logging.DEBUG)

    # extra checks on the config we have to make sure it makes sense

    # if hex given check if looks valid
    if ret['hex']:
        if not is_valid_tx(ret['hex']):
            raise ConfigError(f'invalid tx hex: {ret["hex"]}')

    # if file read it
    if ret['filename']:
        try:
            ret['file_data'] = load_tx(ret['filename'])
        except InvalidTxHex as itx:
            raise ConfigError(str(itx))
        except Exception as e:
            raise ConfigError(f'something went wrong reading file: {ret["filename"]}')

    if ret['dir']:
        if not os.path.isdir(ret['dir']):
            raise ConfigError(f'{ret["dir"]} doesn\'t look like a directory')
        # make the done dir if it doesn't exist
        if not os.path.isdir(f'{ret["dir"]}/done'):
            try:
                os.makedirs(f'{ret["dir"]}/done')
            except Exception as e:
                raise ConfigError(f'unable to make done dir at: {ret["dir"]}')

    if not ret['hex'] and not ret['filename'] and not ret['dir']:
        raise ConfigError('at least one of --hex, --filename, or --dir is required')

    # split the outputs
    ret['output'] = ret['output'].split(',')
    for o in ret['output']:
        if o not in ('nostr', 'mempool', 'blockstream', 'bitcoind'):
            raise ConfigError(f'value {o} is not a valid output')
        if o in ('bitcoind'):
            raise ConfigError(f'output {o} not yet implemented')

    if ret['watch']:
        if not ret['dir']:
            raise ConfigError('--watch only valid where a directory is supplied')

    # if nostr then relay needs to defined
    if 'nostr' in ret['output']:
        if ret['relay'] is None:
            raise ConfigError('output nostr but no relays given!')


    logging.debug(f'new_get_args:: running with options - {ret}')

    return ret


def get_postr_nostr(the_client: ClientPool, network: str):
    def nostr_post(tx_hex: str):
        the_client.publish(get_nostr_bitcoin_tx_event(tx_hex=tx_hex,
                                                      network=network))

    return nostr_post


def get_post_api(api, network: str):
    url_map = {
        'mempool': MEMPOOL_URL_MAP,
        'blockstream': BLOCKSTREAM_URL_MAP
    }

    def api_post(tx_hex: str):
        try:
            to_url = url_map[api][network]
            asyncio.create_task(post_hex_tx_api(to_url=to_url,
                                                tx_hex=tx_hex))
        except KeyError as ke:
            logging.info(f'post_tx to {api} - unable to broadcast event err - {ke}')

    return api_post


def post_files(the_dir: str, outputs: []):
    # find tx files
    tx_files = glob.glob('%s/*.txn' % the_dir)

    for c_filename in tx_files:
        try:
            tx_hex = load_tx(c_filename)
        # TODO: create a error dir and move file there
        except InvalidTxHex as bad_file:
            pass

        # post the tx and then move the file to dir/done
        [c_out(tx_hex) for c_out in outputs]

        # not we don't actually check if we succeeded in outputing...
        shutil.move(c_filename, c_filename.replace(the_dir.strip('/'), '%s/done' % the_dir))


async def main(args: dict):

    # to connect to
    relay = args['relay']

    # the actual client
    my_client = ClientPool(relay)

    # publish to this network
    network = args['network']

    # this may be set if just doing a one off
    tx_hex = args['hex']

    # may be set if one off from a file
    file_data = args['file_data']

    # may be one off sweep or we might watch
    tx_dir = args['dir']

    # in combo with dir, watch that dir for new txs
    watch = args['watch']

    my_posters = {
        'nostr': get_postr_nostr(my_client, network),
        'mempool': get_post_api('mempool', network),
        'blockstream': get_post_api('blockstream', network)
    }

    outputs = []
    for out_name in args['output']:
        outputs.append(my_posters[out_name])

    # only connect relay if we're outputing via nostrr
    if 'nostr' in args['output']:
        asyncio.create_task(my_client.run())
        await my_client.wait_connect()
        print('connect to nostr relays')


    # posting of any hex supplied as arg
    if tx_hex:
        [c_out(tx_hex) for c_out in outputs]

    # filename option, file_data should exist
    if file_data:
        [c_out(file_data) for c_out in outputs]

    # any files in this dir
    if tx_dir:
        post_files(tx_dir, outputs)

    # if watch then we'll hang around and watch that dir for new *.txn files
    if watch:
        print(f'watching for bitcoin transactions at: {tx_dir} output to {args["output"]}')
        while True:
            await asyncio.sleep(1)
            post_files(tx_dir, outputs)

        # hack so don't exit before we actually manage to send any we're not staying running
        # better to check notices/sub and see events probably
        await asyncio.sleep(1)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.ERROR)
    try:
        asyncio.run(main(get_args()))
    except ConfigError as ce:
        print(ce)
    # asyncio.run(main())
    # print(is_valid_tx('020000000001012059c1a33d50ac2c255c4a29112fe85a255b3717f9ee644a823c8b4b6d108f710000000000fdffffff02d007000000000000160014165b9dd9bcd58db7e4960f45d82f872a22672b86ecbc7e0000000000160014b16a74d5e17c4b20235fc4440d0d339582fadbda0247304402205d4a4abf7f73d31ef259d1d7565b4115f5acbe1aa2fdb96afec001c6ecc430ac02205d6e2e63a937e1852e1b075d6f04f05bb3e23e50ba760fa8fd61a23b958d16df012102ab4c89073302f259355487bf4c5213c979e9c1c15a8de1c5df63e3e9851661cb2a192500'))
