import os
import sys
import requests
from google import genai

# 1. Load Secrets from Environment
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
DATASET_ID = os.getenv("APIFY_DATASET_ID")
EARNKARO_ENDPOINT = os.getenv("EARNKARO_ENDPOINT")
EARNKARO_TOKEN = os.getenv("EARNKARO_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PINTEREST_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
BOARD_ID = os.getenv("PINTEREST_BOARD_ID")

HISTORY_FILE = "published_history.txt"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(url):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{url}\n")

def fetch_apify_data():
    url = f"https://api.apify.com/v2/datasets/{DATASET_ID}/items?token={APIFY_TOKEN}"
    res = requests.get(url)
    
    # Catch 404 to provide a cleaner error message
    if res.status_code == 404:
        print(f"\nERROR: Apify Dataset ID '{DATASET_ID}' was not found.")
        print("Free Apify datasets expire over time, or the ID is incorrect.")
        print("Please run your scraper again to get a fresh Dataset ID and update your GitHub Secrets.")
        sys.exit(1)
        
    res.raise_for_status()
    return res.json()

def convert_link_earnkaro(product_url):
    headers = {
        "Authorization": EARNKARO_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {"link": product_url}
    try:
        res = requests.post(EARNKARO_ENDPOINT, json=payload, headers=headers)
        if res.status_code == 200:
            data = res.json()
            return data.get("profit_link", product_url)
    except Exception as e:
        print(f"EarnKaro Conversion Error: {e}")
    return product_url

def generate_seo_copy(title):
    # Updated for new google-genai SDK
    client = genai.Client(api_key=GEMINI_KEY)
    prompt = f"Write a compelling 50-character Pinterest title and a 2-sentence SEO description with hashtags #affiliate #fashion for this item: '{title}'."
    
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=prompt
    )
    
    text = response.text.strip().split("\n")
    
    seo_title = text[0].replace("#", "").strip()[:100]
    seo_desc = " ".join(text[1:]).strip()[:500] if len(text) > 1 else response.text.strip()[:500]
    return seo_title, seo_desc

def create_pinterest_pin(title, description, link, image_url):
    url = "https://api.pinterest.com/v5/pins"
    headers = {
        "Authorization": f"Bearer {PINTEREST_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "board_id": BOARD_ID,
        "title": title,
        "description": description,
        "link": link,
        "media_source": {
            "source_type": "image_url",
            "url": image_url
        }
    }
    res = requests.post(url, json=payload, headers=headers)
    return res.status_code == 201, res.text

def main():
    history = load_history()
    items = fetch_apify_data()
    
    target_item = None
    for item in items:
        prod_url = item.get("url") or item.get("productUrl")
        if prod_url and prod_url not in history:
            target_item = item
            break

    if not target_item:
        print("No new products found in Apify dataset.")
        return

    raw_url = target_item.get("url") or target_item.get("productUrl")
    title = target_item.get("title") or target_item.get("name", "Minimalist Outfit")
    image_url = target_item.get("imageUrl") or target_item.get("image")

    print(f"Processing item: {title}")

    affiliate_link = convert_link_earnkaro(raw_url)
    seo_title, seo_desc = generate_seo_copy(title)

    success, response_text = create_pinterest_pin(seo_title, seo_desc, affiliate_link, image_url)
    
    if success:
        print("Pin successfully created on Pinterest!")
        save_to_history(raw_url)
    else:
        print(f"Failed to post Pin: {response_text}")

if __name__ == "__main__":
    main()
