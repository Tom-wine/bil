"""Main entry point for UMG form submission tool."""
import logging
import os
import sys
import time
import csv
import json
import random
import requests
import urllib3
from typing import List, Dict, Any

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Constants
FORM_URL = "https://forms.umusic-online.com/api/v2/forms/-NL2jY3XB_QvQ4ttcCds/subscriptions"
CLIENT_ID = "6d7b8ddd3a2e30966d462f4f301f7532973fbac7b37404702bb8295ed6aeefe8"
MIN_REQUEST_DELAY = 1.5
MAX_REQUEST_DELAY = 3.0
MAX_RETRIES = 3
RETRY_DELAY_MIN = 1.0
RETRY_DELAY_MAX = 3.0

# Define headers for OPTIONS request
OPTIONS_HEADERS = {
    "Host": "forms.umusic-online.com",
    "Connection": "keep-alive",
    "Accept": "*/*",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "access-control-allow-headers,content-type",
    "Origin": "https://link.fans",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://link.fans/",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
}

# Headers for POST request
POST_HEADERS = {
    "Host": "forms.umusic-online.com",
    "Connection": "keep-alive",
    "sec-ch-ua-platform": "\"Windows\"",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "sec-ch-ua": "\"Chromium\";v=\"136\", \"Google Chrome\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
    "Content-Type": "application/json",
    "sec-ch-ua-mobile": "?0",
    "Access-Control-Allow-Headers": "Content-Type",
    "Origin": "https://link.fans",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://link.fans/",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
}

class Subscriber:
    """Represents a subscriber with all necessary fields."""
    def __init__(self, email, firstname, lastname, country, postcode):
        self.email = email
        self.first_name = firstname
        self.last_name = lastname
        self.country = country
        self.postcode = postcode

def load_subscribers(config_path: str) -> List[Subscriber]:
    """Load subscribers from CSV file."""
    subscribers = []
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Create subscriber
                subscriber = Subscriber(
                    email=row.get("email", "").strip(),
                    firstname=row.get("firstname", "").strip(),
                    lastname=row.get("lastname", "").strip(),
                    country=row.get("country", "").strip().upper() or "US",
                    postcode=row.get("postcode", "").strip()
                )
                
                # Validate subscriber
                if not subscriber.email or "@" not in subscriber.email:
                    logger.warning(f"Skipping invalid email: {subscriber.email}")
                    continue
                
                # Add to list
                subscribers.append(subscriber)
    
    except Exception as e:
        logger.error(f"Error loading subscribers: {e}")
        sys.exit(1)
    
    return subscribers

def submit_form(subscriber: Subscriber) -> Dict[str, Any]:
    """Submit the form for a single subscriber."""
    result = {
        "email": subscriber.email,
        "success": False,
        "status_code": None,
        "error": None
    }
    
    session = requests.Session()
    
    try:
        # Step 1: Send OPTIONS request
        logger.info(f"Sending OPTIONS request for {subscriber.email}")
        options_response = session.options(
            FORM_URL,
            headers=OPTIONS_HEADERS,
            timeout=10,
            verify=False  # Disable SSL verification
        )
        logger.debug(f"OPTIONS response: {options_response.status_code}")
        
        # Small delay between requests (like in the CSV example)
        time.sleep(0.1)
        
        # Step 2: Send POST request
        form_data = {
            "email": subscriber.email,
            "firstName": subscriber.first_name,
            "lastName": subscriber.last_name,
            "locale": "en-US",
            "addressFields": {
                "country": subscriber.country,
                "postal_code": subscriber.postcode
            },
            "clientId": CLIENT_ID
        }
        
        logger.info(f"Sending POST request for {subscriber.email}")
        post_response = session.post(
            FORM_URL,
            headers=POST_HEADERS,
            json=form_data,
            timeout=10,
            verify=False  # Disable SSL verification
        )
        
        result["status_code"] = post_response.status_code
        
        if post_response.status_code in (200, 201, 204):
            logger.info(f"Successfully submitted form for {subscriber.email}")
            result["success"] = True
        else:
            error_msg = f"Failed: {post_response.status_code}"
            if post_response.text:
                try:
                    error_msg += f" - {post_response.json()}"
                except:
                    error_msg += f" - {post_response.text[:100]}"
                    
            logger.error(f"Failed to submit form for {subscriber.email}: {error_msg}")
            result["error"] = error_msg
            
    except Exception as e:
        error_msg = f"Exception: {str(e)}"
        logger.error(f"Exception submitting form for {subscriber.email}: {error_msg}")
        result["error"] = error_msg
        
    return result

def submit_batch(subscribers: List[Subscriber]) -> List[Dict[str, Any]]:
    """Submit forms for all subscribers with delay between requests."""
    results = []
    
    for i, subscriber in enumerate(subscribers):
        logger.info(f"Processing subscriber {i+1}/{len(subscribers)}: {subscriber.email}")
        
        result = submit_form(subscriber)
        results.append(result)
        
        # Add delay between submissions to avoid rate limiting
        if i < len(subscribers) - 1:  # Don't delay after the last one
            delay = random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY)
            logger.info(f"Waiting {delay:.2f} seconds before next submission")
            time.sleep(delay)
    
    return results

def main():
    """Main entry point."""
    logger.info("Starting UMG Form Submission Tool")
    
    # Get the path to config.csv in the current directory
    config_path = os.path.join(os.path.dirname(__file__), "config.csv")
    
    # Load subscribers
    subscribers = load_subscribers(config_path)
    logger.info(f"Loaded {len(subscribers)} subscribers from {config_path}")
    
    if not subscribers:
        logger.error("No valid subscribers found. Exiting.")
        return
    
    # Submit forms
    logger.info("Starting submission process")
    start_time = time.time()
    results = submit_batch(subscribers)
    end_time = time.time()
    
    # Calculate statistics
    successful = sum(1 for r in results if r["success"])
    total = len(results)
    success_rate = (successful / total * 100) if total > 0 else 0
    
    # Log results
    logger.info(f"Submission complete in {end_time - start_time:.2f} seconds")
    logger.info(f"Success rate: {success_rate:.1f}% ({successful}/{total})")
    
    # Log failures if any
    failures = [r for r in results if not r["success"]]
    if failures:
        logger.info(f"Failed submissions: {len(failures)}")
        for failure in failures:
            logger.info(f"  {failure['email']}: {failure['error']}")
    
    logger.info("Process completed.")

if __name__ == "__main__":
    main()
