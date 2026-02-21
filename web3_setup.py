from web3_setup import Web3

ganache_url = "http://127.0.0.1:7545" 
web3 = Web3(Web3.HTTPProvider(ganache_url))

if web3.is_connected():
    print("-" * 30)
    print(" Successfully connected to Ganache")
    print(f"Block Number: {web3.eth.block_number}")

    admin_account = web3.eth.accounts[0]
    print(f"Admin Account: {admin_account}")
    print("-" * 30)
else:
    print(" Failed to connect to Ganache. Ensure Ganache is running!")

import joblib
try:
    artifacts = joblib.load('model/student_placement_model.pkl')
    model = artifacts['model']
    trained_cols = artifacts['features']
    print(" XGBoost Model Loaded")
except:
    print(" Model file not found. Ensure it is in the 'model/' directory.")