import logging
import asyncio
import os
import glob
import shutil
import argparse
from argparse import Namespace
from util import is_valid_tx
from monstr.client.client import ClientPool
from util import get_nostr_bitcoin_tx_event


class ConfigError(Exception):
    pass


class InvalidTxHex(Exception):
    pass


def load_tx(filename):
    with open(filename) as f:
        tx_data = f.read().strip()
        if not is_valid_tx(tx_data):
            raise InvalidTxHex('data from file does not look like bitcoin tx: %s' % tx_data[:20])
        return tx_data


def get_args():
    parser = argparse.ArgumentParser(
        prog='bitcoin transaction broadcaster',
        description='broadcast raw bitcoin txs to nostr or direct to mempool, blockstreaminfo, or via local bitcoin node'
    )

    parser.add_argument('-r', '--relay', action='store', default=None,
                        help='when --output includes nostr this is a comma seperated list of relays to post to')
    parser.add_argument('-n', '--network', action='store', default='mainnet',  choices=['mainnet', 'testnet', 'signet'],
                        help='bitcoin network for the bitcoin transactions to be posted on')
    parser.add_argument('-e', '--hex', action='store', default=None,
                        help='raw bitcoin tx hex')
    parser.add_argument('-f', '--filename', action='store', default=None,
                        help='filename for file containing raw bitcoin tx hex')
    parser.add_argument('-d', '--dir', action='store', default=None,
                        help='directory containing *.txn raw bitcoin tx files')
    parser.add_argument('-w', '--watch', action='store_true', default=False,
                        help="""with -d option keep running and monitor directory broadcasting txs as they are created.
                        A subdir ./done will be created and txn files will be moved there after being broadcast.
                        """)
    parser.add_argument('-o', '--output', action='store', default='nostr',
                        help="""comma seperated list of outputs to broadcast txs valid values are nostr, mempool, blockstream, or
                        bitcoind
                        """)

    parser.add_argument('--debug', action='store_true', help='enable debug output')

    ret = parser.parse_args()
    if ret.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # if hex given check if looks valid
    if ret.hex:
        if not is_valid_tx(ret.hex):
            raise ConfigError('invalid tx hex: %s' % ret.hex)

    # if file read it
    if ret.filename:
        try:
            ret.file_data = load_tx(ret.filename)
        except InvalidTxHex as itx:
            raise ConfigError(str(itx))
        except Exception as e:
            raise ConfigError('something went wrong reading file: %s' % ret.filename)

    if ret.dir:
        if not os.path.isdir(ret.dir):
            raise ConfigError('%s doesn\'t look like a directory' % ret.dir)
        # make the done dir if it doesn't exist
        if not os.path.isdir(ret.dir+'/done'):
            try:
                os.makedirs(ret.dir+'/done')
            except Exception as e:
                raise ConfigError('unable to make done dir at: %s' % ret.dir)

    if not ret.hex and not ret.filename and not ret.dir:
        raise ConfigError('at least one of --hex, --filename, or --dir is required')

    # split the outputs
    ret.output = ret.output.split(',')
    for o in ret.output:
        if o not in ('nostr', 'mempool', 'blockstream', 'bitcoind'):
            raise ConfigError('value %s is not a valid output' % o)
        if o in ('mempool', 'blockstream', 'bitcoind'):
            raise ConfigError('output %s not yet implemented' % o)

    if ret.watch:
        if not ret.dir:
            raise ConfigError('--watch only valid where a directory is supplied')

    # if nostr then relay needs to defined
    if 'nostr' in ret.output:
        if ret.relay is None:
            raise ConfigError('output nostr but no relays given!')

    return ret


async def main(args: Namespace):

    def post_tx(hex: str):
        cp.publish(get_nostr_bitcoin_tx_event(tx_hex=hex,
                                              network=args.network))

    def post_files(dir: str):
        # find tx files
        tx_files = glob.glob('%s/*.txn' % dir)

        for c_filename in tx_files:
            try:
                tx_data = load_tx(c_filename)
            # TODO: create a error dir and move file there
            except InvalidTxHex as bad_file:
                pass

            # post the tx and then move the file to dir/done
            post_tx(tx_data)
            shutil.move(c_filename, c_filename.replace(dir, '%s/done' % dir))

    async with ClientPool(clients=args.relay) as cp:

        # posting of any hex supplied as arg
        if args.hex:
            post_tx(args.hex)

        # # filename option, file_data should exist
        if args.filename:
            post_tx(args.file_data)

        if args.dir:
            post_files(args.dir)

        if args.watch:
            print('watching for bitcoin transactions at: %s' % args.dir)
            while True:
                await asyncio.sleep(1)
                post_files(args.dir)

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
