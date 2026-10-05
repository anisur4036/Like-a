import json
import time
import asyncio
import httpx
import subprocess
import os

# --- Settings ---
# ✅ নতুন JWT API URL (OB55)
API_URL = "https://shawon-jwt-ob55.vercel.app/token"
# Number of retries
MAX_RETRIES = 2 
# Delay between retries (in seconds)
RETRY_DELAY = 60 
# How many accounts to process at once (Batch Size)
BATCH_SIZE = 30 

# --- Token Generation Logic ---

async def generate_single_token(client, uid: str, password: str):
    """Generates a token from the API."""
    try:
        url = f"{API_URL}?uid={uid}&password={password}"
        resp = await client.get(url, timeout=30)
        
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"Error for UID {uid}: {e}")
        return None

async def process_account_with_retry(client, account, index):
    """Processes an account with retry logic."""
    uid = account['uid']
    password = account['password']
    
    for attempt in range(MAX_RETRIES):
        token_data = await generate_single_token(client, uid, password)
        
        if token_data and "token" in token_data:
            return {
                "status": "success",
                "account": account,
                "token_data": token_data,
                "index": index
            }
        
        if attempt < MAX_RETRIES - 1:
            print(f"UID #{index + 1} {uid} - Failed. Retrying in {RETRY_DELAY} seconds...")
            await asyncio.sleep(RETRY_DELAY)
            
    return {
        "status": "failed",
        "account": account,
        "index": index
    }

async def main():
    """Main function that runs the entire process."""
    input_file = "accounts.json"
    
    if not os.path.exists(input_file):
        print(f"⚠️ '{input_file}' not found! Creating an empty file...")
        with open(input_file, 'w') as f:
            json.dump([], f)
            
    try:
        with open(input_file) as f:
            accounts = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: '{input_file}' is not a valid JSON or is empty.")
        return

    print(f"🚀 Starting token generation for {len(accounts)} accounts...")
    start_time = time.time()
    
    result = {'IND': [], 'BR': [], 'BD': []}
    failed_accounts = []

    if accounts:
        async with httpx.AsyncClient() as client:
            all_responses = []
            
            for i in range(0, len(accounts), BATCH_SIZE):
                batch = accounts[i:i + BATCH_SIZE]
                print(f"\n🔄 Processing batch: {i + 1} to {i + len(batch)}...")
                
                tasks = [process_account_with_retry(client, acc, i + j) for j, acc in enumerate(batch)]
                
                batch_responses = await asyncio.gather(*tasks)
                all_responses.extend(batch_responses)
                
                if i + BATCH_SIZE < len(accounts):
                    await asyncio.sleep(0.5)

            print("\n✅ All batches processed. Saving data...")
            for res in all_responses:
                if res['status'] == 'success':
                    account = res['account']
                    token_data = res['token_data']
                    
                    raw_region = token_data.get('region', token_data.get('notiRegion', ''))
                    region_code = (raw_region if raw_region else '').upper()
                    
                    if region_code == 'IND':
                        region = 'IND'
                    elif region_code in {'BR', 'US', 'SAC', 'NA'}:
                        region = 'BR'
                    else:
                        region = 'BD'
                    
                    result[region].append({
                        'uid': account['uid'],
                        'token': token_data['token']
                    })
                    print(f"✅ UID #{res['index'] + 1} {account['uid']} - Token generated ({region})")
                else:
                    failed_accounts.append(res['account']['uid'])
                    print(f"❌ UID #{res['index'] + 1} {res['account']['uid']} - Failed to generate token.")

    for region in ['IND', 'BR', 'BD']:
        tokens = result[region]
        filename = f'token_{region.lower()}.json'
        
        with open(filename, 'w') as f:
            json.dump(tokens, f, indent=2)
        print(f"💾 {len(tokens)} tokens saved in {filename}.")

    print("\n🚀 Preparing files for GitHub upload (Git Add)...")
    try:
        subprocess.run(["git", "add", "token_ind.json", "token_br.json", "token_bd.json"], check=True)
        print("✅ Files successfully added to Git! Your Action will now upload them easily.")
    except Exception as e:
        print(f"⚠️ Error adding to Git (ignore this if running on a local PC): {e}")

    total_time = time.time() - start_time
    print("\n" + "="*40)
    print("✨ Process completed! ✨")
    print(f"⏱️ Total time: {total_time:.2f} seconds")
    print(f" Total accounts: {len(accounts)}")
    print(f"✔️ Successful tokens: {len(accounts) - len(failed_accounts)}")
    print(f"❌ Failed accounts: {len(failed_accounts)}")
    if failed_accounts:
        print(f"   -> Failed UIDs: {', '.join(failed_accounts)}")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(main())