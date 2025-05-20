"""Form submission handler module."""
import time
import logging
import json
import concurrent.futures
from random import uniform
from typing import Dict, List, Optional, Tuple
import requests
import urllib3
import threading
from collections import defaultdict

from config import (
    MAX_RETRIES, RETRY_DELAY_MIN, RETRY_DELAY_MAX, 
    MIN_REQUEST_DELAY, MAX_REQUEST_DELAY
)
from models import Subscriber, SubmissionPayload, SubmissionResult
from proxies import Proxy, ProxyManager

# Suppress insecure connection warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Form URL endpoint
FORM_ENDPOINT = "https://forms.umusic-online.com/api/v2/forms/-NL2jY3XB_QvQ4ttcCds/subscriptions"

# Specific headers that must be used for the request
REQUIRED_HEADERS = {
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

class FormSubmitter:
    """Handles form submission to the UMG API."""
    
    def __init__(self, proxy: Optional[Proxy] = None):
        """Initialize FormSubmitter with optional proxy."""
        self.proxy = proxy
        self.session = None
        self.results = []
    
    def initialize_session(self) -> requests.Session:
        """Initialize or refresh the session with required headers."""
        logger.info("Initializing new requests session...")
        
        if self.session:
            self.session.close()
        
        self.session = requests.Session()
        
        # Set up retries
        retry_strategy = Retry(
            total=MAX_RETRIES,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Set default headers
        self.session.headers.update(REQUIRED_HEADERS)
        
        # Configure proxy if provided
        if self.proxy:
            proxy_url = self.proxy.get_url()
            self.session.proxies.update({
                "http": proxy_url,
                "https": proxy_url
            })
        
        return self.session
    
    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()
    
    def _prepare_payload(self, subscriber: Subscriber) -> Dict:
        """Prepare the form payload data."""
        # Default country code since it's not in the Subscriber model
        country_code = "US"  # Default to United States
        
        payload = {
            "email": subscriber.email,
            "name": subscriber.name if hasattr(subscriber, 'name') else "",
            "locale": "en",
            "country": country_code,  # Use default country code
            "city": "",
            "optInMessage": True,
            "optInEmail": True,
            "termsAndConditions": True,
            "dateOfBirth": "",
            "postalCode": ""
        }
        return payload
    
    def submit(self, subscriber: Subscriber) -> SubmissionResult:
        """Submit a single subscriber to the form."""
        if not self.session:
            self.initialize_session()
        
        success = False
        error_message = ""
        attempts = 0
        retries_left = MAX_RETRIES
        
        # Prepare the payload
        payload = self._prepare_payload(subscriber)
        payload_json = json.dumps(payload)
        
        # Update Content-Length header for this request
        headers = self.session.headers.copy()
        headers["Content-Length"] = str(len(payload_json))
        
        while not success and retries_left > 0:
            attempts += 1
            try:
                response = self.session.post(
                    FORM_ENDPOINT,
                    data=payload_json,
                    headers=headers,
                    timeout=30,
                    verify=False
                )
                
                if response.status_code == 200:
                    success = True
                    logger.info(f"Successfully submitted {subscriber.email}")
                else:
                    error_message = f"Failed submission: HTTP {response.status_code} - {response.text}"
                    logger.error(error_message)
                    
                    # Add delay before retry
                    delay = uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX)
                    time.sleep(delay)
                    retries_left -= 1
                
            except Exception as e:
                error_message = f"Error during submission: {str(e)}"
                logger.error(error_message)
                
                # Add delay before retry
                delay = uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX)
                time.sleep(delay)
                retries_left -= 1
        
        # Add random delay between submissions to prevent rate limiting
        time.sleep(uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY))
        
        result = SubmissionResult(
            subscriber=subscriber,
            success=success,
            error_message=error_message,
            attempts=attempts
        )
        self.results.append(result)
        return result
    
    def submit_batch(self, subscribers: List[Subscriber], max_threads: int = 1) -> List[SubmissionResult]:
        """Submit multiple subscribers."""
        self.results = []
        
        if max_threads <= 1:
            # Sequential processing
            for idx, subscriber in enumerate(subscribers, 1):
                logger.info(f"Processing {idx}/{len(subscribers)}: {subscriber.email}")
                try:
                    result = self.submit(subscriber)
                    self.results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {subscriber.email}: {str(e)}")
                    result = SubmissionResult(
                        subscriber=subscriber,
                        success=False,
                        error_message=str(e),
                        attempts=1
                    )
                    self.results.append(result)
        else:
            # Parallel processing
            self._parallel_submit(subscribers, max_threads)
        
        return self.results
    
    def _parallel_submit(self, subscribers: List[Subscriber], max_threads: int) -> List[SubmissionResult]:
        """Submit subscribers in parallel."""
        results = []
        thread_submitters = {}
        thread_local = threading.local()
        
        def get_thread_submitter():
            thread_id = threading.get_ident()
            if thread_id not in thread_submitters:
                thread_submitters[thread_id] = FormSubmitter(proxy=self.proxy)
                thread_submitters[thread_id].initialize_session()
            return thread_submitters[thread_id]
        
        def process_subscriber(idx, subscriber):
            logger.info(f"Processing {idx}/{len(subscribers)}: {subscriber.email}")
            submitter = get_thread_submitter()
            return submitter.submit(subscriber)
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
                future_to_subscriber = {
                    executor.submit(process_subscriber, idx, subscriber): (idx, subscriber)
                    for idx, subscriber in enumerate(subscribers, 1)
                }
                
                for future in concurrent.futures.as_completed(future_to_subscriber):
                    idx, subscriber = future_to_subscriber[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing {subscriber.email}: {str(e)}")
                        result = SubmissionResult(
                            subscriber=subscriber,
                            success=False,
                            error_message=str(e),
                            attempts=1
                        )
                        results.append(result)
        
        finally:
            # Clean up all thread-local submitters
            for thread_id, submitter in thread_submitters.items():
                try:
                    submitter.close()
                except Exception as e:
                    logger.warning(f"Error closing submitter for thread {thread_id}: {str(e)}")
        
        self.results.extend(results)
        return results
    
    def get_statistics(self) -> Dict[str, int]:
        """Get submission statistics."""
        if not self.results:
            return {"total": 0, "success": 0, "failure": 0}
        
        success_count = sum(1 for r in self.results if r.success)
        total_count = len(self.results)
        
        return {
            "total": total_count,
            "success": success_count,
            "failure": total_count - success_count
        }

class BatchSubmitter:
    """Handles batch submission with optional proxy rotation."""
    
    def __init__(self, max_threads: int = 1, proxy_manager: Optional[ProxyManager] = None, headless: bool = True, **kwargs):
        """Initialize BatchSubmitter with thread count and proxy configuration.
        
        Args:
            max_threads: Maximum number of threads to use
            proxy_manager: Optional proxy manager for rotation
            headless: Ignored parameter (kept for compatibility)
            **kwargs: Additional parameters (ignored)
        """
        self.max_threads = max_threads
        self.proxy_manager = proxy_manager
        self.submitter = None
    
    def submit_batch(self, subscribers: List[Subscriber]) -> List[SubmissionResult]:
        """Submit a batch of subscribers."""
        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager
        
        self.submitter = FormSubmitter(proxy=proxy)
        return self.submitter.submit_batch(subscribers, max_threads=self.max_threads)
    
    def get_statistics(self) -> Dict[str, int]:
        """Get submission statistics."""
        if self.submitter and hasattr(self.submitter, 'get_statistics'):
            return self.submitter.get_statistics()
        
        # Default empty statistics if submitter not available
        return {"total": 0, "success": 0, "failure": 0}