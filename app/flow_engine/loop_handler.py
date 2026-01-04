"""
Loop Handler - Handle iteration over arrays in flows

Supports:
- Iterate over arrays from trigger/previous steps
- Execute steps for each item
- Collect results
- Loop iteration limits
"""

import logging
from typing import Dict, Any, Optional, List
from app.flow_engine.variable_resolver import VariableResolver

logger = logging.getLogger(__name__)


class LoopHandler:
    """
    Handles loop/iteration logic in flows.

    Loop definition example:
    {
        "type": "LOOP",
        "name": "processLineItems",
        "settings": {
            "items": "{{trigger.deal.line_items}}",
            "item_name": "item"  # Variable name for current item
        },
        "steps": [
            {
                "type": "ACTION",
                "name": "createInvoiceItem",
                "settings": {
                    "item_name": "{{item.name}}",
                    "price": "{{item.price}}"
                }
            }
        ]
    }
    """

    MAX_ITERATIONS = 1000  # Safety limit

    def __init__(self, resolver: VariableResolver):
        """
        Initialize loop handler.

        Args:
            resolver: Variable resolver
        """
        self.resolver = resolver

    def get_loop_items(self, loop_def: Dict[str, Any]) -> List[Any]:
        """
        Get items to iterate over.

        Args:
            loop_def: Loop step definition

        Returns:
            List of items to iterate
        """
        settings = loop_def.get('settings', {})
        items_ref = settings.get('items')

        if not items_ref:
            logger.warning("Loop has no items reference")
            return []

        # Resolve items
        items = self.resolver.resolve(items_ref)

        if not isinstance(items, list):
            logger.warning(f"Loop items is not a list: {type(items)}")
            return []

        # Apply iteration limit
        if len(items) > self.MAX_ITERATIONS:
            logger.warning(f"Loop has {len(items)} items, limiting to {self.MAX_ITERATIONS}")
            items = items[:self.MAX_ITERATIONS]

        return items

    def create_item_context(
        self,
        loop_def: Dict[str, Any],
        item: Any,
        index: int
    ) -> Dict[str, Any]:
        """
        Create context for current loop iteration.

        Args:
            loop_def: Loop step definition
            item: Current item
            index: Current index (0-based)

        Returns:
            Context dict with item variables
        """
        settings = loop_def.get('settings', {})
        item_name = settings.get('item_name', 'item')

        # Create context with item data
        context = {
            item_name: item,
            f'{item_name}_index': index,
            f'{item_name}_number': index + 1,  # 1-based
        }

        return context

    def process_loop_results(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process and aggregate loop results.

        Args:
            results: List of results from each iteration

        Returns:
            Aggregated results
        """
        return {
            'items': results,
            'count': len(results),
            'success_count': sum(1 for r in results if r.get('success', True)),
            'error_count': sum(1 for r in results if not r.get('success', True)),
        }


class LoopBreakException(Exception):
    """Exception to break out of loop early"""
    pass


class LoopContinueException(Exception):
    """Exception to skip to next iteration"""
    pass
