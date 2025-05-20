"""Main entry point for UMG form submission tool."""
import logging
import os
import sys
import time
import csv
from typing import List

# Add modules
from models import Subscriber
from proxies import ProxyManager
from form_handler import BatchSubmitter
from config import AppConfig

# Set up logging
logger = logging.getLogger(__name__)

def setup_logging(config: AppConfig):
    """Set up logging based on configuration."""
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_level = logging.DEBUG if config.debug_mode else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler()  # Always log to console
        ]
    )
    
    # Add file handler if enabled
    if config.log_to_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log file path
        log_file = f"submission_{time.strftime('%Y%m%d_%H%M%S')}.log"
        log_path = os.path.join(log_dir, log_file)
        
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
        
        logger.info(f"Logging to {log_path}")
    
    # Suppress verbose logs from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)

def load_subscribers(config_path: str) -> List[Subscriber]:
    """Load subscribers from CSV file."""
    subscribers = []
    
    # Open the provided CSV file
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows
                if not row or not any(row.values()):
                    continue
                
                # Skip comment rows
                if row.get("email", "").startswith("#"):
                    continue
                
                # Create subscriber
                subscriber = Subscriber(
                    email=row.get("email", "").strip(),
                    first_name=row.get("first_name", "").strip(),
                    last_name=row.get("last_name", "").strip(),
                    country=row.get("country", "").strip().upper() or "US",
                    postcode=row.get("postcode", "").strip()  # Added postcode field
                )
                
                # Validate subscriber
                if not subscriber.email or "@" not in subscriber.email:
                    logger.warning(f"Skipping invalid email: {subscriber.email}")
                    continue
                
                # Validate postcode is present
                if not subscriber.postcode:
                    logger.warning(f"Skipping subscriber with missing postcode: {subscriber.email}")
                    continue
                
                # Add to list
                subscribers.append(subscriber)
    
    except Exception as e:
        logger.error(f"Error loading subscribers: {e}")
        sys.exit(1)
    
    return subscribers

def main():
    """Main entry point."""
    # Get configuration
    config = AppConfig()
    
    # Update config path to look in the correct location
    config.config_path = os.path.join(os.path.dirname(__file__), "config.csv")
    
    # Enable proxies
    config.use_proxies = True
    config.proxy_file = os.path.join(os.path.dirname(__file__), "proxies.txt")
    
    # Set up logging
    setup_logging(config)
    
    logger.info("Starting UMG Form Submission Tool")
    logger.info(f"Configuration: {config}")

    subscribers = load_subscribers(config.config_path)
    logger.info(f"Loaded {len(subscribers)} subscribers from {config.config_path}")
    
    # Initialize proxy manager if using proxies
    proxy_manager = None
    if config.use_proxies:
        proxy_manager = ProxyManager(
            proxy_file=config.proxy_file,
            rotation_strategy=config.proxy_rotation
    )
    logger.info(f"Loaded {proxy_manager.count()} proxies from {config.proxy_file}")
    
    # Initialize submitter
    submitter = BatchSubmitter(
        proxy_manager=proxy_manager,
        max_threads=config.max_threads
    )
    
    # Submit forms
    logger.info(f"Starting batch submission with {config.max_threads} threads")
    start_time = time.time()
    results = submitter.submit_batch(subscribers)
    end_time = time.time()
    
    # Log results
    logger.info(f"Submission complete in {end_time - start_time:.2f} seconds")
    submitter.log_stats()
    
    # Calculate statistics
    stats = submitter.get_stats()
    success_rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
    logger.info(f"Success rate: {success_rate:.1f}% ({stats['success']}/{stats['total']})")
    
    # Log any failures
    failure_count = sum(1 for result in results if not result.success)
    if failure_count > 0:
        logger.warning(f"Failures: {failure_count}")
        for result in results:
            if not result.success:
                logger.warning(f"  {result.subscriber.email}: {result.error}")

if __name__ == "__main__":  
    main()