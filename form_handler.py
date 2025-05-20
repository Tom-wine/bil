"""Form submission handler module."""
import time
import logging
import json
import concurrent.futures
from random import uniform
from typing import Dict, List, Optional, Tuple
import requests
import urllib3
from collections import defaultdict
import threading

from config import (
    MAX_RETRIES, RETRY_DELAY_MIN, RETRY_DELAY_MAX, 
    MIN_REQUEST_DELAY, MAX_REQUEST_DELAY,
    CLIENT_ID, FORM_URL
)
from models import Subscriber, SubmissionResult
from proxies import Proxy, ProxyManager

# Suppress insecure connection warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Define headers for OPTIONS request exactly as specified
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


class BatchSubmitter:
    """Handles batch submission of forms."""
    
    def __init__(self, proxy_manager: Optional[ProxyManager] = None, max_threads: int = 1):
        self.proxy_manager = proxy_manager
        self.max_threads = max(1, max_threads)
        self.stats = {
            "total": 0,
            "success": 0,
            "failure": 0,
            "errors": defaultdict(int)
        }
        self._stats_lock = threading.Lock()
    
    def submit_batch(self, subscribers: List[Subscriber]) -> List[SubmissionResult]:
        results = []
        if self.max_threads > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                futures = []
                for subscriber in subscribers:
                    proxy = None
                    if self.proxy_manager:
                        proxy = self.proxy_manager.get_next_proxy(subscriber.country)
                    futures.append(executor.submit(self.submit_form, subscriber, proxy))
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        self._update_stats(result)
                    except Exception as e:
                        logger.error(f"Error in worker thread: {str(e)}")
        else:
            for subscriber in subscribers:
                proxy = None
                if self.proxy_manager:
                    proxy = self.proxy_manager.get_next_proxy(subscriber.country)
                try:
                    result = self.submit_form(subscriber, proxy)
                    results.append(result)
                    self._update_stats(result)
                except Exception as e:
                    logger.error(f"Error submitting form: {str(e)}")
                    error_result = SubmissionResult(subscriber=subscriber, success=False)
                    error_result.error_message = str(e)
                    results.append(error_result)
                    self._update_stats(error_result)
                if subscriber != subscribers[-1]:
                    time.sleep(uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY))
        return results
    
    def submit_form(self, subscriber: Subscriber, proxy: Optional[Proxy] = None) -> SubmissionResult:
        """Submit a form with the given subscriber information."""
        # Check if subscriber is None
        if subscriber is None:
            logger.error("Received None subscriber")
            empty_subscriber = Subscriber(email="unknown", first_name="", last_name="", country="", postcode="")
            result = SubmissionResult(subscriber=empty_subscriber, success=False)
            result.error_message = "Subscriber is None"
            return result
        
        logger.info(f"Submitting form for {subscriber.email}")
        
        # Prepare result object
        result = SubmissionResult(subscriber=subscriber, success=False)
        
        # Prepare proxy for requests
        proxy_dict = None
        if proxy:
            proxy_dict = proxy.proxy_dict
        
        # Add retry handling
        for attempt in range(MAX_RETRIES):
            try:
                
                session = requests.Session()
                
                # First make OPTIONS request using raw requests without any data
                options_response = session.options(
                    FORM_URL,
                    headers=OPTIONS_HEADERS,
                    proxies=proxy_dict,
                    timeout=10,
                    verify=False
                )
                
                logger.debug(f"OPTIONS response: {options_response.status_code} {options_response.reason}")
                
                # Brief pause between OPTIONS and POST
                time.sleep(uniform(0.5, 1.5))
                
                # Prepare payload for POST request
                payload = {
                    "client_id": CLIENT_ID,
                    "optins": ["-MxcmJpUtUKsxARFLAz2"],
                    "consumer": {
                        "consumer_country": subscriber.country or "FR",
                        "email": subscriber.email,
                        "postcode": subscriber.postcode or ""
                    },
                    "metadata": {
                        "acquisition_sys": "6d697261",
                        "campaign_id": "ad41fa4adbff455fa967a6c62433566d",
                        "host_url": "https://link.fans/hmhastoursignup"
                    }
                }
                
                # Make the POST request with the JSON payload
                response = session.post(
                    FORM_URL,
                    headers=POST_HEADERS,
                    json=payload,  # This will automatically serialize to JSON
                    proxies=proxy_dict,
                    verify=False,
                    timeout=30
                )
                
                # Debug the response
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                logger.debug(f"Response body: {response.text}")

                if response.status_code in (200, 201):
                    result.success = True
                    try:
                        result.response_data = response.json()
                    except Exception:
                        result.response_data = {"raw": response.text}
                    return result
                else:
                    result.error_message = f"HTTP {response.status_code}: {response.text}"
                    if response.status_code in (429, 503):
                        time.sleep(uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX) * (attempt + 1))
                        continue
                    if 400 <= response.status_code < 500:
                        return result
                    time.sleep(uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX) * (attempt + 1))
            except Exception as e:
                logger.error(f"Error submitting form for {subscriber.email}: {str(e)}")
                result.error_message = str(e)
                if attempt < MAX_RETRIES - 1:
                    delay = uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX) * (attempt + 1)
                    logger.info(f"Retrying in {delay:.1f} seconds (attempt {attempt+1}/{MAX_RETRIES})")
                    time.sleep(delay)
        
        return result

    def _update_stats(self, result: SubmissionResult) -> None:
        """Update submission statistics (thread-safe)."""
        with self._stats_lock:
            self.stats["total"] += 1
            if result.success:
                self.stats["success"] += 1
            else:
                self.stats["failure"] += 1
                err = result.error_message or "unknown"
                key = ("rate_limit" if "429" in err else
                       "forbidden" if "403" in err else
                       "timeout" if "timeout" in err.lower() else
                       "connection" if "connection" in err.lower() else err[:30])
                self.stats["errors"][key] += 1

    def get_stats(self) -> Dict:
        """Get current submission statistics."""
        with self._stats_lock:
            return self.stats.copy()
            
    def log_stats(self) -> None:
        """Log current submission statistics."""
        stats = self.get_stats()
        logger.info(f"Submission stats: {stats['success']}/{stats['total']} successful ({stats['failure']} failed)")
        if stats["errors"]:
            logger.info("Error breakdown:")
            for err, count in sorted(stats["errors"].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {err}: {count}")