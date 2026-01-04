"""
Tests for LoopHandler
"""

import pytest
from app.flow_engine.loop_handler import LoopHandler
from app.flow_engine.variable_resolver import VariableResolver


class TestLoopHandler:
    """Test loop logic"""

    def test_get_loop_items(self):
        """Test getting items to iterate over"""
        resolver = VariableResolver(trigger_output={
            'line_items': [
                {'name': 'Item 1', 'price': 100},
                {'name': 'Item 2', 'price': 200}
            ]
        })
        handler = LoopHandler(resolver)

        loop_def = {
            'settings': {
                'items': '{{trigger.line_items}}'
            }
        }

        items = handler.get_loop_items(loop_def)
        assert len(items) == 2
        assert items[0]['name'] == 'Item 1'

    def test_create_item_context(self):
        """Test creating context for loop iteration"""
        resolver = VariableResolver(trigger_output={})
        handler = LoopHandler(resolver)

        loop_def = {
            'settings': {
                'item_name': 'product'
            }
        }

        item = {'name': 'Product A', 'price': 100}

        context = handler.create_item_context(loop_def, item, 0)

        assert context['product'] == item
        assert context['product_index'] == 0
        assert context['product_number'] == 1

    def test_process_loop_results(self):
        """Test processing loop results"""
        resolver = VariableResolver(trigger_output={})
        handler = LoopHandler(resolver)

        results = [
            {'success': True, 'id': '1'},
            {'success': True, 'id': '2'},
            {'success': False, 'error': 'Failed'}
        ]

        processed = handler.process_loop_results(results)

        assert processed['count'] == 3
        assert processed['success_count'] == 2
        assert processed['error_count'] == 1
        assert processed['items'] == results

    def test_iteration_limit(self):
        """Test that iteration limit is enforced"""
        # Create array with more than MAX_ITERATIONS items
        large_array = [{'id': i} for i in range(2000)]

        resolver = VariableResolver(trigger_output={'items': large_array})
        handler = LoopHandler(resolver)

        loop_def = {
            'settings': {
                'items': '{{trigger.items}}'
            }
        }

        items = handler.get_loop_items(loop_def)

        # Should be limited to MAX_ITERATIONS (1000)
        assert len(items) == handler.MAX_ITERATIONS

    def test_non_list_items(self):
        """Test handling non-list items gracefully"""
        resolver = VariableResolver(trigger_output={'items': 'not a list'})
        handler = LoopHandler(resolver)

        loop_def = {
            'settings': {
                'items': '{{trigger.items}}'
            }
        }

        items = handler.get_loop_items(loop_def)
        assert items == []

    def test_missing_items_reference(self):
        """Test handling missing items reference"""
        resolver = VariableResolver(trigger_output={})
        handler = LoopHandler(resolver)

        loop_def = {
            'settings': {}  # No items reference
        }

        items = handler.get_loop_items(loop_def)
        assert items == []
