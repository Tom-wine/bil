"""Proxy management module."""
import logging
import random
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Proxy:
    """Represents a proxy configuration."""
    hostname: str
    port: int
    username: str
    password: str
    country: Optional[str] = None
    session_id: Optional[str] = None
    
    @property
    def proxy_url(self) -> str:
        """Returns the proxy URL for use with requests."""
        return f"http://{self.username}:{self.password}@{self.hostname}:{self.port}"
    
    @property
    def proxy_dict(self) -> Dict[str, str]:
        """Returns the proxy as a dictionary for requests."""
        url = self.proxy_url
        return {
            "http": url,
            "https": url
        }
    
    def __str__(self) -> str:
        """String representation with password obfuscated."""
        return f"{self.username}@{self.hostname}:{self.port} (country: {self.country})"


class ProxyManager:
    """Manages a pool of proxies."""
    
    def __init__(self, proxy_file: Optional[str] = None):
        """Initialize with proxies from a file."""
        self.proxies: List[Proxy] = []
        
        if proxy_file:
            self.load_proxies(proxy_file)
        
    def load_proxies(self, proxy_file: str) -> None:
        """Load proxies from a text file."""
        try:
            with open(proxy_file, 'r') as f:
                proxy_lines = [line.strip() for line in f if line.strip()]
            
            self.proxies = []
            for line in proxy_lines:
                try:
                    # Parse the proxy string
                    # Format: hostname:port:username:password_country-us_session-id
                    proxy = self._parse_proxy_line(line)
                    if proxy:
                        self.proxies.append(proxy)
                except Exception as e:
                    logger.warning(f"Failed to parse proxy line: {line}. Error: {str(e)}")
            
            logger.info(f"Loaded {len(self.proxies)} proxies from {proxy_file}")
        except Exception as e:
            logger.error(f"Failed to load proxies from {proxy_file}: {str(e)}")
    
    def _parse_proxy_line(self, line: str) -> Optional[Proxy]:
        """Parse a single proxy line."""
        # Split main parts: host:port:user:pass_metadata
        main_parts = line.split(':')
        if len(main_parts) < 4:
            logger.warning(f"Invalid proxy format: {line}")
            return None
        
        hostname = main_parts[0]
        port = int(main_parts[1])
        username = main_parts[2]
        
        # Last part might contain password and metadata
        password_meta = main_parts[3]
        
        # Handle metadata parts
        meta_parts = password_meta.split('_')
        password = meta_parts[0]
        
        # Extract country and session if available
        country = None
        session_id = None
        
        for part in meta_parts[1:]:
            if part.startswith('country-'):
                country = part.replace('country-', '')
            elif part.startswith('session-'):
                session_id = part.replace('session-', '')
        
        return Proxy(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            country=country,
            session_id=session_id
        )
    
    def get_random_proxy(self) -> Optional[Proxy]:
        """Get a random proxy from the pool."""
        if not self.proxies:
            logger.warning("No proxies available")
            return None
        
        return random.choice(self.proxies)
    
    def get_proxy_by_country(self, country_code: str) -> Optional[Proxy]:
        """Get a random proxy for a specific country."""
        country_proxies = [p for p in self.proxies if p.country == country_code]
        
        if not country_proxies:
            logger.warning(f"No proxies available for country: {country_code}")
            return None
        
        return random.choice(country_proxies)