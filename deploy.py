import json
import os
from web3 import Web3
from solcx import compile_standard, install_solc

print("Installing Solidity Compiler...")
install_solc("0.8.0")

with open("StudentRegistry.sol", "r") as file:
    student_registry_file = file.read()

compiled_sol = compile_standard(
    {
        "language": "Solidity",
        "sources": {"StudentRegistry.sol": {"content": student_registry_file}},
        "settings": {
            "outputSelection": {
                "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
            }
        },
    },
    solc_version="0.8.0",
)

bytecode = compiled_sol["contracts"]["StudentRegistry.sol"]["StudentRegistry"]["evm"]["bytecode"]["object"]
abi = compiled_sol["contracts"]["StudentRegistry.sol"]["StudentRegistry"]["abi"]

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

if not w3.is_connected():
    print(" Error: Could not connect to Ganache. Is it running?")
    exit()

my_address = w3.eth.accounts[0]

print("Deploying Contract to Ganache...")
StudentRegistry = w3.eth.contract(abi=abi, bytecode=bytecode)
tx_hash = StudentRegistry.constructor().transact({'from': my_address})
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

contract_data = {
    "address": tx_receipt.contractAddress,
    "abi": abi
}

with open("contract_info.json", "w") as f:
    json.dump(contract_data, f)

print("-" * 30)
print(f" Contract Deployed Successfully!")
print(f"Address: {tx_receipt.contractAddress}")
print(f"Details saved to contract_info.json")
print("-" * 30)