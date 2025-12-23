"""
Data Normalizers for different CRM and data sources.

Provides a unified interface for normalizing data from:
- HubSpot (with associations)
- Webhooks (generic)
- Google Forms
- Stripe
- Pipedrive (future)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DataNormalizer(ABC):
    """
    Abstract base class for data normalizers.

    Each data source (CRM, webhook, etc.) should implement this interface
    to normalize data into a consistent format for the tag system.
    """

    source_name: str = ""

    @abstractmethod
    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw data into a standard format.

        The normalized data should be flat where possible, with nested
        structures only where semantically meaningful (e.g., 'associated').

        Args:
            data: Raw data from the source

        Returns:
            Normalized data dictionary
        """
        pass

    @abstractmethod
    def get_associations(
        self,
        data: Dict[str, Any],
        association_type: str
    ) -> List[Dict[str, Any]]:
        """
        Get associated objects from the data.

        Args:
            data: The normalized data
            association_type: Type of association (e.g., 'contacts', 'deals', 'line_items')

        Returns:
            List of associated objects, empty list if not supported or no associations
        """
        pass

    def supports_associations(self) -> bool:
        """
        Check if this source supports associations between objects.

        Returns:
            True if associations are supported
        """
        return False

    def get_supported_association_types(self) -> List[str]:
        """
        Get list of supported association types.

        Returns:
            List of association type names
        """
        return []


class HubSpotNormalizer(DataNormalizer):
    """
    Normalizer for HubSpot CRM data.

    Handles:
    - Contact, Deal, Company, Ticket objects
    - Properties normalization
    - Associations (contacts ↔ deals ↔ companies ↔ line_items)
    """

    source_name = "hubspot"

    # Default association mappings by object type
    ASSOCIATION_TYPES = {
        'contact': ['companies', 'deals'],
        'deal': ['contacts', 'companies', 'line_items', 'tickets'],
        'company': ['contacts', 'deals', 'tickets'],
        'ticket': ['contacts', 'companies', 'deals'],
        'line_item': ['deals'],
    }

    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize HubSpot object data.

        Input format (from HubSpot API):
        {
            'id': '123',
            'properties': {
                'firstname': 'John',
                'email': 'john@example.com',
                ...
            },
            'associations': {
                'companies': {'results': [...]},
                'deals': {'results': [...]}
            }
        }

        Output format:
        {
            'id': '123',
            'firstname': 'John',
            'email': 'john@example.com',
            'associated': {
                'companies': [...],
                'deals': [...]
            },
            '_source': 'hubspot',
            '_object_type': 'contact'
        }
        """
        normalized = {
            '_source': 'hubspot',
        }

        # Copy ID
        if 'id' in data:
            normalized['id'] = data['id']

        # Detect object type
        object_type = data.get('_object_type') or self._detect_object_type(data)
        normalized['_object_type'] = object_type

        # Flatten properties to root level
        properties = data.get('properties', {})
        for key, value in properties.items():
            # Don't overwrite special keys
            if not key.startswith('_'):
                normalized[key] = value

        # Handle timestamps
        if 'createdate' in properties:
            normalized['created_at'] = properties['createdate']
        if 'lastmodifieddate' in properties:
            normalized['updated_at'] = properties['lastmodifieddate']

        # Normalize associations
        associations = data.get('associations', {})
        normalized['associated'] = {}

        for assoc_type, assoc_data in associations.items():
            if isinstance(assoc_data, dict) and 'results' in assoc_data:
                # Full association data with nested objects
                normalized['associated'][assoc_type] = [
                    self._normalize_associated_object(obj)
                    for obj in assoc_data['results']
                ]
            elif isinstance(assoc_data, list):
                # List of IDs or objects
                normalized['associated'][assoc_type] = [
                    self._normalize_associated_object(obj) if isinstance(obj, dict) else {'id': obj}
                    for obj in assoc_data
                ]

        return normalized

    def _normalize_associated_object(self, obj: Dict) -> Dict:
        """Normalize a single associated object."""
        if 'properties' in obj:
            # Full object with properties
            result = {'id': obj.get('id')}
            result.update(obj.get('properties', {}))
            return result
        return obj

    def _detect_object_type(self, data: Dict) -> str:
        """Detect object type from data structure."""
        properties = data.get('properties', {})

        # Check for type-specific properties
        if 'email' in properties or 'firstname' in properties:
            return 'contact'
        if 'dealname' in properties or 'amount' in properties:
            return 'deal'
        if 'domain' in properties or 'name' in properties and 'industry' in properties:
            return 'company'
        if 'subject' in properties or 'content' in properties:
            return 'ticket'
        if 'hs_sku' in properties or 'quantity' in properties:
            return 'line_item'

        return 'unknown'

    def get_associations(
        self,
        data: Dict[str, Any],
        association_type: str
    ) -> List[Dict[str, Any]]:
        """Get associated objects from normalized data."""
        associated = data.get('associated', {})
        return associated.get(association_type, [])

    def supports_associations(self) -> bool:
        return True

    def get_supported_association_types(self) -> List[str]:
        return ['contacts', 'companies', 'deals', 'tickets', 'line_items']


class WebhookNormalizer(DataNormalizer):
    """
    Normalizer for generic webhook data.

    Webhooks are passed through with minimal normalization since
    their structure varies by source.
    """

    source_name = "webhook"

    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize webhook data.

        Mostly pass-through with source tagging.
        """
        normalized = {
            '_source': 'webhook',
            '_raw': data,  # Keep original for reference
        }

        # Flatten top-level data
        for key, value in data.items():
            if not key.startswith('_'):
                normalized[key] = value

        return normalized

    def get_associations(
        self,
        data: Dict[str, Any],
        association_type: str
    ) -> List[Dict[str, Any]]:
        """Webhooks generally don't have associations."""
        # Check if the association type exists as a key
        return data.get(association_type, []) if isinstance(data.get(association_type), list) else []

    def supports_associations(self) -> bool:
        return False


