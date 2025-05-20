"""Utility functions for the application."""
import os
import csv
import logging
import datetime
from typing import List, Dict, Any, Optional

from models import Subscriber


def setup_logging(log_file=None, debug=False):
    """
    Configure logging for the application.
    
    Args:
        log_file: Path to log file
        debug: Whether to enable debug logging
    """
    import logging
    import os
    from datetime import datetime
    
    # Determine log level based on debug flag
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handler (if log file is specified)
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)
    
    return root_logger


def read_subscriber_data(config_path: str) -> List[Subscriber]:
    """Read the CSV file and return a list of Subscriber objects."""
    subscribers = []
    
    try:
        with open(config_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                subscriber = Subscriber.from_csv_row(row)
                subscribers.append(subscriber)
        
        return subscribers
    
    except Exception as e:
        logging.error(f"Error reading CSV file: {str(e)}")
        raise


def save_results_to_csv(results: List[Dict[str, Any]], output_path: Optional[str] = None) -> str:
    """Save submission results to a CSV file."""
    from config import LOG_DIR
    
    if output_path is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(LOG_DIR, f"results_{timestamp}.csv")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    fieldnames = ["email", "country", "postcode", "success", "status_code", 
                 "response_text", "error_message", "attempts"]
    
    try:
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                writer.writerow({
                    "email": result.subscriber.email,
                    "country": result.subscriber.country,
                    "postcode": result.subscriber.postcode,
                    "success": result.success,
                    "status_code": result.status_code,
                    "response_text": result.response_text,
                    "error_message": result.error_message,
                    "attempts": result.attempts
                })
        
        logging.info(f"Results saved to: {output_path}")
        return output_path
        
    except Exception as e:
        logging.error(f"Error saving results to CSV: {str(e)}")
        raise
def export_results(results, filename="submission_results.csv"):
    """
    Export submission results to a CSV file.
    
    Args:
        results: List of submission result dictionaries
        filename: Output CSV filename
    """
    import csv
    import os
    from datetime import datetime
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Add timestamp to filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(filename)
    output_path = os.path.join(output_dir, f"{base}_{timestamp}{ext}")
    
    # Write results to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if not results or len(results) == 0:
            return
            
        fieldnames = results[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        
    return output_path