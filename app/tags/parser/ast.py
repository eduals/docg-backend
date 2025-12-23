"""
Abstract Syntax Tree (AST) nodes for the tag system.

The AST represents the parsed structure of tags and their content.
"""

from dataclasses import dataclass, field
from typing import List, Any, Optional, Union
from enum import Enum


class ComparisonOp(Enum):
    """Comparison operators for conditionals."""
    EQ = '=='
    NE = '!='
    GT = '>'
    GTE = '>='
    LT = '<'
    LTE = '<='
    CONTAINS = '~'


class LogicalOp(Enum):
    """Logical operators for combining conditions."""
    AND = '&&'
    OR = '||'
    NOT = '!'


class MathOp(Enum):
    """Mathematical operators."""
    ADD = '+'
    SUB = '-'
    MUL = '*'
    DIV = '/'
    MOD = '%'


@dataclass
class TagNode:
    """Base class for all AST nodes."""
    position: int = 0

    def accept(self, visitor):
        """Accept a visitor (for visitor pattern)."""
        method_name = f'visit_{self.__class__.__name__}'
        method = getattr(visitor, method_name, visitor.generic_visit)
        return method(self)


@dataclass
class TextNode(TagNode):
    """
    Literal text content (not a tag).

    Example: "Hello, " in "Hello, {{name}}"
    """
    content: str = ""


@dataclass
class TransformNode(TagNode):
    """
    A transform (pipe operation) applied to a value.

    Example: format:"DD/MM/YYYY" in {{date | format:"DD/MM/YYYY"}}
    """
    name: str = ""
    params: List[Any] = field(default_factory=list)


@dataclass
class VariableNode(TagNode):
    """
    A variable reference with optional transforms.

    Example: {{trigger.deal.amount | currency:"BRL"}}

    Attributes:
        path: List of path segments ['trigger', 'deal', 'amount']
        transforms: List of TransformNode to apply
        index: Optional array index access [0]
    """
    path: List[str] = field(default_factory=list)
    transforms: List[TransformNode] = field(default_factory=list)
    index: Optional[int] = None


@dataclass
class GlobalVarNode(TagNode):
    """
    A global variable reference.

    Example: {{$timestamp}}, {{$date}}, {{$document_number}}
    """
    name: str = ""


@dataclass
class NumberNode(TagNode):
    """A numeric literal."""
    value: Union[int, float] = 0


@dataclass
class StringNode(TagNode):
    """A string literal."""
    value: str = ""


@dataclass
class BinaryOpNode(TagNode):
    """
    A binary operation (math or comparison).

    Example: amount * 1.1, price > 100
    """
    left: TagNode = None
    operator: Union[MathOp, ComparisonOp] = None
    right: TagNode = None


@dataclass
class LogicalOpNode(TagNode):
    """
    A logical operation combining conditions.

    Example: amount > 100 && status == "active"
    """
    left: TagNode = None
    operator: LogicalOp = None
    right: TagNode = None


@dataclass
class UnaryOpNode(TagNode):
    """
    A unary operation.

    Example: !active, -amount
    """
    operator: str = ""
    operand: TagNode = None


@dataclass
class FunctionCallNode(TagNode):
    """
    A function call in a formula.

    Example: SUM(items.price), ROUND(amount, 2), IF(cond, a, b)
    """
    name: str = ""
    arguments: List[TagNode] = field(default_factory=list)


@dataclass
class FormulaNode(TagNode):
    """
    A formula expression (starts with =).

    Example: {{= price * 1.1}}, {{= SUM(items.amount)}}
    """
    expression: TagNode = None


@dataclass
class ConditionNode(TagNode):
    """
    A condition for IF statements.

    Can be a simple comparison or a complex logical expression.
    """
    expression: TagNode = None


@dataclass
class ConditionalNode(TagNode):
    """
    A conditional block (IF/ELSE/ENDIF).

    Example:
        {{IF amount > 1000}}
        You get a discount!
        {{ELSE}}
        No discount available.
        {{ENDIF}}
    """
    condition: ConditionNode = None
    true_branch: List[TagNode] = field(default_factory=list)
    false_branch: List[TagNode] = field(default_factory=list)


@dataclass
class LoopNode(TagNode):
    """
    A loop block (FOR/ENDFOR).

    Example:
        {{FOR item IN trigger.deal.line_items}}
        - {{item.name}}: {{item.price}}
        {{ENDFOR}}
    """
    item_name: str = ""
    collection: TagNode = None  # VariableNode referencing the collection
    body: List[TagNode] = field(default_factory=list)


@dataclass
class DocumentNode(TagNode):
    """
    Root node containing all parsed content.

    A document is a sequence of text and tag nodes.
    """
    children: List[TagNode] = field(default_factory=list)


# Type alias for any expression node
ExpressionNode = Union[
    VariableNode,
    GlobalVarNode,
    NumberNode,
    StringNode,
    BinaryOpNode,
    LogicalOpNode,
    UnaryOpNode,
    FunctionCallNode
]
