import os
import json
from typing import Dict, Tuple
from web3 import Web3
from eth_account import Account
from hexbytes import HexBytes

# Required environment variables (set in Render dashboard)
INFURA_URL = os.getenv("INFURA_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ABI_PATH = os.getenv("ABI_PATH", "contract_abi.json")

# Validate env
missing = [k for k, v in {
    "INFURA_URL": INFURA_URL,
    "CONTRACT_ADDRESS": CONTRACT_ADDRESS,
    "PRIVATE_KEY": PRIVATE_KEY
}.items() if not v]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

# Web3 setup
w3 = Web3(Web3.HTTPProvider(INFURA_URL))
account = Account.from_key(PRIVATE_KEY)

with open(ABI_PATH, "r", encoding="utf-8") as f:
    contract_abi = json.load(f)

contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=contract_abi
)

def run_oracle_validations(panel_json: Dict) -> Dict:
    """
    Stub for your two-oracle pipeline.
    Raise errors if validation fails. Return status dict if ok.
    """
    # TODO: replace with real validation logic (Trust Filter + Prediction Verifier)
    return {"oracle_a_status": "ok", "oracle_b_status": "ok"}

def deterministic_hash(obj: Dict) -> str:
    """
    Keccak-256 over canonical JSON (sorted keys, compact separators).
    """
    data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return Web3.keccak(data).hex()

def build_event_payload(panel_json: Dict, event_type: str) -> Tuple[str, str]:
    """
    Extract panel_id and compute the event hash over the full updated DPP snapshot.
    """
    try:
        panel_id = panel_json["Factory Registration"]["Panel_ID"]
    except Exception:
        raise ValueError("Panel_ID not found at Factory Registration.Panel_ID")

    # Contract constraints
    if not (0 < len(panel_id) <= 64):
        raise ValueError("Invalid panelId length")
    if not (0 < len(event_type) <= 32):
        raise ValueError("Invalid eventType length")

    # Optionally update lifecycle metadata inline (oracle wallet + anchor time)
    panel_json.setdefault("Installation_Metadata", {})
    panel_json["Installation_Metadata"]["oracle_wallet"] = account.address
    # Use latest block timestamp for clear on-chain correlation
    panel_json["Installation_Metadata"]["anchored_at"] = int(w3.eth.get_block("latest").timestamp)

    # Hash the full payload snapshot (ID, event type, DPP JSON)
    event_hash_hex = deterministic_hash({
        "panel_id": panel_id,
        "event_type": event_type,
        "dpp": panel_json
    })

    return panel_id, event_hash_hex

def anchor_event(panel_id: str, event_type: str, event_hash_hex: str) -> str:
    """
    Call addPanelEvent(panelId, eventType, eventHash) with EIP-1559 fields.
    """
    event_hash_bytes32 = HexBytes(event_hash_hex)

    tx = contract.functions.addPanelEvent(panel_id, event_type, event_hash_bytes32).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "maxFeePerGas": w3.to_wei("30", "gwei"),
        "maxPriorityFeePerGas": w3.to_wei("2", "gwei"),
        "gas": 250000,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    return receipt.transactionHash.hex()

def process_and_anchor(panel_json: Dict, event_type: str = "installation") -> Tuple[str, str, str]:
    """
    Full pipeline: validations → build payload → anchor on-chain.
    Returns (panel_id, event_type, tx_hash).
    """
    validations = run_oracle_validations(panel_json)
    if validations.get("oracle_a_status") != "ok" or validations.get("oracle_b_status") != "ok":
        raise RuntimeError("Oracle validation failed")

    panel_id, event_hash_hex = build_event_payload(panel_json, event_type)
    tx_hash = anchor_event(panel_id, event_type, event_hash_hex)
    return panel_id, event_type, tx_hash