class GoogleFormsNormalizer(DataNormalizer):
    """
    Normalizer for Google Forms response data.

    Handles form responses with question IDs mapped to answers.
    """

    source_name = "google_forms"

    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Google Forms response.

        Input format:
        {
            'response_id': '...',
            'create_time': '...',
            'answers': [
                {'question_id': 'q1', 'value': 'Answer 1'},
                ...
            ]
        }

        Output format:
        {
            'response_id': '...',
            'created_at': '...',
            'q1': 'Answer 1',
            ...
        }
        """
        normalized = {
            '_source': 'google_forms',
        }

        # Copy standard fields
        if 'response_id' in data:
            normalized['response_id'] = data['response_id']

        if 'create_time' in data:
            normalized['created_at'] = data['create_time']

        if 'last_submitted_time' in data:
            normalized['submitted_at'] = data['last_submitted_time']

        # Flatten answers
        answers = data.get('answers', [])
        if isinstance(answers, list):
            for answer in answers:
                qid = answer.get('question_id')
                value = answer.get('value') or answer.get('text_answer') or answer.get('file_upload_answer')
                if qid:
                    normalized[qid] = value
        elif isinstance(answers, dict):
            # Already in dict format
            normalized.update(answers)

        # Keep raw for complex answer types
        normalized['_raw_answers'] = data.get('answers')

        return normalized

    def get_associations(
        self,
        data: Dict[str, Any],
        association_type: str
    ) -> List[Dict[str, Any]]:
        """Forms don't have associations."""
        return []

    def supports_associations(self) -> bool:
        return False


class StripeNormalizer(DataNormalizer):
    """
    Normalizer for Stripe webhook event data.

    Handles common Stripe events like payment_intent, customer, subscription.
    """

    source_name = "stripe"

    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Stripe webhook event.

        Input format:
        {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_...',
                    'amount': 5000,
                    'currency': 'usd',
                    ...
                }
            }
        }
        """
        normalized = {
            '_source': 'stripe',
        }

        # Event metadata
        normalized['event_type'] = data.get('type')
        normalized['event_id'] = data.get('id')

        # Extract the main object
        event_data = data.get('data', {})
        obj = event_data.get('object', {})

        # Copy object properties
        for key, value in obj.items():
            if not key.startswith('_'):
                normalized[key] = value

        # Normalize some common fields
        if 'amount' in obj:
            # Stripe amounts are in cents
            normalized['amount_cents'] = obj['amount']
            normalized['amount'] = obj['amount'] / 100

        if 'customer' in obj:
            normalized['customer_id'] = obj['customer']

        # Handle nested customer object
        if isinstance(obj.get('customer'), dict):
            customer = obj['customer']
            normalized['customer'] = {
                'id': customer.get('id'),
                'email': customer.get('email'),
                'name': customer.get('name'),
            }

        return normalized

    def get_associations(
        self,
        data: Dict[str, Any],
        association_type: str
    ) -> List[Dict[str, Any]]:
        """
        Stripe has limited associations.

        Supports: subscriptions (from customer)
        """
        if association_type == 'subscriptions':
            # Would need to be fetched from Stripe API
            return data.get('subscriptions', {}).get('data', [])
        return []

    def supports_associations(self) -> bool:
        return True  # Limited support

    def get_supported_association_types(self) -> List[str]:
        return ['subscriptions']


class GenericNormalizer(DataNormalizer):
    """
    Generic normalizer for unknown data sources.

    Passes data through with minimal transformation.
    """

    source_name = "generic"

    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pass through with source tag."""
        normalized = {
            '_source': 'generic',
        }
        normalized.update(data)
        return normalized

    def get_associations(
        self,
        data: Dict[str, Any],
        association_type: str
    ) -> List[Dict[str, Any]]:
        """No associations for generic data."""
        return []


# Normalizer registry
_NORMALIZERS = {
    'hubspot': HubSpotNormalizer(),
    'webhook': WebhookNormalizer(),
    'google_forms': GoogleFormsNormalizer(),
    'stripe': StripeNormalizer(),
    'generic': GenericNormalizer(),
}


def get_normalizer_for_source(source: str) -> DataNormalizer:
    """
    Get the appropriate normalizer for a data source.

    Args:
        source: Source identifier (e.g., 'hubspot', 'webhook')

    Returns:
        DataNormalizer instance
    """
    source_lower = source.lower() if source else 'generic'

    # Check for exact match
    if source_lower in _NORMALIZERS:
        return _NORMALIZERS[source_lower]

    # Check for partial match
    for key, normalizer in _NORMALIZERS.items():
        if key in source_lower:
            return normalizer

    # Default to generic
    return _NORMALIZERS['generic']


def register_normalizer(source: str, normalizer: DataNormalizer):
    """Register a custom normalizer for a source."""
    _NORMALIZERS[source.lower()] = normalizer
