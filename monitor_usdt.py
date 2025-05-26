import requests
import time
import json
from datetime import datetime
import os # For file path handling
import threading
import queue

# --- Configuration ---
BSCSCAN_API_KEY = "M4W3T779D8ZBNIYDTFIUWKY21AAC4ISHR2"  # Replace with your BscScan API Key
MONITORED_ADDRESS = "0xBbeC5076e3fb65A4e59BFFc6C190Afd422621368"  # Replace with the address you want to monitor
USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955" # USDT on BSC

CHECK_INTERVAL_SECONDS = 0.5  # How often to check (0.5 = twice a second)
API_REQUEST_TIMEOUT = 5     # Seconds to wait for API response (reduced for faster cycles)
BSC_RPC_URL = "https://bsc-dataseed.binance.org/" # Public BSC RPC
AMOUNT_FILE_PATH = "amount.txt" # File to store the detected amount

# --- Global State ---
processed_tx_hashes = set()
last_processed_block = None

# --- File Writing Queue and Thread ---
file_write_queue = queue.Queue()
stop_event = threading.Event()

def file_writer_thread_func():
    """
    Worker thread that processes the file write queue.
    Writes amounts to the AMOUNT_FILE_PATH.
    """
    thread_name = threading.current_thread().name
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {thread_name}: File writer thread started.")
    
    while not stop_event.is_set() or not file_write_queue.empty():
        try:
            # Wait for an item for a short period to allow checking stop_event
            amount_str = file_write_queue.get(timeout=0.1)
            
            temp_file_path = AMOUNT_FILE_PATH + ".tmp"
            try:
                with open(temp_file_path, 'w') as f:
                    f.write(amount_str)
                    f.flush()  # Ensure data is passed from Python's buffer to OS buffer
                    os.fsync(f.fileno()) # Ensure OS buffer is flushed to disk
                
                os.replace(temp_file_path, AMOUNT_FILE_PATH) # Atomic rename/move
                
                # Optional: print confirmation from worker thread if desired
                # print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {thread_name}: Amount {amount_str} written to {AMOUNT_FILE_PATH}")
            
            except IOError as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {thread_name}: Error writing amount to file {AMOUNT_FILE_PATH}: {e}")
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {thread_name}: Unexpected error during file write operation: {e}")
            finally:
                file_write_queue.task_done()

        except queue.Empty:
            # Queue is empty, loop again to check stop_event or wait for new items
            continue
        except Exception as e:
            # Catch-all for other errors in the worker loop (e.g., from queue ops)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {thread_name}: Error in worker loop: {e}")
            # Sleep briefly to prevent tight error loops if queue operations fail continuously
            if not stop_event.is_set(): # Avoid sleeping if we are trying to shut down
                 time.sleep(1)
                 
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {thread_name}: File writer thread stopped.")

def write_amount_to_file_queued(amount_value_str):
    """
    Queues the amount string for writing by the background file writer thread.
    This function returns quickly.
    """
    file_write_queue.put(amount_value_str)
    # Optional: print a confirmation that item is queued, if desired
    # print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Amount {amount_value_str} queued for writing to {AMOUNT_FILE_PATH}")


