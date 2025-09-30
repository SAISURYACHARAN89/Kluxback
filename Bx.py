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

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


# -------------------------
# CONFIG
# -------------------------
PAIR_ADDRESS = "CtFWU65jGuHrLhQHPACrCZEerc31Y75M8tGvbBpzf9w4"
community_id = "1972677938530394294"
BASE_DIR = pathlib.Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
JSON_FILE = DATA_DIR / "pair_filtered.json" 
CONFIG_FILE = DATA_DIR / "dashboard_config.json"
fetch_interval = 3  # seconds

# Create data directory if it doesn't exist
DATA_DIR.mkdir(exist_ok=True)

# Axiom API endpoints
axiom_endpoints = {
    "pair_info": f"https://api9.axiom.trade/pair-info?pairAddress={PAIR_ADDRESS}",
    "token_info": f"https://api9.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}",
    "pair_stats": f"https://api9.axiom.trade/pair-stats?pairAddress={PAIR_ADDRESS}",
    "token_holders": f"https://api10.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}"
}

# Replace Axiom API config
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



# Construct X endpoints (provided in your code earlier)
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


# -------------------------
# FETCH FUNCTIONS
# -------------------------
def fetch_axiom_data():
    data = {}
    for name, url in axiom_endpoints.items():
        try:
            resp = requests.get(url, headers=axiom_headers, cookies=axiom_cookies, timeout=15)
            if resp.status_code == 200:
                data[name] = resp.json()
            else:
                data[name] = {}
        except Exception as e:
            print(f"❌ Error fetching Axiom {name}: {e}")
            data[name] = {}
    return data

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
PRICE_UPDATE_INTERVAL = 600  # 10 minutes in seconds

# Global cache for SOL price
cached_sol_price = {
    "price": 0,
    "last_updated": 0
}
# -------------------------
# MARKET CAP DROP CHECK
# -------------------------
low_mc_start_time = None
peak_mc_seen = 0


