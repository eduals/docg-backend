"""
Formula Evaluator for the tag system.

Safely evaluates mathematical expressions without using eval().
Uses AST-based evaluation with whitelisted operations.
"""

from typing import Any, Dict, List, Union
from app.tags.parser.ast import (
    TagNode,
    NumberNode,
    StringNode,
    VariableNode,
    GlobalVarNode,
    BinaryOpNode,
    LogicalOpNode,
    UnaryOpNode,
    FunctionCallNode,
    MathOp,
    ComparisonOp,
    LogicalOp
)
from app.tags.engine.functions import default_function_registry, FunctionError


class FormulaError(Exception):
    """Error during formula evaluation."""
    pass


class FormulaEvaluator:
    """
    Safely evaluates formula expressions.

    Supports:
    - Arithmetic: +, -, *, /, %
    - Comparisons: ==, !=, >, <, >=, <=, ~ (contains)
    - Logical: &&, ||, !
    - Functions: SUM(), ROUND(), IF(), etc.
    """

    # Maximum recursion depth for safety
    MAX_DEPTH = 50

    def __init__(self, context: Dict[str, Any], function_registry=None):
        self.context = context
        self.function_registry = function_registry or default_function_registry
        self._depth = 0

    def evaluate(self, node: TagNode) -> Any:
        """
        Evaluate a formula AST node.

        Args:
            node: The AST node to evaluate

        Returns:
            The result of the evaluation
        """
        self._depth += 1

        if self._depth > self.MAX_DEPTH:
            raise FormulaError("Maximum recursion depth exceeded")

        try:
            result = self._evaluate_node(node)
            return result
        finally:
            self._depth -= 1

    def _evaluate_node(self, node: TagNode) -> Any:
        """Dispatch evaluation based on node type."""
        if isinstance(node, NumberNode):
            return node.value

        if isinstance(node, StringNode):
            return node.value

        if isinstance(node, VariableNode):
            return self._evaluate_variable(node)

        if isinstance(node, GlobalVarNode):
            return self._evaluate_global_var(node)

        if isinstance(node, BinaryOpNode):
            return self._evaluate_binary_op(node)

        if isinstance(node, LogicalOpNode):
            return self._evaluate_logical_op(node)

        if isinstance(node, UnaryOpNode):
            return self._evaluate_unary_op(node)

        if isinstance(node, FunctionCallNode):
            return self._evaluate_function_call(node)

        raise FormulaError(f"Unknown node type: {type(node).__name__}")

    def _evaluate_variable(self, node: VariableNode) -> Any:
        """Evaluate a variable reference."""
        value = self._resolve_path(node.path, self.context)

        # Handle array index
        if node.index is not None and isinstance(value, (list, tuple)):
            if 0 <= node.index < len(value):
                value = value[node.index]
            else:
                value = None

        return value

    def _evaluate_global_var(self, node: GlobalVarNode) -> Any:
        """Evaluate a global variable."""
        globals_context = self.context.get('_globals', {})
        return globals_context.get(node.name)

    def _evaluate_binary_op(self, node: BinaryOpNode) -> Any:
        """Evaluate a binary operation."""
        left = self.evaluate(node.left)
        right = self.evaluate(node.right)

        op = node.operator

        # Math operations
        if isinstance(op, MathOp):
            return self._apply_math_op(op, left, right)

        # Comparison operations
        if isinstance(op, ComparisonOp):
            return self._apply_comparison_op(op, left, right)

        raise FormulaError(f"Unknown operator: {op}")

    def _apply_math_op(self, op: MathOp, left: Any, right: Any) -> Union[int, float]:
        """Apply a mathematical operation."""
        # Convert to numbers
        left_num = self._to_number(left)
        right_num = self._to_number(right)

        if op == MathOp.ADD:
            return left_num + right_num
        elif op == MathOp.SUB:
            return left_num - right_num
        elif op == MathOp.MUL:
            return left_num * right_num
        elif op == MathOp.DIV:
            if right_num == 0:
                raise FormulaError("Division by zero")
            return left_num / right_num
        elif op == MathOp.MOD:
            if right_num == 0:
                raise FormulaError("Modulo by zero")
            return left_num % right_num

        raise FormulaError(f"Unknown math operator: {op}")

    def _apply_comparison_op(self, op: ComparisonOp, left: Any, right: Any) -> bool:
        """Apply a comparison operation."""
        # Handle contains operator separately
        if op == ComparisonOp.CONTAINS:
            left_str = str(left) if left is not None else ""
            right_str = str(right) if right is not None else ""
            return right_str in left_str

        # For numeric comparisons, try to convert
        try:
            left_num = self._to_number(left)
            right_num = self._to_number(right)
            use_numeric = True
        except (ValueError, TypeError):
            use_numeric = False

        if op == ComparisonOp.EQ:
            if use_numeric:
                return left_num == right_num
            return left == right

        elif op == ComparisonOp.NE:
            if use_numeric:
                return left_num != right_num
            return left != right

        elif op == ComparisonOp.GT:
            if use_numeric:
                return left_num > right_num
            return str(left) > str(right)

        elif op == ComparisonOp.GTE:
            if use_numeric:
                return left_num >= right_num
            return str(left) >= str(right)

        elif op == ComparisonOp.LT:
            if use_numeric:
                return left_num < right_num
            return str(left) < str(right)

        elif op == ComparisonOp.LTE:
            if use_numeric:
                return left_num <= right_num
            return str(left) <= str(right)

        raise FormulaError(f"Unknown comparison operator: {op}")

    def _evaluate_logical_op(self, node: LogicalOpNode) -> bool:
        """Evaluate a logical operation."""
        # Short-circuit evaluation
        if node.operator == LogicalOp.AND:
            left = self._to_bool(self.evaluate(node.left))
            if not left:
                return False
            return self._to_bool(self.evaluate(node.right))

        elif node.operator == LogicalOp.OR:
            left = self._to_bool(self.evaluate(node.left))
            if left:
                return True
            return self._to_bool(self.evaluate(node.right))

        raise FormulaError(f"Unknown logical operator: {node.operator}")

    def _evaluate_unary_op(self, node: UnaryOpNode) -> Any:
        """Evaluate a unary operation."""
        operand = self.evaluate(node.operand)

        if node.operator == '-':
            return -self._to_number(operand)

        elif node.operator == '!':
            return not self._to_bool(operand)

        raise FormulaError(f"Unknown unary operator: {node.operator}")

    def _evaluate_function_call(self, node: FunctionCallNode) -> Any:
        """Evaluate a function call."""
        # Evaluate arguments
        args = [self.evaluate(arg) for arg in node.arguments]

        try:
            return self.function_registry.execute(node.name, args, self.context)
        except FunctionError:
            raise
        except Exception as e:
            raise FormulaError(f"Function {node.name} failed: {e}")

    def _resolve_path(self, path: List[str], data: Dict[str, Any]) -> Any:
        """Resolve a dotted path in the context."""
        current = data

        for key in path:
            if current is None:
                return None

            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                current = current[idx] if 0 <= idx < len(current) else None
            elif hasattr(current, key):
                current = getattr(current, key)
            else:
                return None

        return current

    def _to_number(self, value: Any) -> Union[int, float]:
        """Convert a value to a number."""
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return 0
            # Try to parse as number
            try:
                return int(value)
            except ValueError:
                pass
            try:
                return float(value)
            except ValueError:
                raise FormulaError(f"Cannot convert '{value}' to number")
        return float(value)

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