def get_bep20_token_transfers(address, contract_address, api_key, start_block=0, sort_order='asc', page=1, offset=100):
    """
    Fetches BEP20 token transfers for a given address and contract.
    """
    api_url = "https://api.bscscan.com/api"
    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": contract_address,
        "address": address,
        "startblock": start_block,
        "endblock": 99999999, # Effectively 'latest'
        "page": page,
        "offset": offset,
        "sort": sort_order,
        "apikey": api_key,
    }

    try:
        response = requests.get(api_url, params=params, timeout=API_REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "1":
            return data["result"]
        elif data["status"] == "0" and data["message"] == "No transactions found":
            return []
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BscScan API Info: {data['message']} (Result: {data.get('result', '')})")
            return []
    except requests.exceptions.Timeout:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: Request to BscScan API timed out.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error fetching transactions from BscScan: {e}")
        return []
    except json.JSONDecodeError:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: Could not decode JSON response from BscScan. Response text: {response.text if 'response' in locals() else 'N/A'}")
        return []

def get_current_block_number_rpc(rpc_url):
    """Fetches the current block number from a BSC RPC node."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    }
    try:
        response = requests.post(rpc_url, json=payload, timeout=API_REQUEST_TIMEOUT)
        response.raise_for_status()
        return int(response.json()['result'], 16)
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error fetching current block number from RPC ({rpc_url}): {e}")
        return None

def initialize_last_processed_block():
    """Initializes last_processed_block intelligently."""
    global last_processed_block

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initializing last processed block...")

    current_block_rpc = get_current_block_number_rpc(BSC_RPC_URL)
    if current_block_rpc is not None:
        last_processed_block = current_block_rpc
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Started monitoring from current block: {last_processed_block} (via RPC)")
        return

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RPC block fetch failed. Trying BscScan for last transaction block...")
    initial_transactions = get_bep20_token_transfers(
        MONITORED_ADDRESS, USDT_CONTRACT_ADDRESS, BSCSCAN_API_KEY,
        start_block=0, sort_order='desc', offset=1
    )
    if initial_transactions and isinstance(initial_transactions, list) and len(initial_transactions) > 0:
        try:
            last_known_tx_block = int(initial_transactions[0]['blockNumber'])
            last_processed_block = last_known_tx_block
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Started monitoring from block of last known transaction: {last_processed_block} (via BscScan)")
        except (KeyError, ValueError, TypeError) as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error parsing block from initial BscScan transaction: {e}. Defaulting to block 0.")
            last_processed_block = 0
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No past transactions found via BscScan or error. Starting monitoring from block 0.")
        last_processed_block = 0


def monitor_address():
    global processed_tx_hashes
    global last_processed_block

    if BSCSCAN_API_KEY == "YOUR_BSCSCAN_API_KEY" or MONITORED_ADDRESS == "YOUR_BEP20_WALLET_ADDRESS_TO_MONITOR":
        print("ERROR: Please set your BSCSCAN_API_KEY and MONITORED_ADDRESS in the script.")
        return

    # Start the file writer thread
    # daemon=True means the thread will not prevent the main program from exiting.
    # We handle graceful shutdown explicitly with stop_event and join().
    writer_thread = threading.Thread(target=file_writer_thread_func, name="FileWriterThread", daemon=True)
    writer_thread.start()

    initialize_last_processed_block()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Monitoring address: {MONITORED_ADDRESS}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] For incoming USDT (Contract: {USDT_CONTRACT_ADDRESS})")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Refresh interval: {CHECK_INTERVAL_SECONDS}s. Press Ctrl+C to stop.\n")

    monitored_address_lower = MONITORED_ADDRESS.lower()

    try:
        while True: # Main monitoring loop
            try: # Inner try for loop-specific exceptions, allowing cleanup on outer level
                start_block_query = (last_processed_block + 1) if last_processed_block is not None else 0

                transactions = get_bep20_token_transfers(
                    MONITORED_ADDRESS, USDT_CONTRACT_ADDRESS, BSCSCAN_API_KEY,
                    start_block=start_block_query, sort_order='asc', offset=100
                )

                if transactions:
                    current_batch_max_block = 0

                    for tx in transactions:
                        try:
                            tx_hash = tx["hash"]
                            to_address = tx["to"].lower()
                            block_number = int(tx["blockNumber"])

                            if block_number > current_batch_max_block:
                                current_batch_max_block = block_number

                            if to_address == monitored_address_lower and tx_hash not in processed_tx_hashes:
                                value_raw = int(tx["value"])
                                token_decimal = int(tx["tokenDecimal"])
                                amount = value_raw / (10 ** token_decimal)
                                timestamp = int(tx["timeStamp"])
                                tx_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

                                print("-" * 70)
                                print(f"🎉 INCOMING USDT TRANSFER DETECTED at {tx_time} 🎉")
                                print(f"  From:      {tx['from']}")
                                print(f"  To:        {tx['to']}")
                                print(f"  Amount:    {amount:.6f} {tx['tokenSymbol']}") # Print with precision
                                print(f"  Tx Hash:   {tx_hash}")
                                print(f"  Block:     {block_number}")
                                print("-" * 70)
                                
                                # Queue the amount for writing. The string conversion is done here.
                                # Original format was default float to string.
                                write_amount_to_file_queued(f"{amount}") 
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
                                # If specific precision (e.g., 6 decimal places) is desired in the file:
                                # write_amount_to_file_queued(f"{amount:.6f}")

                                processed_tx_hashes.add(tx_hash)
                        except (KeyError, ValueError, TypeError) as e:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error processing a transaction: {tx.get('hash', 'N/A')}, Error: {e}")
                            continue # Skip to next transaction

                    if current_batch_max_block > 0:
                        if last_processed_block is None or current_batch_max_block > last_processed_block:
                            last_processed_block = current_batch_max_block

                time.sleep(CHECK_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                # Re-raise to be caught by the outer try/except KeyboardInterrupt for shutdown
                raise
            except Exception as e:
                # Handle other exceptions that might occur within the main polling logic
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] An unexpected error occurred in the main polling loop: {e}")
                # Sleep for a longer period to avoid rapid error logging if the issue is persistent
                time.sleep(max(CHECK_INTERVAL_SECONDS * 4, 10)) # e.g., sleep at least 10s or 4x interval

    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Monitoring stopped by user. Shutting down...")
    except Exception as e:
        # Catches exceptions from initialization or other parts outside the main while loop
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] A critical unexpected error occurred: {e}. Shutting down...")
    finally:
        # This block executes on any exit from the try block (normal, exception, or KeyboardInterrupt)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initiating shutdown sequence...")
        stop_event.set() # Signal the file writer thread to stop
        
        if writer_thread.is_alive(): # Check if thread was started and is running
            # Wait for the file writer queue to be emptied
            q_size = file_write_queue.qsize()
            if q_size > 0:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Waiting for file writer queue to empty ({q_size} items)...")
            file_write_queue.join() # Blocks until all items in the queue are gotten and processed
            if q_size > 0: # Only print if there were items
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] File writer queue empty.")
            
            # Wait for the file writer thread to terminate
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Waiting for file writer thread to stop...")
            writer_thread.join(timeout=10) # Wait for up to 10 seconds for the thread
            if writer_thread.is_alive():
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] File writer thread did not stop in time.")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] File writer thread stopped.")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] File writer thread was not active or already stopped.")
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Shutdown complete.")


if __name__ == "__main__":
    monitor_address()