def update_sol_price():
    while True:
        try:
            response = requests.get(COINGECKO_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                cached_sol_price["price"] = data['solana']['usd']
                cached_sol_price["last_updated"] = time.time()
                print(f"✅ Updated SOL price: ${cached_sol_price['price']}")
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
    data = {}
    for name, url in x_urls.items():
        try:
            resp = requests.get(url, headers=x_headers, timeout=15)

            # Log status + response preview
            print(f"[{name}] Status {resp.status_code}, Length {len(resp.content)}")

            if resp.status_code != 200:
                print(f"❌ Non-200 response from {name}: {resp.text[:200]}")
                data[name] = {"error": "non_200"}
                continue

            # --- handle compression manually ---
            content = resp.content
            encoding = resp.headers.get("Content-Encoding", "")

            if encoding == "br":  # Brotli
                try:
                    content = brotli.decompress(content)
                except Exception:
                    # maybe already JSON, so fallback to text
                    content = resp.text.encode("utf-8")

            elif encoding == "gzip":  # Gzip
                try:
                    content = gzip.GzipFile(fileobj=BytesIO(content)).read()
                except Exception:
                    # maybe already JSON
                    content = resp.text.encode("utf-8")

            # --- normalize content ---
            if isinstance(content, bytes):
                try:
                    text = content.decode("utf-8")
                except Exception:
                    text = content.decode("utf-8", errors="ignore")
            else:
                text = str(content)

            # --- try parse JSON ---
            try:
                raw = json.loads(text)
            except Exception as e:
                print(f"❌ Non-JSON response from {name}: {str(e)[:100]}")
                print("Preview:", text[:200])
                data[name] = {"error": "not_json"}
                continue

            # --- parse fetchOne ---
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

            # --- parse timeline ---
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

            # --- fallback raw ---
            else:
                data[name] = raw

        except Exception as e:
            print(f"❌ Error fetching X {name}: {e}")
            data[name] = {"error": str(e)}

    return data

# -------------------------
# BACKGROUND FETCHER
# -------------------------
# Add this function to calculate wallet age categories
def categorize_wallet_age(funded_at):
    if not funded_at:
        return "unknown"
    
    try:
        funded_date = datetime.fromisoformat(funded_at.replace('Z', '+00:00'))
        current_date = datetime.now(funded_date.tzinfo)
        age_days = (current_date - funded_date).days
        
        if age_days <= 30:  # 1 month or less
            return "baby"
        elif age_days <= 180:  # 1-6 months
            return "adult"
        else:  # More than 6 months
            return "old"
    except:
        return "unknown"

# Modify the fetch_all_data function to include wallet age analysis
def fetch_all_data():
    while True:  # Retry loop
        try:
            axiom_data = fetch_axiom_data()
            x_data = fetch_x_data()
            
            # Count unique authors and collect followers data
            timeline = x_data.get("timeline", [])
            unique_authors = set()
            author_followers = []
            
            for item in timeline:
                author = item.get("author_screen")
                followers = item.get("followers_count", 0)
                if author:
                    unique_authors.add(author)
                    author_followers.append({
                        "author": author,
                        "followers": followers,
                        "author_name": item.get("author_name", "")
                    })
            
            # Analyze wallet ages for bubble chart - FIXED LOGIC
            holders_info = []
            wallet_age_counts = {"baby": 0, "adult": 0, "old": 0}
            total_holders_count = 0
            
            try:
                holder_url = f"https://api6.axiom.trade/holder-data-v3?pairAddress={PAIR_ADDRESS}&onlyTrackedWallets=false"
                holder_resp = requests.get(holder_url, headers=axiom_headers, cookies=axiom_cookies, timeout=15)
                if holder_resp.status_code == 200:
                    holder_json = holder_resp.json()

                    if isinstance(holder_json, dict):
                        holder_json = [holder_json]

                    if isinstance(holder_json, list):
                        for h in holder_json:
                            if not h or not isinstance(h, dict):
                                continue
                            wallet = h.get("walletAddress")
                            funded_at = None
                            wf = h.get("walletFunding")
                            if isinstance(wf, dict):
                                funded_at = wf.get("fundedAt")
                            
                            # Categorize wallet age
                            age_category = categorize_wallet_age(funded_at)
                            wallet_age_counts[age_category] += 1
                            
                            holders_info.append({
                                "walletAddress": wallet,
                                "fundedAt": funded_at,
                                "ageCategory": age_category
                            })
                        
                        # Get total holders count from token_info
                        token_info = axiom_data.get("token_info", {})
                        total_holders_count = token_info.get("numHolders", len(holder_json))
                        
                        print(f"📊 Wallet stats: Found {len(holder_json)} wallets with age data, Total holders: {total_holders_count}")
                        
            except Exception as e:
                print(f"❌ Error fetching holders fundedAt: {e}")
                # If we can't get holder data, use fallback distribution based on typical patterns
                token_info = axiom_data.get("token_info", {})
                total_holders_count = token_info.get("numHolders", 0)
                if total_holders_count > 0:
                    # Estimate distribution (adjust these ratios based on your typical data)
                    wallet_age_counts = {
                        "baby": max(1, int(total_holders_count * 0.4)),  # 40% new wallets
                        "adult": max(1, int(total_holders_count * 0.3)),  # 30% medium age
                        "old": max(1, int(total_holders_count * 0.3))     # 30% old wallets
                    }

            # If we have very few wallets but many total holders, scale up the counts
            actual_wallets_count = len(holders_info)
            if total_holders_count > actual_wallets_count > 0:
                # Scale up the wallet age counts proportionally
                scale_factor = total_holders_count / actual_wallets_count
                wallet_age_counts = {
                    "baby": max(1, int(wallet_age_counts["baby"] * scale_factor)),
                    "adult": max(1, int(wallet_age_counts["adult"] * scale_factor)),
                    "old": max(1, int(wallet_age_counts["old"] * scale_factor))
                }
                print(f"⚖️ Scaled wallet counts: {wallet_age_counts} (scale factor: {scale_factor:.2f})")

            # Rest of your existing data processing...
            pair_info = axiom_data.get("pair_info", {})
            token_info = axiom_data.get("token_info", {})
            token_holders = axiom_data.get("token_holders", {})
            pair_stats = axiom_data.get("pair_stats", [])
            first_stats = pair_stats[0] if pair_stats else {}
            sol_price_usd = cached_sol_price["price"]
            
            # Calculate fib levels (your existing code)
            fib62 = 0
            fib50 = 0
            min_mc = 5750
            max_mc = min_mc

            if os.path.exists(JSON_FILE):
                try:
                    with open(JSON_FILE, "r", encoding="utf-8") as f:
                        max_mc = min_mc
                        for line in f:
                            try:
                                entry = json.loads(line)
                                mc = entry.get("axiom", {}).get("marketCapUSD", 0)
                                if mc > max_mc:
                                    max_mc = mc
                            except:
                                continue

                    fib62 = min_mc + 0.62 * (max_mc - min_mc)
                    fib50 = min_mc + 0.50 * (max_mc - min_mc)
                except Exception as e:
                    print(f"❌ Error calculating fibLevel62: {e}")

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
                    "totalHolders": total_holders_count,  # Add total for reference
                    "top10HoldersPercent": top10_holders_percent,
                    "insidersHoldPercent": insiders_hold_percent,
                    "bundlersHoldPercent": bundlers_hold_percent,
                    "snipersHoldPercent": snipers_hold_percent
                },
                "x_data": x_data,
                "unique_authors": len(unique_authors),
                "author_followers": author_followers
            }

            # Save and emit
            # Save with timestamp as filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            daily_file = DATA_DIR / f"data_{timestamp[:8]}.json"
            
            # Save to main file
            with open(JSON_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
            
            # Also save to daily file
            with open(daily_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

            # Keep only last 7 days of daily files
            cleanup_old_files()

            socketio.emit('data_update', result)

            print(f"✅ Emitted and saved data at {result['timestamp']}")
            print(f"👥 Wallet Age Distribution: {wallet_age_counts} (Total: {total_holders_count})")
            print(f"📊 Author Followers: {[f['followers'] for f in author_followers]}")

            break
        except Exception as e:
            print(f"❌ Fetch failed, retrying in 5s: {e}")
            time.sleep(5)
def fetch_all_viewData():
    x_data = fetch_x_data()
    timeline = x_data.get("timeline", [])
    total_views = 0
    unique_authors = set()  # Changed from unique_tweets

    for t in timeline:
        # count views
        views = t.get("views", 0)
        try:
            views_int = int(views)
            total_views += views_int
        except (ValueError, TypeError):
            pass

        # track unique authors
        author = t.get("author_screen")
        if author:
            unique_authors.add(author)

    return {
        "total_views": total_views,
        "unique_authors": len(unique_authors)  # Changed from unique_count
    }
def check_exit_condition(curr_mc):
    global low_mc_start_time, peak_mc_seen

    # Track peak market cap seen so far
    if curr_mc > peak_mc_seen:
        peak_mc_seen = curr_mc

    # Conditions
    cond1 = curr_mc < 6500
    cond2 = (peak_mc_seen > 0 and curr_mc < 0.1 * peak_mc_seen)

    if cond1 or cond2:
        if low_mc_start_time is None:
            low_mc_start_time = time.time()
        else:
            elapsed = time.time() - low_mc_start_time
            if elapsed >= 180:  # 3 minutes
                print(f"❌ MarketCapUSD drop detected for 3 minutes continuously. Exiting... "
                      f"(curr_mc={curr_mc}, peak_mc={peak_mc_seen})")
                os._exit(1)  # force exit immediately
    else:
        low_mc_start_time = None  # reset if safe

def background_fetcher():
    while True:
        result = fetch_all_data()
        if result and "axiom" in result:
            curr_mc = result["axiom"].get("marketCapUSD", 0) or 0
            check_exit_condition(curr_mc)

        view_stats = fetch_all_viewData()
        print(f"📊 Timeline Stats → Views: {view_stats['total_views']} | Unique Authors: {view_stats['unique_authors']}")
        time.sleep(fetch_interval)


# -------------------------
# API ROUTES
# -------------------------
@app.route("/api/data")
def latest_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "rb") as f:
            try:
                f.seek(-2, os.SEEK_END)
                while f.read(1) != b"\n":
                    f.seek(-2, os.SEEK_CUR)
            except OSError:
                f.seek(0)
            last_line = f.readline().decode().strip()
            if last_line:
                return jsonify(json.loads(last_line))
    return jsonify({"error": "No data available"})

@app.route("/api/history")
def history_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_50 = [json.loads(line) for line in lines[-50:]]
            return jsonify(last_50)
    return jsonify([])
@app.route("/api/status")
def status():
    if not server_status["is_configured"]:
        return jsonify({
            "status": "waiting",
            "message": "Waiting for configuration"
        })
    elif not server_status["is_running"]:
        return jsonify({
            "status": "stopped",
            "error": "Backend not running"
        }), 503
    
    return jsonify({
        "status": "active",
        "started_at": server_status["start_time"],
        "uptime_seconds": (datetime.now() - datetime.fromisoformat(server_status["start_time"])).total_seconds()
    })

# -------------------------
# CONFIGURATION
# -------------------------
# Add new config storage
dashboard_config = {
    "pair_address": None,
    "community_id": None,
    "x_headers": None
}

CONFIG_FILE = "dashboard_config.json"

def load_saved_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
                dashboard_config.update(saved_config)
                return True
    except Exception as e:
        print(f"Error loading config: {e}")
    return False

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

# Add new route to handle configuration
@app.route("/api/config", methods=["POST"])
def update_config():
    try:
        config = request.json
        
        # Required fields
        if not config.get("pairAddress") or not config.get("communityId"):
            return jsonify({"error": "Missing required fields"}), 400

        # Update config with required fields
        global PAIR_ADDRESS, community_id, axiom_endpoints
        PAIR_ADDRESS = config["pairAddress"]
        community_id = config["communityId"]
        
        # Update dashboard config
        dashboard_config["pair_address"] = PAIR_ADDRESS
        dashboard_config["community_id"] = community_id

        # Only update x_headers if provided, otherwise keep existing ones
        if config.get("headers"):
            global x_headers
            x_headers = config["headers"]
            dashboard_config["x_headers"] = x_headers
        
        # Update endpoints with new pair address
        axiom_endpoints = {
            "pair_info": f"https://api9.axiom.trade/pair-info?pairAddress={PAIR_ADDRESS}",
            "token_info": f"https://api9.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}",
            "pair_stats": f"https://api9.axiom.trade/pair-stats?pairAddress={PAIR_ADDRESS}",
            "token_holders": f"https://api10.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}"
        }
        
        if save_config(dashboard_config):
            # Start data fetching only after configuration
            if not server_status["is_running"]:
                try:
                    # Initialize price data
                    cached_sol_price["price"] = get_sol_usd_price()
                    cached_sol_price["last_updated"] = time.time()
                    
                    # Start background threads
                    threading.Thread(target=update_sol_price, daemon=True).start()
                    threading.Thread(target=background_fetcher, daemon=True).start()
                    
                    server_status["is_running"] = True
                    server_status["is_configured"] = True
                    server_status["start_time"] = datetime.now().isoformat()
                except Exception as e:
                    return jsonify({
                        "status": "error",
                        "message": f"Failed to start fetching: {str(e)}"
                    }), 500

            return jsonify({
                "status": "success",
                "message": "Configuration updated and fetching started"
            }), 200
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
            
    except Exception as e:
        print(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500

# Modify status endpoint to include configuration state

# Add config endpoint to get current config
@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({
        "pairAddress": dashboard_config["pair_address"],
        "communityId": dashboard_config["community_id"]
    })

# Add download endpoint
@app.route("/api/download")
def download_data():
    if os.path.exists(JSON_FILE):
        return send_file(
            JSON_FILE,
            mimetype='application/json',
            as_attachment=True,
            download_name='trading_data.json'
        )
    return jsonify({"error": "No data available"}), 404

# Add cleanup function
def cleanup_old_files():
    # Keep only last 7 days of data files
    daily_files = sorted(DATA_DIR.glob("data_*.json"))
    if len(daily_files) > 7:
        for old_file in daily_files[:-7]:
            old_file.unlink()

# Add startup status tracking
server_status = {
    "is_running": False,
    "start_time": None,
    "is_configured": False  # New flag to track if config is set
}

# Remove the /start-backend route as it's no longer needed
# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    print("🚀 Starting Dashboard Server...")
    print("⏳ Waiting for configuration...")
    
    # Load saved config if exists but don't start fetching
    if load_saved_config():
        print("✅ Loaded saved configuration")
        PAIR_ADDRESS = dashboard_config["pair_address"]
        community_id = dashboard_config["community_id"]
        
        # Update endpoints
        axiom_endpoints = {
            "pair_info": f"https://api9.axiom.trade/pair-info?pairAddress={PAIR_ADDRESS}",
            "token_info": f"https://api9.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}",
            "pair_stats": f"https://api9.axiom.trade/pair-stats?pairAddress={PAIR_ADDRESS}",
            "token_holders": f"https://api10.axiom.trade/token-info?pairAddress={PAIR_ADDRESS}"
        }
    
    # Just start the server and wait for configuration
    port = int(os.environ.get("PORT", 5050))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
