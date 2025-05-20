"""Configuration settings for the UMG form submission tool."""
import os
from dataclasses import dataclass
from typing import List, Optional  # Add Optional import here

# API Configuration
FORM_URL = "https://forms.umusic-online.com/api/v2/forms/-NL2jY3XB_QvQ4ttcCds/subscriptions"
CLIENT_ID = "6d7b8ddd3a2e30966d462f4f301f7532973fbac7b37404702bb8295ed6aeefe8"
ACQ_SYS = "6d697261"
CAMPAIGN_ID = "ad41fa4adbff455fa967a6c62433566d"
HOST_URL = "https://link.fans/hmhastoursignup"
OPTINS = ["-MxcmJpUtUKsxARFLAz2"]

# Browser Configuration
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

# Rate Limiting
MIN_REQUEST_DELAY = 1.5
MAX_REQUEST_DELAY = 4.0
MIN_CHALLENGE_WAIT = 4.0
MAX_CHALLENGE_WAIT = 7.0

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY_MIN = 2.0
RETRY_DELAY_MAX = 5.0

# Paths
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.csv")
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

# Proxy Configuration
DEFAULT_PROXY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "proxies.txt")
PROXY_ROTATION_STRATEGY = "round_robin"  # Options: random, round_robin, country_match

@dataclass
class AppConfig:
    """Application configuration container."""
    config_path: str = DEFAULT_CONFIG_PATH
    proxy_file: Optional[str] = None
    use_proxies: bool = False
    proxy_rotation: str = PROXY_ROTATION_STRATEGY
    log_to_file: bool = True
    debug_mode: bool = False
    headless: bool = True
    max_threads: int = 1  # Default to single thread for safety