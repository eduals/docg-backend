"""
Tag Evaluator for the tag system.

Evaluates parsed AST nodes into final output.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from app.tags.parser.ast import (
    TagNode,
    DocumentNode,
    TextNode,
    VariableNode,
    GlobalVarNode,
    FormulaNode,
    ConditionalNode,
    LoopNode,
    TransformNode
)
from app.tags.transforms import default_registry as default_transform_registry
from app.tags.engine.formula import FormulaEvaluator, FormulaError


class EvaluationError(Exception):
    """Error during evaluation."""
    pass


class TagEvaluator:
    """
    Evaluates parsed AST into final output.

    Handles:
    - Variable resolution
    - Transform application
    - Formula evaluation
    - Conditional processing
    - Loop expansion
    """

    # Safety limits
    MAX_LOOPS = 1000
    MAX_LOOP_DEPTH = 3

    def __init__(
        self,
        context: Dict[str, Any],
        transform_registry=None,
        locale: str = 'pt_BR'
    ):
        self.context = context
        self.transform_registry = transform_registry or default_transform_registry
        self.locale = locale

        # Add locale to context for transforms
        self.context['locale'] = locale

        # Statistics
        self._resolved_count = 0
        self._loops_count = 0
        self._conditionals_count = 0
        self._current_loop_depth = 0

        # Formula evaluator (lazy initialization)
        self._formula_evaluator = None

    def evaluate(self, node: TagNode) -> Any:
        """
        Evaluate an AST node.

        Args:
            node: The AST node to evaluate

        Returns:
            The evaluated result (string for documents, can be other types for intermediate results)
        """
        if isinstance(node, DocumentNode):
            return self._evaluate_document(node)

        if isinstance(node, TextNode):
            return node.content

        if isinstance(node, VariableNode):
            return self._evaluate_variable(node)

        if isinstance(node, GlobalVarNode):
            return self._evaluate_global_var(node)

        if isinstance(node, FormulaNode):
            return self._evaluate_formula(node)

        if isinstance(node, ConditionalNode):
            return self._evaluate_conditional(node)

        if isinstance(node, LoopNode):
            return self._evaluate_loop(node)

        raise EvaluationError(f"Unknown node type: {type(node).__name__}")

    def _evaluate_document(self, node: DocumentNode) -> str:
        """Evaluate a document (root node)."""
        parts = []

        for child in node.children:
            result = self.evaluate(child)
            if result is not None:
                parts.append(str(result))

        return ''.join(parts)

    def _evaluate_variable(self, node: VariableNode) -> Any:
        """Evaluate a variable reference with optional transforms."""
        # Resolve the path
        value = self._resolve_path(node.path)
        self._resolved_count += 1

        # Handle array index
        if node.index is not None and isinstance(value, (list, tuple)):
            if 0 <= node.index < len(value):
                value = value[node.index]
            else:
                value = None

        # Apply transforms
        for transform in node.transforms:
            value = self._apply_transform(transform, value)

        return value

    def _evaluate_global_var(self, node: GlobalVarNode) -> Any:
        """Evaluate a global variable."""
        self._resolved_count += 1

        # Get global variables from context
        globals_dict = self.context.get('_globals', {})

        # Check in globals first
        if node.name in globals_dict:
            return globals_dict[node.name]

        # Built-in global variables
        now = datetime.now()

        if node.name == 'timestamp':
            return now.isoformat()

        if node.name == 'date':
            return now.strftime('%Y-%m-%d')

        if node.name == 'date_br':
            return now.strftime('%d/%m/%Y')

        if node.name == 'time':
            return now.strftime('%H:%M')

        if node.name == 'datetime':
            return now.strftime('%Y-%m-%d %H:%M:%S')

        if node.name == 'datetime_br':
            return now.strftime('%d/%m/%Y %H:%M')

        if node.name == 'year':
            return now.year

        if node.name == 'month':
            return now.month

        if node.name == 'day':
            return now.day

        if node.name == 'uuid':
            import uuid
            return str(uuid.uuid4())

        if node.name == 'document_number':
            # Get from context or generate
            return globals_dict.get('document_number', 1)

        if node.name == 'workflow_name':
            return self.context.get('workflow', {}).get('name', '')

        # Not found
        return None

    def _evaluate_formula(self, node: FormulaNode) -> Any:
        """Evaluate a formula expression."""
        if self._formula_evaluator is None:
            self._formula_evaluator = FormulaEvaluator(self.context)

        try:
            return self._formula_evaluator.evaluate(node.expression)
        except FormulaError as e:
            # Return error message in output
            return f"[Error: {e}]"

    def _evaluate_conditional(self, node: ConditionalNode) -> str:
        """Evaluate a conditional block."""
        self._conditionals_count += 1

        # Evaluate condition
        condition_result = self._evaluate_condition(node.condition.expression)

        # Evaluate appropriate branch
        if condition_result:
            branch = node.true_branch
        else:
            branch = node.false_branch

        # Evaluate branch content
        parts = []
        for child in branch:
            result = self.evaluate(child)
            if result is not None:
                parts.append(str(result))

        return ''.join(parts)

    def _evaluate_condition(self, node: TagNode) -> bool:
        """Evaluate a condition expression to boolean."""
        if self._formula_evaluator is None:
            self._formula_evaluator = FormulaEvaluator(self.context)

        result = self._formula_evaluator.evaluate(node)

        # Convert to boolean
        return self._to_bool(result)

    def _evaluate_loop(self, node: LoopNode) -> str:
        """Evaluate a loop block."""
        self._loops_count += 1
        self._current_loop_depth += 1

        if self._current_loop_depth > self.MAX_LOOP_DEPTH:
            self._current_loop_depth -= 1
            return "[Error: Maximum loop depth exceeded]"

        try:
            # Get collection
            collection = self._resolve_path(node.collection.path)

            if not isinstance(collection, (list, tuple)):
                return ""

            if len(collection) > self.MAX_LOOPS:
                return f"[Error: Loop exceeds maximum of {self.MAX_LOOPS} iterations]"

            parts = []

            for index, item in enumerate(collection):
                # Create loop context with item
                loop_context = {
                    **self.context,
                    node.item_name: item,
                    '_loop': {
                        'index': index,
                        'index1': index + 1,
                        'first': index == 0,
                        'last': index == len(collection) - 1,
                        'length': len(collection)
                    }
                }

                # Create evaluator for loop iteration
                loop_evaluator = TagEvaluator(
                    loop_context,
                    transform_registry=self.transform_registry,
                    locale=self.locale
                )
                loop_evaluator._current_loop_depth = self._current_loop_depth

                # Evaluate body
                for child in node.body:
                    result = loop_evaluator.evaluate(child)
                    if result is not None:
                        parts.append(str(result))

            return ''.join(parts)

        finally:
            self._current_loop_depth -= 1

    def _apply_transform(self, transform: TransformNode, value: Any) -> Any:
        """Apply a transform to a value."""
        transform_context = {
            **self.context,
            '_transform_name': transform.name
        }

        try:
            return self.transform_registry.apply(
                transform.name,
                value,
                transform.params,
                transform_context
            )
        except Exception as e:
            # Return original value if transform fails
            import logging
            logging.getLogger(__name__).warning(
                f"Transform '{transform.name}' failed: {e}"
            )
            return value

    def _resolve_path(self, path: List[str]) -> Any:
        """Resolve a dotted path in the context."""
        if not path:
            return None

        current = self.context

        for key in path:
            if current is None:
                return None

            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                if key.isdigit():
                    idx = int(key)
                    current = current[idx] if 0 <= idx < len(current) else None
                else:
                    # Try to get property from all items
                    current = [self._get_value(item, key) for item in current]
            elif hasattr(current, key):
                current = getattr(current, key)
            else:
                # Try dict-like access on objects
                try:
                    current = current[key]
                except (KeyError, TypeError, IndexError):
                    return None

        return current

    def _get_value(self, obj: Any, key: str) -> Any:
        """Get a value from an object by key."""
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key)
        if hasattr(obj, key):
            return getattr(obj, key)
        return None

    def _to_bool(self, value: Any) -> bool:
        """Convert a value to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.lower() not in ('', 'false', '0', 'no', 'null', 'none')
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return bool(value)

    # Statistics methods

    def get_resolved_count(self) -> int:
        """Get count of resolved variables."""
        return self._resolved_count

    def get_loops_count(self) -> int:
        """Get count of loops evaluated."""
        return self._loops_count

    def get_conditionals_count(self) -> int:
        """Get count of conditionals evaluated."""
        return self._conditionals_count
