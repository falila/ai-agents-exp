import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.wallet import generate_faucet_wallet

class XRPLManager:
    def __init__(self, node_url: str):
        self.client = JsonRpcClient(node_url)

    def create_testnet_wallet(self):
        return generate_faucet_wallet(self.client)
