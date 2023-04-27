import logging
import asyncio
from monstr.client.client import ClientPool, Client
from monstr.client.event_handlers import EventHandler
from monstr.event.event import Event

clients = 'wss://relay.damus.io,wss://nostr.wine'.split(',')


class TxEventHandler(EventHandler):

    def do_event(self, the_client: Client, sub_id, evt: Event):
        print(the_client.url,evt)


async def main():
    tx_handler = TxEventHandler()

    def my_connect(the_client: Client):
        print('connected to: %s' % the_client.url)
        the_client.subscribe(sub_id='btc_txs',
                             handlers=[tx_handler],
                             filters={
                                 'kinds': [Event.KIND_TEXT_NOTE]
                             })

    async with ClientPool(clients=clients,
                          on_connect=my_connect) as c:
        while True:
            await asyncio.sleep(0.5)
            print('sleeping...')


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    asyncio.run(main())