import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
import requests
import json
import os
import threading
import time
from datetime import datetime
import sys
import gzip
from io import BytesIO
import brotli
import pathlib

# Ensure Windows console supports UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# ✅ Initialize Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'abc123'

# ✅ CORS setup
CORS(app, origins=[
    "https://dashboard-void-shell-i7s0d7g3z-saisuryacharan89s-projects.vercel.app",
    "http://localhost:5173", 
    "http://localhost:3000",
    "https://dashboard-void-shell.vercel.app"
], supports_credentials=True)

# ✅ Socket.IO setup
socketio = SocketIO(
    app,
    cors_allowed_origins=[
        "https://dashboard-void-shell-i7s0d7g3z-saisuryacharan89s-projects.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
        "https://dashboard-void-shell.vercel.app"
    ],
    async_mode="eventlet",
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://dashboard-void-shell-i7s0d7g3z-saisuryacharan89s-projects.vercel.app')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Handle preflight requests
@app.route('/api/<path:path>', methods=['OPTIONS'])
def options_response(path):
    return jsonify({'status': 'ok'}), 200

# =============================================
# SIMPLE IN-MEMORY STORAGE
# =============================================
class SimpleStorage:
    def __init__(self):
        self.data = []
        self.max_entries = 200
    
    def save(self, new_data):
        self.data.append(new_data)
        if len(self.data) > self.max_entries:
            self.data = self.data[-self.max_entries:]
    
    def get_latest(self):
        return self.data[-1] if self.data else {}
    
    def get_all(self):
        return self.data

# Initialize storage
data_storage = SimpleStorage()

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    print(f"✅ Client connected: {request.sid}")
    latest_data = get_latest_data()
    if latest_data:
        socketio.emit('data_update', latest_data, room=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 Client disconnected: {request.sid}")

# Debug endpoint
@app.route("/api/socket-debug")
def socket_debug():
    try:
        rooms = socketio.server.manager.rooms.get('/', {})
        return jsonify({
            "connected_clients": len(rooms),
            "client_ids": list(rooms.keys()),
            "server_time": datetime.now().isoformat(),
            "status": "active"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------
# CONFIG
# -------------------------
PAIR_ADDRESS = None
community_id = None
fetch_interval = 3  # seconds

# Axiom API endpoints (will be updated with PAIR_ADDRESS)
axiom_endpoints = {}

# Axiom API config
axiom_headers = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://axiom.trade",
    "referer": "https://axiom.trade/",
    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
}

axiom_cookies = {
    "auth-access-token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdXRoZW50aWNhdGVkVXNlcklkIjoiMWJiMzA2NzYtMzViZS00ZDQ4LWFlY2QtODZmM2NiMDI3NmY2IiwiaWF0IjoxNzU4MjY3ODU3LCJleHAiOjE3NTgyNjg4MTd9.oWDeaZX2cYKM8PpwW7srMjQE0D3Y1_sqDjDA3jIMGUM",
    "auth-refresh-token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyZWZyZXNoVG9rZW5JZCI6ImE1OTczNTczLTZkNzYtNGFhNy1hN2FjLWM1NTlhMzYyMjkxZSIsImlhdCI6MTc1NzA5MDM2N30.eyAxIxtMo71JhCjX9hQ-nuld1wX9TYJx_gc7lOHoOf0"
}

# X.com Community API config
x_headers = {
    "authority": "x.com",
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
    "content-type": "application/json",
    "cookie": 'd_prefs=MjoxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw; __cuid=d9f285191ba7417b8b0668b4deb3ea1c; g_state={"i_l":0}; kdt=bCVzebeRicfFpAjpz0l2iW5RHQ82C02b3ft88dxy; lang=en; ph_phc_TXdpocbGVeZVm5VJmAsHTMrCofBQu3e0kN8HGMNGTVW_posthog=%7B%22distinct_id%22%3A%220198cd37-7348-7f73-bc78-9aa1915ba1c4%22%2C%22%24sesid%22%3A%5B1755926910651%2C%220198d54d-5634-70fc-ac6f-16f1f0231e84%22%2C1755925272116%5D%7D; dnt=1; guest_id=v1%3A175864037128521710; auth_token=84c79d35cb2a902f89168422691d42a685e810cb; ct0=61f38a6545d11663e819f9f141229a157b4da9742e66762cb54e799b149de7d6ea6d327683a4ab7d5a59ee4f8841dd5395e95aaeefdca7847794a5df46ecb2a24c88a47849d6ef6e4f41e2c110e06232; twid=u%3D1919992237397835776; guest_id_marketing=v1%3A175864037128521710; guest_id_ads=v1%3A175864037128521710; personalization_id="v1_lZ2VF3rbJuzSps45G0TMuA=="',
    "priority": "u=1, i",
    "referer": "https://x.com/i/communities/1972677938530394294",
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "x-client-transaction-id": "/JT89eMYcLDNLe6YaPM0zMP5WJgV9UBedf9He11ulyZPf24gN4PTZXZrScvmJJYcSfOsd/iXKab0eww8vzwq8vFL5Vw+/w",
    "x-csrf-token": "61f38a6545d11663e819f9f141229a157b4da9742e66762cb54e799b149de7d6ea6d327683a4ab7d5a59ee4f8841dd5395e95aaeefdca7847794a5df46ecb2a24c88a47849d6ef6e4f41e2c110e06232",
    "x-twitter-active-user": "yes",
    "x-twitter-auth-type": "OAuth2Session",
    "x-twitter-client-language": "en",
    "x-xp-forwarded-for": "1dff0f5c36061e940f483d608f30ff9548e825fa4494fbea542c194f5a4c33c2926652e15f5439719439b2b8aa7a2aff4c8b5bfa1e0bceb490ae5424c8cf7a3ed3f4efa23a1a5b84c8e39794c85907399b423d72351a550563a62a48ac96d501dc75e06cf2fac269615dc7488ab161c4cc0967e868fd6d492e833b762757d680de466f9e46ec09cd90c0d5e7edb01d42b55ec2c5c9c3ae2c1708435e24735ae02665d83e35111ac4d4daa68fbbafa937414c4913ee575939a4dea4798d9d570c71800ec4d0b60e32ed8eeb4ff717395476c8f22d224f0284c86115a981a6fa061ba561dc9741fc3dd07152bf7458ccabe504b5dc56db63a38b9d58"
}

# X endpoints (will be updated with community_id)
x_urls = {}

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
PRICE_UPDATE_INTERVAL = 600

# Global cache for SOL price
cached_sol_price = {
    "price": 0,
    "last_updated": 0
}

# -------------------------
# FETCH FUNCTIONS
# -------------------------
def fetch_axiom_data():
    if not PAIR_ADDRESS:
        print("❌ No pair address configured")
        return {}
        
    data = {}
    for name, url in axiom_endpoints.items():
        try:
            print(f"🔍 Fetching Axiom {name} from {url}")
            resp = requests.get(url, headers=axiom_headers, cookies=axiom_cookies, timeout=15)
            print(f"✅ Axiom {name} status: {resp.status_code}")
            
            if resp.status_code == 200:
                data[name] = resp.json()
            else:
                print(f"❌ Axiom {name} failed with status: {resp.status_code}")
                data[name] = {}
        except Exception as e:
            print(f"❌ Error fetching Axiom {name}: {e}")
            data[name] = {}
    return data

def update_sol_price():
    while True:
        try:
            print("🔍 Fetching SOL price...")
            response = requests.get(COINGECKO_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                cached_sol_price["price"] = data['solana']['usd']
                cached_sol_price["last_updated"] = time.time()
                print(f"✅ Updated SOL price: ${cached_sol_price['price']}")
            else:
                print(f"❌ SOL price fetch failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Error updating SOL price: {e}")
        time.sleep(PRICE_UPDATE_INTERVAL)

def get_sol_usd_price():
    try:
        resp = requests.get(COINGECKO_URL, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("solana", {}).get("usd", 0)
    except Exception as e:
        print(f"❌ Error fetching SOL price: {e}")
    return 0

def fetch_x_data():
    if not community_id:
        print("❌ No community ID configured")
        return {"timeline": [], "fetchOne": {}}
        
    data = {}
    for name, url in x_urls.items():
        try:
            print(f"🔍 Fetching X {name}...")
            resp = requests.get(url, headers=x_headers, timeout=15)
            print(f"✅ X {name} status: {resp.status_code}")

            if resp.status_code != 200:
                print(f"❌ Non-200 response from {name}: {resp.status_code}")
                data[name] = {"error": "non_200"}
                continue

            # Handle compression
            content = resp.content
            encoding = resp.headers.get("Content-Encoding", "")

            if encoding == "br":
                try:
                    content = brotli.decompress(content)
                except Exception:
                    content = resp.text.encode("utf-8")
            elif encoding == "gzip":
                try:
                    content = gzip.GzipFile(fileobj=BytesIO(content)).read()
                except Exception:
                    content = resp.text.encode("utf-8")

            # Normalize content
            if isinstance(content, bytes):
                try:
                    text = content.decode("utf-8")
                except Exception:
                    text = content.decode("utf-8", errors="ignore")
            else:
                text = str(content)

            # Parse JSON
            try:
                raw = json.loads(text)
            except Exception as e:
                print(f"❌ Non-JSON response from {name}: {str(e)[:100]}")
                data[name] = {"error": "not_json"}
                continue

            # Parse fetchOne
            if name == "fetchOne":
                community = raw.get("data", {}).get("communityResults", {}).get("result", {})
                admin = community.get("admin_results", {}).get("result", {})
                core = admin.get("core", {})
                legacy = admin.get("legacy", {})
                data[name] = {
                    "id": community.get("id_str"),
                    "name": community.get("name"),
                    "description": community.get("description"),
                    "member_count": community.get("member_count"),
                    "admin": {
                        "name": core.get("name"),
                        "screen_name": core.get("screen_name"),
                        "followers": legacy.get("followers_count"),
                        "statuses": legacy.get("statuses_count"),
                        "bio": legacy.get("description"),
                    },
                }

            # Parse timeline
            elif name == "timeline":
                tweets = []
                instructions = (
                    raw.get("data", {})
                       .get("communityResults", {})
                       .get("result", {})
                       .get("ranked_community_timeline", {})
                       .get("timeline", {})
                       .get("instructions", [])
                )
                for ins in instructions:
                    if ins.get("type") != "TimelineAddEntries":
                        continue
                    for entry in ins.get("entries", []):
                        tweet = (
                            entry.get("content", {})
                                 .get("itemContent", {})
                                 .get("tweet_results", {})
                                 .get("result", {})
                        )
                        if not tweet or tweet.get("__typename") != "Tweet":
                            continue
                        legacy = tweet.get("legacy", {})
                        user = (
                            tweet.get("core", {})
                                 .get("user_results", {})
                                 .get("result", {})
                        )
                        user_legacy = user.get("legacy", {})
                        user_core = user.get("core", {})
                        tweets.append({
                            "tweet_id": tweet.get("rest_id"),
                            "text": legacy.get("full_text"),
                            "created_at": legacy.get("created_at"),
                            "author_name": user_core.get("name"),
                            "author_screen": user_core.get("screen_name"),
                            "followers_count": user_legacy.get("followers_count"),
                            "retweet_count": legacy.get("retweet_count"),
                            "reply_count": legacy.get("reply_count"),
                            "favorite_count": legacy.get("favorite_count"),
                            "views": tweet.get("views", {}).get("count", "0"),
                        })
                data[name] = tweets

            else:
                data[name] = raw

        except Exception as e:
            print(f"❌ Error fetching X {name}: {e}")
            data[name] = {"error": str(e)}

    return data

def categorize_wallet_age(funded_at):
    if not funded_at:
        return "unknown"
    
    try:
        funded_date = datetime.fromisoformat(funded_at.replace('Z', '+00:00'))
        current_date = datetime.now(funded_date.tzinfo)
        age_days = (current_date - funded_date).days
        
        if age_days <= 30:
            return "baby"
        elif age_days <= 180:
            return "adult"
        else:
            return "old"
    except:
        return "unknown"

def fetch_all_data():
    print("🔄 Starting data fetch cycle...")
    
    if not PAIR_ADDRESS or not community_id:
        print("❌ Configuration not complete. Skipping fetch.")
        return
        
    try:
        print("📡 Fetching Axiom data...")
        axiom_data = fetch_axiom_data()
        print("📡 Fetching X data...")
        x_data = fetch_x_data()
        
        # Process timeline data
        timeline = x_data.get("timeline", [])
        unique_authors = set()
        author_followers = []
        
        for item in timeline:
            author = item.get("author_screen")
            followers = item.get("followers_count", 0)
            if author and author not in unique_authors:
                unique_authors.add(author)
                author_followers.append({
                    "author": author,
                    "followers": followers,
                    "author_name": item.get("author_name", "")
                })
        
        # Process wallet data
        holders_info = []
        wallet_age_counts = {"baby": 0, "adult": 0, "old": 0}
        total_holders_count = 0
        
        try:
            holder_url = f"https://api6.axiom.trade/holder-data-v3?pairAddress={PAIR_ADDRESS}&onlyTrackedWallets=false"
            print(f"🔍 Fetching holder data from {holder_url}")
            holder_resp = requests.get(holder_url, headers=axiom_headers, cookies=axiom_cookies, timeout=15)
            
            if holder_resp.status_code == 200:
                holder_json = holder_resp.json()
                print(f"✅ Holder data received: {len(holder_json) if isinstance(holder_json, list) else 1} entries")

                if isinstance(holder_json, dict):
                    holder_json = [holder_json]

                if isinstance(holder_json, list):
                    seen_wallets = set()
                    for h in holder_json:
                        if not h or not isinstance(h, dict):
                            continue
                        wallet = h.get("walletAddress")
                        if not wallet or wallet in seen_wallets:
                            continue
                        seen_wallets.add(wallet)

                        funded_at = None
                        wf = h.get("walletFunding")
                        if isinstance(wf, dict):
                            funded_at = wf.get("fundedAt")
                        
                        age_category = categorize_wallet_age(funded_at)
                        wallet_age_counts[age_category] += 1
                        
                        holders_info.append({
                            "walletAddress": wallet,
                            "fundedAt": funded_at,
                            "ageCategory": age_category
                        })

                    token_info = axiom_data.get("token_info", {})
                    total_holders_count = token_info.get("numHolders", len(holder_json))
                    print(f"📊 Wallet stats: {len(holder_json)} wallets, {total_holders_count} total holders")
            else:
                print(f"❌ Holder data fetch failed: {holder_resp.status_code}")
                
        except Exception as e:
            print(f"❌ Error fetching holders: {e}")
            token_info = axiom_data.get("token_info", {})
            total_holders_count = token_info.get("numHolders", 0)
            if total_holders_count > 0:
                wallet_age_counts = {
                    "baby": max(1, int(total_holders_count * 0.4)),
                    "adult": max(1, int(total_holders_count * 0.3)),
                    "old": max(1, int(total_holders_count * 0.3))
                }

        # Process main data
        pair_info = axiom_data.get("pair_info", {})
        token_info = axiom_data.get("token_info", {})
        token_holders = axiom_data.get("token_holders", {})
        pair_stats = axiom_data.get("pair_stats", [])
        first_stats = pair_stats[0] if pair_stats else {}
        sol_price_usd = cached_sol_price["price"]
        
        # Calculate fib levels
        fib62 = 0
        fib50 = 0
        min_mc = 5750
        max_mc = min_mc

        all_data = data_storage.get_all()
        if all_data:
            for entry in all_data:
                mc = entry.get("axiom", {}).get("marketCapUSD", 0)
                if mc > max_mc:
                    max_mc = mc

            fib62 = min_mc + 0.62 * (max_mc - min_mc)
            fib50 = min_mc + 0.50 * (max_mc - min_mc)

        # Extract token metrics
        top10_holders_percent = token_holders.get("top10HoldersPercent", 0) 
        insiders_hold_percent = token_holders.get("insidersHoldPercent", 0) 
        bundlers_hold_percent = token_holders.get("bundlersHoldPercent", 0) 
        snipers_hold_percent = token_holders.get("snipersHoldPercent", 0) 
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "axiom": {
                "tokenAddress": pair_info.get("tokenAddress"),
                "tokenName": pair_info.get("tokenName"),
                "tokenTicker": pair_info.get("tokenTicker"),
                "dexPaid": pair_info.get("dexPaid"),
                "twitter": pair_info.get("twitter"),
                "tokenImage": pair_info.get("tokenImage"),
                "createdAt": pair_info.get("createdAt"),
                "marketCapSol": (first_stats.get("priceSol", 0) * pair_info.get("supply", 0)) if first_stats else None,
                "marketCapUSD": ((first_stats.get("priceSol", 0) * pair_info.get("supply", 0)) * sol_price_usd) if first_stats else None,
                "fibLevel62": fib62,
                "fibLevel50": fib50,
                "volumeSol": first_stats.get("buyVolumeSol", 0) - first_stats.get("sellVolumeSol", 0),
                "volumeUSD": ((first_stats.get("buyVolumeSol", 0) - first_stats.get("sellVolumeSol", 0)) * sol_price_usd),
                "netCount": first_stats.get("buyCount", 0) - first_stats.get("sellCount", 0),
                "buyVolumeSol": first_stats.get("buyVolumeSol", 0),
                "buyVolumeUSD": first_stats.get("buyVolumeSol", 0) * sol_price_usd,
                "sellVolumeSol": first_stats.get("sellVolumeSol", 0),
                "sellVolumeUSD": first_stats.get("sellVolumeSol", 0) * sol_price_usd,
                "buyCount": first_stats.get("buyCount", 0),
                "sellCount": first_stats.get("sellCount", 0),
                "liquiditySol": pair_info.get("initialLiquiditySol"),
                "liquidityUSD": pair_info.get("initialLiquiditySol", 0) * sol_price_usd if pair_info.get("initialLiquiditySol") else 0,
                "numHolders": token_info.get("numHolders"),
                "supply": pair_info.get("supply"),
                "solPriceUSD": sol_price_usd,
                "priceLastUpdated": cached_sol_price["last_updated"],
                "holders": holders_info,
                "walletAgeCounts": wallet_age_counts,
                "totalHolders": total_holders_count,
                "top10HoldersPercent": top10_holders_percent,
                "insidersHoldPercent": insiders_hold_percent,
                "bundlersHoldPercent": bundlers_hold_percent,
                "snipersHoldPercent": snipers_hold_percent
            },
            "x_data": x_data,
            "unique_authors": len(unique_authors),
            "author_followers": author_followers
        }

        # Save to storage
        data_storage.save(result)
        print(f"✅ Data saved at {result['timestamp']}")
        print(f"📊 Market Cap: ${result['axiom'].get('marketCapUSD', 0):,.2f}")
        print(f"👥 Holders: {result['axiom'].get('numHolders', 0)}")
        print(f"🐦 Unique Authors: {len(unique_authors)}")

        # Emit via Socket.IO
        socketio.emit('data_update', result)
        return result

    except Exception as e:
        print(f"❌ Error in fetch_all_data: {e}")
        import traceback
        traceback.print_exc()
        return None

def background_fetcher():
    print("🚀 Starting background fetcher...")
    time.sleep(5)  # Wait for initial configuration
    
    while True:
        try:
            if PAIR_ADDRESS and community_id:  # Only fetch if configured
                result = fetch_all_data()
                if result:
                    print("✅ Background fetch successful")
                else:
                    print("❌ Background fetch failed")
            else:
                print("⏳ Waiting for configuration...")
                
        except Exception as e:
            print(f"❌ Error in background_fetcher: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(fetch_interval)

# -------------------------
# API ROUTES
# -------------------------
def get_latest_data():
    return data_storage.get_latest()

@app.route("/api/data")
def latest_data():
    try:
        latest = data_storage.get_latest()
        if latest:
            return jsonify(latest)
        return jsonify({"error": "No data available", "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/history")
def history_data():
    return jsonify(data_storage.get_all())

@app.route("/api/marketcap")
def marketcap_data():
    try:
        all_data = data_storage.get_all()
        history_data = []
        
        for data in all_data[-100:]:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
                history_data.append({
                    "timestamp": timestamp.isoformat(),
                    "time": timestamp.strftime("%H:%M"),
                    "marketCapUSD": data.get("axiom", {}).get("marketCapUSD", 0),
                    "marketCapSol": data.get("axiom", {}).get("marketCapSol", 0),
                    "volumeUSD": data.get("axiom", {}).get("volumeUSD", 0),
                })
            except:
                continue

        latest_data = get_latest_data()
        current_mc = latest_data.get("axiom", {}).get("marketCapUSD", 0)
        
        return jsonify({
            "current": {
                "marketCapUSD": current_mc,
                "marketCapSol": latest_data.get("axiom", {}).get("marketCapSol", 0),
                "volumeUSD": latest_data.get("axiom", {}).get("volumeUSD", 0),
                "lastUpdated": latest_data.get("timestamp", "")
            },
            "history": history_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tokeninfo")
def token_info_data():
    try:
        latest_data = get_latest_data()
        axiom_data = latest_data.get("axiom", {})
        
        return jsonify({
            "tokenAddress": axiom_data.get("tokenAddress"),
            "tokenName": axiom_data.get("tokenName"),
            "tokenTicker": axiom_data.get("tokenTicker"),
            "twitter": axiom_data.get("twitter"),
            "tokenImage": axiom_data.get("tokenImage"),
            "createdAt": axiom_data.get("createdAt"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/buys-sells")
def buys_sells_data():
    try:
        all_data = data_storage.get_all()
        history_data = []
        
        for data in all_data[-50:]:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
                history_data.append({
                    "timestamp": timestamp.isoformat(),
                    "time": timestamp.strftime("%H:%M"),
                    "buyVolume": data.get("axiom", {}).get("buyVolumeUSD", 0),
                    "sellVolume": data.get("axiom", {}).get("sellVolumeUSD", 0),
                    "netVolume": data.get("axiom", {}).get("volumeUSD", 0),
                    "buyCount": data.get("axiom", {}).get("buyCount", 0),
                    "sellCount": data.get("axiom", {}).get("sellCount", 0)
                })
            except:
                continue

        latest_data = get_latest_data()
        
        return jsonify({
            "current": {
                "buyVolume": latest_data.get("axiom", {}).get("buyVolumeUSD", 0),
                "sellVolume": latest_data.get("axiom", {}).get("sellVolumeUSD", 0),
                "netVolume": latest_data.get("axiom", {}).get("volumeUSD", 0),
                "buyCount": latest_data.get("axiom", {}).get("buyCount", 0),
                "sellCount": latest_data.get("axiom", {}).get("sellCount", 0),
                "lastUpdated": latest_data.get("timestamp", "")
            },
            "history": history_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet-age")
def wallet_age_data():
    try:
        latest_data = get_latest_data()
        wallet_age = latest_data.get("axiom", {}).get("walletAgeCounts", {})
        holders_data = latest_data.get("axiom", {}).get("holders", [])
        
        return jsonify({
            "distribution": wallet_age,
            "totalHolders": latest_data.get("axiom", {}).get("totalHolders", 0),
            "holders": holders_data[:50],
            "lastUpdated": latest_data.get("timestamp", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/social")
def social_data():
    try:
        all_data = data_storage.get_all()
        history_data = []
        
        for data in all_data[-50:]:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
                timeline = data.get("x_data", {}).get("timeline", [])
                
                total_views = sum(int(t.get("views", 0)) for t in timeline if t.get("views"))
                total_likes = sum(t.get("favorite_count", 0) for t in timeline)
                total_retweets = sum(t.get("retweet_count", 0) for t in timeline)
                total_replies = sum(t.get("reply_count", 0) for t in timeline)
                
                history_data.append({
                    "timestamp": timestamp.isoformat(),
                    "time": timestamp.strftime("%H:%M"),
                    "views": total_views,
                    "likes": total_likes,
                    "retweets": total_retweets,
                    "replies": total_replies,
                    "uniqueAuthors": data.get("unique_authors", 0)
                })
            except:
                continue

        latest_data = get_latest_data()
        timeline = latest_data.get("x_data", {}).get("timeline", [])
        
        current_views = sum(int(t.get("views", 0)) for t in timeline if t.get("views"))
        current_likes = sum(t.get("favorite_count", 0) for t in timeline)
        current_retweets = sum(t.get("retweet_count", 0) for t in timeline)
        current_replies = sum(t.get("reply_count", 0) for t in timeline)
        
        return jsonify({
            "current": {
                "views": current_views,
                "likes": current_likes,
                "retweets": current_retweets,
                "replies": current_replies,
                "uniqueAuthors": latest_data.get("unique_authors", 0),
                "memberCount": latest_data.get("x_data", {}).get("fetchOne", {}).get("member_count", 0),
                "lastUpdated": latest_data.get("timestamp", "")
            },
            "history": history_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/metrics")
def metrics_data():
    try:
        latest_data = get_latest_data()
        axiom_data = latest_data.get("axiom", {})
        x_data = latest_data.get("x_data", {})
        
        return jsonify({
            "marketCapUSD": axiom_data.get("marketCapUSD", 0),
            "volumeUSD": axiom_data.get("volumeUSD", 0),
            "holders": axiom_data.get("numHolders", 0),
            "liquidityUSD": axiom_data.get("liquidityUSD", 0),
            "uniqueAuthors": latest_data.get("unique_authors", 0),
            "memberCount": x_data.get("fetchOne", {}).get("member_count", 0),
            "solPrice": axiom_data.get("solPriceUSD", 0),
            "lastUpdated": latest_data.get("timestamp", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/holders")
def holders_data():
    try:
        latest_data = get_latest_data()
        all_data = data_storage.get_all()
        history_data = []
        
        for data in all_data[-100:]:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
                history_data.append({
                    "timestamp": timestamp.isoformat(),
                    "time": timestamp.strftime("%H:%M"),
                    "value": data.get("axiom", {}).get("numHolders", 0),
                    "marketCap": data.get("axiom", {}).get("marketCapUSD", 0),
                    "uniqueAuthors": data.get("unique_authors", 0),
                })
            except Exception as e:
                continue

        current_holders = latest_data.get("axiom", {}).get("numHolders", 0)
        wallet_age_data = latest_data.get("axiom", {}).get("walletAgeCounts", {})
        
        percent_change = 0
        holder_increase = 0
        if len(history_data) >= 2:
            previous_holders = history_data[-2]["value"]
            if previous_holders > 0:
                percent_change = ((current_holders - previous_holders) / previous_holders) * 100
                holder_increase = current_holders - previous_holders

        return jsonify({
            "current": {
                "holderCount": current_holders,
                "percentChange": round(percent_change, 2),
                "holderIncrease": holder_increase,
                "lastUpdated": latest_data.get("timestamp", ""),
                "walletAgeDistribution": wallet_age_data,
                "totalHolders": latest_data.get("axiom", {}).get("totalHolders", 0)
            },
            "history": history_data,
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------
# CONFIGURATION
# -------------------------
dashboard_config = {
    "pair_address": None,
    "community_id": None,
}

def extract_community_id_from_url(twitter_url):
    try:
        if not twitter_url:
            return None
            
        print(f"🔗 Processing Twitter URL: {twitter_url}")
        
        if "communities/" in twitter_url:
            parts = twitter_url.split("communities/")
            if len(parts) > 1:
                community_id = parts[1].split('/')[0].split('?')[0].strip()
                if community_id.isdigit():
                    print(f"✅ Extracted community ID: {community_id}")
                    return community_id
        
        print(f"❌ Could not extract community ID from URL: {twitter_url}")
        return None
        
    except Exception as e:
        print(f"❌ Error extracting community ID from URL: {e}")
        return None

def update_x_urls_with_community_id(community_id):
    global x_urls
    
    x_urls = {
        "timeline": (
            "https://x.com/i/api/graphql/Nyt-88UX4-pPCImZNUl9RQ/CommunityTweetsTimeline"
            f"?variables=%7B%22communityId%22%3A%22{community_id}%22%2C%22count%22%3A20%2C%22displayLocation%22%3A%22Community%22%2C%22rankingMode%22%3A%22Relevance%22%2C%22withCommunity%22%3Atrue%7D"
            "&features=%7B%22rweb_video_screen_enabled%22%3Afalse%2C%22payments_enabled%22%3Afalse%2C%22rweb_xchat_enabled%22%3Afalse%2C%22profile_label_improvements_pcf_label_in_post_enabled%22%3Atrue%2C%22rweb_tipjar_consumption_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Atrue%2C%22creator_subscriptions_tweet_preview_api_enabled%22%3Atrue%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22premium_content_api_read_enabled%22%3Afalse%2C%22communities_web_enable_tweet_community_results_fetch%22%3Atrue%2C%22c9s_tweet_anatomy_moderator_badge_enabled%22%3Atrue%2C%22responsive_web_grok_analyze_button_fetch_trends_enabled%22%3Afalse%2C%22responsive_web_grok_analyze_post_followups_enabled%22%3Atrue%2C%22responsive_web_jetfuel_frame%22%3Atrue%2C%22responsive_web_grok_share_attachment_enabled%22%3Atrue%2C%22articles_preview_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22view_counts_everywhere_api_enabled%22%3Atrue%2C%22longform_notetweets_consumption_enabled%22%3Atrue%2C%22responsive_web_twitter_article_tweet_consumption_enabled%22%3Atrue%2C%22tweet_awards_web_tipping_enabled%22%3Afalse%2C%22responsive_web_grok_show_grok_translated_post%22%3Atrue%2C%22responsive_web_grok_analysis_button_from_backend%22%3Atrue%2C%22creator_subscriptions_quote_tweet_preview_enabled%22%3Afalse%2C%22freedom_of_speech_not_reach_fetch_enabled%22%3Atrue%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Atrue%2C%22longform_notetweets_rich_text_read_enabled%22%3Atrue%2C%22longform_notetweets_inline_media_enabled%22%3Atrue%2C%22responsive_web_grok_image_annotation_enabled%22%3Atrue%2C%22responsive_web_grok_imagine_annotation_enabled%22%3Atrue%2C%22responsive_web_grok_community_note_auto_translation_is_enabled%22%3Afalse%2C%22responsive_web_enhance_cards_enabled%22%3Afalse%7D"
        ),
        "fetchOne": (
            "https://x.com/i/api/graphql/pbuqwPzh0Ynrw8RQY3esYA/CommunitiesFetchOneQuery"
            f"?variables=%7B%22communityId%22%3A%22{community_id}%22%2C%22withDmMuting%22%3Afalse%2C%22withGrokTranslatedBio%22%3Afalse%7D"
            "&features=%7B%22payments_enabled%22%3Afalse%2C%22profile_label_improvements_pcf_label_in_post_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22rweb_tipjar_consumption_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Atrue%7D"
        ),
    }
    
    print(f"🔗 Updated X URLs with community ID: {community_id}")

@app.route("/api/config", methods=["POST"])
def update_config():
    try:
        config = request.get_json()
        print("📩 Incoming config:", config)

        if not config.get("pairAddress"):
            return jsonify({"error": "Missing required field: pairAddress"}), 400

        pair_address = config["pairAddress"]
        user_community_id = config.get("communityId")
        
        # Update global variables
        global PAIR_ADDRESS, community_id, axiom_endpoints
        PAIR_ADDRESS = pair_address
        
        # Update Axiom endpoints
        axiom_endpoints = {
            "pair_info": f"https://api9.axiom.trade/pair-info?pairAddress={PAIR_ADDRESS}",
            "token_info": f"https://api9.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}",
            "pair_stats": f"https://api9.axiom.trade/pair-stats?pairAddress={PAIR_ADDRESS}",
            "token_holders": f"https://api10.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}"
        }

        # Extract community ID if not provided
        twitter_url = None
        if not user_community_id:
            print("🔍 Fetching Axiom data to extract community ID...")
            axiom_data = fetch_axiom_data()
            pair_info = axiom_data.get("pair_info", {})
            twitter_url = pair_info.get("twitter")
            
            if twitter_url and "communities/" in twitter_url:
                extracted_community_id = extract_community_id_from_url(twitter_url)
                if extracted_community_id:
                    user_community_id = extracted_community_id
                    print(f"✅ Extracted community ID: {user_community_id}")
                else:
                    return jsonify({
                        "error": "Could not extract community ID from Twitter URL",
                        "twitterUrl": twitter_url,
                        "suggestion": "Please provide communityId manually"
                    }), 400
            else:
                return jsonify({
                    "error": "No valid Twitter community URL found",
                    "twitterUrl": twitter_url,
                    "suggestion": "Please provide communityId manually"
                }), 400

        community_id = user_community_id
        dashboard_config["pair_address"] = PAIR_ADDRESS
        dashboard_config["community_id"] = community_id

        # Update X endpoints
        update_x_urls_with_community_id(community_id)

        print(f"✅ Configuration updated: {PAIR_ADDRESS}, {community_id}")

        # Initialize price data
        cached_sol_price["price"] = get_sol_usd_price()
        cached_sol_price["last_updated"] = time.time()

        return jsonify({
            "status": "success",
            "message": "Configuration updated and fetching started",
            "config": {
                "pairAddress": PAIR_ADDRESS,
                "communityId": community_id,
                "twitterUrl": twitter_url,
                "autoDiscovered": config.get("communityId") is None
            }
        }), 200

    except Exception as e:
        print(f"❌ Error in config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({
        "pairAddress": dashboard_config["pair_address"],
        "communityId": dashboard_config["community_id"]
    })

@app.route("/api/status")
def status():
    return jsonify({
        "status": "active",
        "started_at": datetime.now().isoformat(),
        "uptime_seconds": 0,
        "socket_connected": True,
        "data_points": len(data_storage.get_all()),
        "pair_address": PAIR_ADDRESS,
        "community_id": community_id
    })

# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    print("🚀 Starting Flask server with Socket.IO...")
    print("💾 Using in-memory storage")
    
    # Start background threads
    threading.Thread(target=update_sol_price, daemon=True).start()
    threading.Thread(target=background_fetcher, daemon=True).start()

    print("✅ Server starting on http://0.0.0.0:5050")
    
    socketio.run(
        app,
        host="0.0.0.0",
        port=5050,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
