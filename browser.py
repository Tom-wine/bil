"""Browser session handling module."""
import logging
import time
from random import uniform
from typing import Optional

import undetected_chromedriver as uc
import requests

from config import (
    FORM_URL, USER_AGENT, 
    MIN_CHALLENGE_WAIT, MAX_CHALLENGE_WAIT
)
from proxies import Proxy

logger = logging.getLogger(__name__)


class BrowserSession:
    """Handles browser sessions for bypassing Incapsula protection."""
    
    def __init__(self, headless: bool = True, proxy: Optional[Proxy] = None):
        """Initialize the browser session."""
        self.headless = headless
        self.proxy = proxy
        self.driver = None
        
    def get_session(self) -> requests.Session:
        """
        Launch a browser to pass Incapsula's JS challenge and retrieve the cookies.
        Returns a requests.Session with those cookies and default headers.
        """
        try:
            logger.info("Launching browser to obtain Incapsula cookies...")
            options = self._get_browser_options()
            
            self.driver = uc.Chrome(options=options)
            
            logger.info(f"Loading URL: {FORM_URL}")
            self.driver.get(FORM_URL)
            
            # Randomize wait time to appear more human-like
            wait_time = uniform(MIN_CHALLENGE_WAIT, MAX_CHALLENGE_WAIT)
            logger.info(f"Waiting {wait_time:.2f} seconds for Incapsula challenge...")
            time.sleep(wait_time)
            
            cookies = self.driver.get_cookies()
            logger.info(f"Retrieved {len(cookies)} cookies from browser session")
            
            session = self._create_session_from_cookies(cookies)
            
            # Setup proxy for the requests session if specified
            if self.proxy:
                session.proxies.update(self.proxy.proxy_dict)
                logger.info(f"Session configured with proxy: {self.proxy}")
                
            logger.info("Session initialized successfully")
            return session
            
        except Exception as e:
            logger.error(f"Failed to get browser session: {str(e)}")
            raise
    
    def _get_browser_options(self) -> uc.ChromeOptions:
        """Configure Chrome options."""
        options = uc.ChromeOptions()
        
        if self.headless:
            options.add_argument("--headless")
        
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={USER_AGENT}")
        
        # Configure proxy for Chrome if specified
        if self.proxy:
            logger.info(f"Configuring Chrome with proxy: {self.proxy}")
            options.add_argument(f'--proxy-server={self.proxy.hostname}:{self.proxy.port}')
            
            # For authenticated proxies, we'll use a plugin
            if self.proxy.username and self.proxy.password:
                plugin_path = self._create_proxy_auth_plugin()
                if plugin_path:
                    options.add_extension(plugin_path)
        
        return options
    
    def _create_proxy_auth_plugin(self) -> Optional[str]:
        """Create a Chrome plugin for proxy authentication."""
        import os
        import tempfile
        import zipfile
        
        if not (self.proxy and self.proxy.username and self.proxy.password):
            return None
        
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            }
        }
        """
        
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{self.proxy.hostname}",
                    port: {self.proxy.port}
                }},
                bypassList: ["localhost"]
            }}
        }};

        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{self.proxy.username}",
                    password: "{self.proxy.password}"
                }}
            }};
        }}

        chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """
        
        try:
            # Create a temporary directory
            temp_dir = tempfile.mkdtemp()
            plugin_path = os.path.join(temp_dir, "proxy_auth_plugin.zip")
            
            with zipfile.ZipFile(plugin_path, 'w') as zp:
                zp.writestr("manifest.json", manifest_json)
                zp.writestr("background.js", background_js)
                
            logger.info(f"Created proxy authentication plugin at {plugin_path}")
            return plugin_path
            
        except Exception as e:
            logger.error(f"Failed to create proxy auth plugin: {str(e)}")
            return None
            
    def _create_session_from_cookies(self, cookies) -> requests.Session:
        """Create a requests Session with browser cookies."""
        session = requests.Session()
        # Set cookies in the session
        for c in cookies:
            session.cookies.set(c['name'], c['value'], domain=c.get('domain'))
        
        # Default headers
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://link.fans",
            "Referer": "https://link.fans/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        })
        
        return session
    
    def close(self):
        """Close the browser if it's open."""
        if self.driver:
            try:
                logger.info("Closing browser session")
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing browser: {str(e)}")
            finally:
                self.driver = None