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

# Define a HeaderOrderKey class for compatibility
class HeaderOrderKey:
    pass

http = type('http', (), {'HeaderOrderKey': HeaderOrderKey})

# Headers for OPTIONS request
OPTIONS_HEADERS = {
    "Host":        {"forms.umusic-online.com"},
    "Connection":        {"keep-alive"},
    "Accept":        {"*/*"},
    "Access-Control-Request-Method":        {"POST"},
    "Access-Control-Request-Headers":        {"access-control-allow-headers,content-type"},
    "Origin":        {"https://link.fans"},
    "User-Agent":        {"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"},
    "Sec-Fetch-Mode":        {"cors"},
    "Sec-Fetch-Site":        {"cross-site"},
    "Sec-Fetch-Dest":        {"empty"},
    "Referer":        {"https://link.fans/"},
    "Accept-Encoding":        {"gzip, deflate, br, zstd"},
    "Accept-Language":        {"fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"},
    http.HeaderOrderKey: { "Host", "Connection", "Accept", "Access-Control-Request-Method", "Access-Control-Request-Headers", "Origin", "User-Agent", "Sec-Fetch-Mode", "Sec-Fetch-Site", "Sec-Fetch-Dest", "Referer", "Accept-Encoding", "Accept-Language" },
}

# Headers for POST request
POST_HEADERS = {
    "Host":        {"forms.umusic-online.com"},
    "Connection":        {"keep-alive"},
    "sec-ch-ua-platform":        {"\"Windows\""},
    "User-Agent":        {"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"},
    "Accept":        {"application/json, text/plain, */*"},
    "sec-ch-ua":        {"\"Chromium\";v=\"136\", \"Google Chrome\";v=\"136\", \"Not.A/Brand\";v=\"99\""},
    "Content-Type":        {"application/json"},
    "sec-ch-ua-mobile":        {"?0"},
    "Access-Control-Allow-Headers":        {"Content-Type"},
    "Origin":        {"https://link.fans"},
    "Sec-Fetch-Site":        {"cross-site"},
    "Sec-Fetch-Mode":        {"cors"},
    "Sec-Fetch-Dest":        {"empty"},
    "Referer":        {"https://link.fans/"},
    "Accept-Encoding":        {"gzip, deflate, br, zstd"},
    "Accept-Language":        {"fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"},
    http.HeaderOrderKey: { "Host", "Connection", "sec-ch-ua-platform", "User-Agent", "Accept", "sec-ch-ua", "Content-Type", "sec-ch-ua-mobile", "Access-Control-Allow-Headers", "Origin", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Referer", "Accept-Encoding", "Accept-Language" },
}

def convert_headers(headers_special_format):
    """Convert headers from special format to requests-compatible format."""
    # Extract only the actual headers, skipping the header order key
    result = {}
    for key, value in headers_special_format.items():
        if key != http.HeaderOrderKey:
            # Extract the string value from the set/dictionary
            result[key] = next(iter(value))
    return result

class BatchSubmitter:
    """Handles batch submission of forms."""
    
    def __init__(self, proxy_manager: Optional[ProxyManager] = None, max_threads: int = 1):
        """Initialize batch submitter."""
        self.proxy_manager = proxy_manager
        self.max_threads = max(1, max_threads)  # Ensure at least 1 thread
        self.stats = {
            "total": 0,
            "success": 0,
            "failure": 0,
            "errors": defaultdict(int)
        }
        self._stats_lock = threading.Lock()  # For thread safety
    
    def submit_batch(self, subscribers: List[Subscriber]) -> List[SubmissionResult]:
        """Submit a batch of forms."""
        results = []
        
        # Use ThreadPoolExecutor for parallel submission if enabled
        if self.max_threads > 1:
            logger.info(f"Using thread pool with {self.max_threads} threads")
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                # Create list of tasks
                futures = []
                for subscriber in subscribers:
                    # Get proxy if using proxies
                    proxy = None
                    if self.proxy_manager:
                        proxy = self.proxy_manager.get_next_proxy(subscriber.country)
                    
                    # Submit task
                    future = executor.submit(self.submit_form, subscriber, proxy)
                    futures.append(future)
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        self._update_stats(result)
                    except Exception as e:
                        logger.error(f"Error in worker thread: {str(e)}")
        else:
            # Single-threaded mode
            for subscriber in subscribers:
                # Get proxy if using proxies
                proxy = None
                if self.proxy_manager:
                    proxy = self.proxy_manager.get_next_proxy(subscriber.country)
                
                # Submit form
                try:
                    result = self.submit_form(subscriber, proxy)
                    results.append(result)
                    self._update_stats(result)
                except Exception as e:
                    logger.error(f"Error submitting form: {str(e)}")
                    # Create a result object for the error
                    error_result = SubmissionResult(subscriber=subscriber, success=False)
                    error_result.error = str(e)
                    results.append(error_result)
                    self._update_stats(error_result)
                
                # Add delay before next submission
                if subscriber != subscribers[-1]:  # Don't delay after last submission
                    delay = uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY)
                    time.sleep(delay)
        
        return results
    
    def submit_form(self, subscriber: Subscriber, proxy: Optional[Proxy] = None) -> SubmissionResult:
        """Submit a form with the given subscriber information."""
        # Check if subscriber is None
        if subscriber is None:
            logger.error("Received None subscriber")
            empty_subscriber = Subscriber(email="unknown", first_name="", last_name="", country="", postcode="")
            result = SubmissionResult(subscriber=empty_subscriber, success=False)
            result.error = "Subscriber is None"
            return result
        
        logger.info(f"Submitting form for {subscriber.email}")
        
        # Prepare result object
        result = SubmissionResult(subscriber=subscriber, success=False)  # Initialize with success=False
        
        # Prepare proxy for requests
        proxy_dict = None
        if proxy:
            proxy_dict = proxy.proxy_dict
        
        # Set up request session
        session = requests.Session()
        
        # Convert headers to requests-compatible format
        options_headers = convert_headers(OPTIONS_HEADERS)
        post_headers = convert_headers(POST_HEADERS)
        
        # Add retry handling
        for attempt in range(MAX_RETRIES):
            try:
                # First make OPTIONS request  
                options_response = session.options(
                    FORM_URL,
                    headers=options_headers,  # Use converted headers
                    proxies=proxy_dict,
                    timeout=10,
                    verify=False
                )
                
                # Brief pause between OPTIONS and POST
                time.sleep(uniform(0.5, 1.5))
                
                # Prepare payload (form data) with the exact structure provided
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
                
                # Debug the payload
                logger.debug(f"Sending payload: {json.dumps(payload)}")
                
                # Make the POST request
                response = session.post(
                    FORM_URL,
                    headers=post_headers,  # Use converted headers
                    json=payload,  # This will properly serialize the dict to JSON
                    proxies=proxy_dict,
                    verify=False,
                    timeout=30
                )
                
                # Debug the response
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                logger.debug(f"Response body: {response.text}")
                
                # Process response
                if response.status_code in (200, 201):
                    # Success
                    logger.info(f"Form submitted successfully for {subscriber.email}")
                    result.success = True
                    try:
                        result.response_data = response.json()
                    except:
                        result.response_data = {"raw": response.text}
                    return result
                else:
                    # Request failed with response
                    logger.warning(f"Submission failed with status {response.status_code}: {response.text}")
                    result.error = f"HTTP {response.status_code}: {response.text}"
                    
                    # If rate limited, definitely retry
                    if response.status_code in (429, 503):
                        delay = uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX) * (attempt + 1)
                        logger.info(f"Rate limited. Retrying in {delay:.1f} seconds (attempt {attempt+1}/{MAX_RETRIES})")
                        time.sleep(delay)
                        continue
                    
                    # For client errors, don't retry
                    if response.status_code >= 400 and response.status_code < 500:
                        return result
                    
                    # For other errors, retry with backoff
                    delay = uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX) * (attempt + 1)
                    logger.info(f"Retrying in {delay:.1f} seconds (attempt {attempt+1}/{MAX_RETRIES})")
                    time.sleep(delay)
            
            except Exception as e:
                logger.error(f"Error submitting form for {subscriber.email}: {str(e)}")
                result.error = str(e)
                
                # Retry with backoff
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
                
                # Track error types
                error_type = "unknown"
                if hasattr(result, 'error') and result.error:
                    if "429" in result.error:
                        error_type = "rate_limit"
                    elif "403" in result.error:
                        error_type = "forbidden"
                    elif "timeout" in result.error.lower():
                        error_type = "timeout"
                    elif "connection" in result.error.lower():
                        error_type = "connection"
                    else:
                        # Use first 30 chars of error as type
                        error_type = result.error[:30]
                
                self.stats["errors"][error_type] += 1
    
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
            for error_type, count in sorted(stats["errors"].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {error_type}: {count}")