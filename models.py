"""Data models for the application."""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Subscriber:
    """Represents a subscriber record from the CSV file."""
    email: str
    country: str
    postcode: str
    
    # Optional fields that might be in the CSV
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> 'Subscriber':
        """Create a Subscriber instance from a CSV row dictionary."""
        return cls(
            email=row["email"],
            country=row["country"],
            postcode=row["postcode"],
            first_name=row.get("first_name"),
            last_name=row.get("last_name")
        )


@dataclass
class SubmissionPayload:
    """Represents the JSON payload for the API submission."""
    client_id: str
    consumer: Dict[str, str]
    metadata: Dict[str, str]
    optins: List[str]
    
    @classmethod
    def from_subscriber(cls, subscriber: Subscriber) -> Dict:
        """Create a submission payload dict from a Subscriber."""
        from config import CLIENT_ID, ACQ_SYS, CAMPAIGN_ID, HOST_URL, OPTINS
        
        # Build consumer dict with optional fields if present
        consumer = {
            "email": subscriber.email,
            "consumer_country": subscriber.country,
            "postcode": subscriber.postcode
        }
        
        if subscriber.first_name:
            consumer["first_name"] = subscriber.first_name
        if subscriber.last_name:
            consumer["last_name"] = subscriber.last_name
        
        return {
            "client_id": CLIENT_ID,
            "consumer": consumer,
            "metadata": {
                "acquisition_sys": ACQ_SYS,
                "campaign_id": CAMPAIGN_ID,
                "host_url": HOST_URL
            },
            "optins": OPTINS
        }


@dataclass
class SubmissionResult:
    """Represents the result of a form submission."""
    subscriber: Subscriber
    success: bool
    status_code: Optional[int] = None
    response_text: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 0
    # Standard ISO country codes mapping
COUNTRY_CODE_MAP = {
    "United States": "US",
    "USA": "US",
    "United Kingdom": "GB",
    "UK": "GB",
    "Canada": "CA",
    "Australia": "AU",
    # Add more mappings as needed
}

class SubmissionPayload:
    """Payload for form submission."""
    
    @classmethod
    def from_subscriber(cls, subscriber: Subscriber) -> Dict:
        """Create submission payload from subscriber data."""
        # Convert country to proper ISO code
        country_code = subscriber.country
        if country_code in COUNTRY_CODE_MAP:
            country_code = COUNTRY_CODE_MAP[country_code]
        elif len(country_code) > 2:
            # Default conversion: take first two characters and uppercase
            country_code = country_code[:2].upper()
            
        # Ensure country code is valid
        if not country_code or len(country_code) != 2:
            country_code = "US"  # Default to US if invalid
            
        return {
            "consumer": {
                "first_name": subscriber.first_name,
                "last_name": subscriber.last_name,
                "email": subscriber.email,
                "consumer_country": country_code,
                # Add any other required fields
            }
            # Add any other required top-level fields
        }