"""Main entry point for the UMG form submission tool."""
import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional

from config import AppConfig, LOG_DIR
from models import Subscriber
from form_handler import BatchSubmitter
from proxies import ProxyManager
from utils import setup_logging, export_results

logger = logging.getLogger(__name__)


def load_subscribers(config_path: str) -> List[Subscriber]:
    """Load subscribers from the CSV file."""
    subscribers = []
    
    try:
        with open(config_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    subscriber = Subscriber.from_csv_row(row)
                    subscribers.append(subscriber)
                except KeyError as e:
                    logger.error(f"Missing required field in CSV row: {e}")
                except Exception as e:
                    logger.error(f"Error processing CSV row: {e}")
        
        logger.info(f"Loaded {len(subscribers)} subscribers from {config_path}")
        return subscribers
    
    except Exception as e:
        logger.error(f"Failed to load subscribers from {config_path}: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="UMG Form Submission Tool")
    parser.add_argument("--config", help="Path to subscriber CSV file")
    parser.add_argument("--proxies", help="Path to proxies text file")
    parser.add_argument("--threads", type=int, default=1, help="Number of concurrent submissions")
    parser.add_argument("--no-headless", action="store_true", help="Run with visible browser")
    parser.add_argument("--log-to-file", action="store_true", help="Log to file instead of console")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Create config from args
    config = AppConfig(
        config_path=args.config or os.path.join(os.path.dirname(__file__), "config.csv"),
        proxy_file=args.proxies,
        use_proxies=bool(args.proxies),
        log_to_file=args.log_to_file,
        debug_mode=args.debug,
        headless=not args.no_headless,
        max_threads=max(1, args.threads)
    )
    
    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = None
    if config.log_to_file:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        log_file = os.path.join(LOG_DIR, f"umg_submission_{timestamp}.log")
    
    setup_logging(debug=config.debug_mode, log_file=log_file)
    
    logger.info("Starting UMG Form Submission Tool")
    logger.info(f"Configuration: {config}")
    
    # Load subscribers
    subscribers = load_subscribers(config.config_path)
    if not subscribers:
        logger.error("No subscribers to process. Exiting.")
        return 1
    
    # Initialize proxy manager if needed
    proxy_manager = None
    if config.use_proxies and config.proxy_file:
        proxy_manager = ProxyManager(config.proxy_file)
        if not proxy_manager.proxies:
            logger.warning("No valid proxies loaded. Will proceed without proxies.")
    
    # Process submissions
    batch_submitter = BatchSubmitter(
        headless=config.headless,
        max_threads=config.max_threads,
        proxy_manager=proxy_manager
    )
    
    try:
        logger.info(f"Starting batch submission with {config.max_threads} threads")
        results = batch_submitter.submit_batch(subscribers)
        
        # Log statistics
        stats = batch_submitter.get_statistics()
        logger.info(f"Submission completed. Stats: {stats}")
        
        # Export results
        results_file = f"results_{timestamp}.csv"
        export_results(results, results_file)
        logger.info(f"Results exported to {results_file}")
        
        return 0
    
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 130
    
    except Exception as e:
        logger.exception(f"An error occurred during execution: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())