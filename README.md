# txbroadcastr
bitcoin  tx broadcaster in python based on https://github.com/benthecarman/nostr-tx-broadcast

* broadcaster.py - listens to nostr relays for transient bitcoin tx event kind (28333) 
and broadcasts the events content as bitcoin tx via mempool.space, blockstream, or local bitcoind
* poster.py - posts bitcoin transactions to nostr, or directly to a service.
Can be done as one off or monitor a directory for *.txn signed transaction files.

# broadcaster
```
usage: nostr bitcointx broadcaster [-h] [-r RELAY]
                                   [-n {any,mainnet,testnet,signet}]
                                   [-o OUTPUT] [-u USER] [-p PASSWORD]
                                   [--debug]

monitors nostr relays for bitcoin tx events (kind 28333) and broadcasts to any
of blockstream, mempool, or bitcoind.

options:
  -h, --help            show this help message and exit
  -r RELAY, --relay RELAY
                        comma seperated list of relays to monitor
  -n {any,mainnet,testnet,signet}, --network {any,mainnet,testnet,signet}
                        broadcast events seen for for this network
  -o OUTPUT, --output OUTPUT
                        comma seperated list of outputs to broadcast txs valid
                        values are mempool, blockstream, or bitcoind
  -u USER, --user USER  rpc username for bitcoind, required if output bitcoind
  -p PASSWORD, --password PASSWORD
                        rpc password for bitcoind, required if output bitcoind
  --debug               enable debug output
```
__examples__  
```
$ python broadcaster.py
```
listen for bitcoin tx events on local relay ws://localhost:8081 and broadcast to mempool.space
```
python broadcaster.py -r wss://nos.lol -o bitcoind --user=monty --password=password
```
listen for bitcoin tx events on wss://nos.lol and post to local bitcoind instance

# poster

```
usage: bitcoin transaction poster [-h] [-r RELAY] [-n {mainnet,testnet,signet}] [-e HEX] [-f FILENAME]
                                  [-d DIR] [-w] [-o OUTPUT] [--debug]

post raw bitcoin txs to nostr or direct to mempool, blockstreaminfo, or via local bitcoin node

options:
  -h, --help            show this help message and exit
  -r RELAY, --relay RELAY
                        when --output includes nostr this is a comma seperated list of relays to post
                        to - default ws://localhost:8081
  -n {mainnet,testnet,signet}, --network {mainnet,testnet,signet}
                        bitcoin network for the bitcoin transactions to be posted on - default mainnet
  -e HEX, --hex HEX     raw bitcoin tx hex
  -f FILENAME, --filename FILENAME
                        filename for file containing raw bitcoin tx hex
  -d DIR, --dir DIR     directory containing *.txn raw bitcoin tx files
  -w, --watch           with -d option keep running and monitor directory broadcasting txs as they are
                        created. A subdir ./done will be created and txn files will be moved there
                        after being broadcast.
  -o OUTPUT, --output OUTPUT
                        comma seperated list of outputs to broadcast txs valid values are nostr,
                        mempool, blockstream, or bitcoind - default nostr
  --debug               enable debug output
```
__examples__  
```
$ python poster.py --hex '02...'
```  
posts given hex bitcoin tx, by default this will be to nostr and tagged as a mainnet tx   
```
$ python poster.py --dir /home/monty/bitcoin_txs/ -o mempool -w
```
watches /home/monty/bitcoin_txs/ and posts *.txn files saved there to mempool.space api,
by default the txs will be posted to mainnet


# todo
- [ ] configs from toml file 
- [ ] instead of network tag change to use magic and network magic nums
- [ ] change using nostr event content for the tx value to being held within tags.