from bitcoinlib.transactions import Transaction


def is_valid_tx(tx_hex: str) -> bool:
    # if we can parse tx_hex it's valid I guess
    ret = False
    try:
        Transaction.parse_hex(tx_hex)
        ret = True
    except Exception as e:
        pass
    return ret