"""Utility functions for the application."""
import os
import csv
import logging
import datetime
from typing import List, Dict, Any, Optional

from models import Subscriber, SubmissionResult


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

def export_results(results: List[SubmissionResult], filename="submission_results.csv"):
    """
    Export submission results to a CSV file.
    
    Args:
        results: List of submission result objects
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
    
    # Convert SubmissionResult objects to dictionaries
    result_dicts = []
    for result in results:
        result_dict = {
            "email": result.subscriber.email,
            "country": result.subscriber.country if hasattr(result.subscriber, "country") else "",
            "success": result.success,
            "error_message": result.error_message,
            "attempts": result.attempts
        }
        
        # Add additional fields if they exist
        if hasattr(result, "status_code") and result.status_code is not None:
            result_dict["status_code"] = result.status_code
        
        if hasattr(result, "response_text") and result.response_text is not None:
            result_dict["response_text"] = result.response_text
            
        if hasattr(result.subscriber, "postcode") and result.subscriber.postcode:
            result_dict["postcode"] = result.subscriber.postcode
            
        if hasattr(result.subscriber, "first_name") and result.subscriber.first_name:
            result_dict["first_name"] = result.subscriber.first_name
            
        if hasattr(result.subscriber, "last_name") and result.subscriber.last_name:
            result_dict["last_name"] = result.subscriber.last_name
        
        result_dicts.append(result_dict)
    
    # Write results to CSV
    if not result_dicts:
        logging.warning("No results to export")
        return
        
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = result_dicts[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(result_dicts)
    
    logging.info(f"Results exported to: {output_path}")    
    return output_path