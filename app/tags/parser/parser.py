"""
Parser for the Tag System

Converts tokens from the lexer into an Abstract Syntax Tree (AST).

Supports:
- Simple variables: {{trigger.deal.name}}
- Pipes: {{value | upper | truncate:100}}
- Formulas: {{= price * 1.1}}
- Conditionals: {{IF condition}}...{{ELSE}}...{{ENDIF}}
- Loops: {{FOR item IN items}}...{{ENDFOR}}
- Global vars: {{$timestamp}}
"""

from typing import List, Optional, Set
import re

from app.tags.parser.lexer import Lexer, Token, TokenType, LexerError
from app.tags.parser.ast import (
    TagNode,
    DocumentNode,
    TextNode,
    VariableNode,
    GlobalVarNode,
    FormulaNode,
    ConditionalNode,
    ConditionNode,
    LoopNode,
    TransformNode,
    NumberNode,
    StringNode,
    BinaryOpNode,
    LogicalOpNode,
    UnaryOpNode,
    FunctionCallNode,
    MathOp,
    ComparisonOp,
    LogicalOp
)


class ParseError(Exception):
    """Error during parsing."""
    def __init__(self, message: str, token: Token = None):
        self.token = token
        if token:
            super().__init__(f"{message} at position {token.position}")
        else:
            super().__init__(message)


class TagParser:
    """
    Parser for tag syntax.

    Converts tokenized input into an AST for evaluation.
    """

    MATH_OPS = {
        TokenType.PLUS: MathOp.ADD,
        TokenType.MINUS: MathOp.SUB,
        TokenType.MULTIPLY: MathOp.MUL,
        TokenType.DIVIDE: MathOp.DIV,
        TokenType.MODULO: MathOp.MOD,
    }

    COMPARISON_OPS = {
        TokenType.EQUALS_EQUALS: ComparisonOp.EQ,
        TokenType.NOT_EQUALS: ComparisonOp.NE,
        TokenType.GT: ComparisonOp.GT,
        TokenType.GTE: ComparisonOp.GTE,
        TokenType.LT: ComparisonOp.LT,
        TokenType.LTE: ComparisonOp.LTE,
        TokenType.CONTAINS: ComparisonOp.CONTAINS,
    }

    def __init__(self):
        self.tokens: List[Token] = []
        self.pos = 0
        self._tag_count = 0
        self._extracted_tags: Set[str] = set()

    def parse(self, text: str) -> DocumentNode:
        """
        Parse text into a DocumentNode AST.

        Args:
            text: Text containing tags to parse

        Returns:
            DocumentNode containing the parsed structure
        """
        lexer = Lexer(text)
        self.tokens = lexer.tokenize()
        self.pos = 0
        self._tag_count = 0

        children = []

        while not self._is_at_end():
            node = self._parse_content()
            if node:
                children.append(node)

        return DocumentNode(children=children)

    def extract_tags(self, text: str) -> List[str]:
        """
        Extract all tag strings from text without full parsing.

        Args:
            text: Text containing tags

        Returns:
            List of tag strings (including delimiters)
        """
        # Simple regex extraction for quick tag listing
        pattern = r'\{\{[^}]+\}\}'
        return re.findall(pattern, text)

    def validate(self, text: str) -> dict:
        """
        Validate tags in text.

        Returns:
            Dict with 'valid', 'errors', 'warnings'
        """
        errors = []
        warnings = []

        try:
            self.parse(text)
            valid = True
        except (ParseError, LexerError) as e:
            valid = False
            errors.append(str(e))

        return {
            'valid': valid,
            'errors': errors,
            'warnings': warnings
        }

    def get_tag_count(self) -> int:
        """Get count of tags found during last parse."""
        return self._tag_count

    def _parse_content(self) -> Optional[TagNode]:
        """Parse content (text or tag)."""
        if self._is_at_end():
            return None

        token = self._current()

        if token.type == TokenType.TEXT:
            self._advance()
            return TextNode(content=token.value, position=token.position)

        if token.type == TokenType.OPEN_TAG:
            return self._parse_tag()

        # Skip unexpected tokens
        self._advance()
        return None

    def _parse_tag(self) -> TagNode:
        """Parse a complete tag (from {{ to }})."""
        self._expect(TokenType.OPEN_TAG)
        self._tag_count += 1

        token = self._current()

        # Formula: {{= expression}}
        if token.type == TokenType.EQUALS:
            return self._parse_formula()

        # Global variable: {{$name}}
        if token.type == TokenType.DOLLAR:
            return self._parse_global_var()

        # Keywords: IF, FOR, ELSE, ENDIF, ENDFOR
        if token.type == TokenType.IF:
            return self._parse_conditional()

        if token.type == TokenType.FOR:
            return self._parse_loop()

        if token.type in (TokenType.ELSE, TokenType.ENDIF, TokenType.ENDFOR):
            # These are handled by their parent parsers
            # Return a marker that the parent will handle
            return self._parse_block_keyword()

        # Variable with optional transforms: {{path | transform}}
        return self._parse_variable()

    def _parse_formula(self) -> FormulaNode:
        """Parse a formula: {{= expression}}"""
        start_pos = self._current().position
        self._expect(TokenType.EQUALS)

        expression = self._parse_expression()

        self._expect(TokenType.CLOSE_TAG)

        return FormulaNode(expression=expression, position=start_pos)

    def _parse_global_var(self) -> GlobalVarNode:
        """Parse a global variable: {{$name}}"""
        start_pos = self._current().position
        self._expect(TokenType.DOLLAR)

        name_token = self._expect(TokenType.IDENTIFIER)

        self._expect(TokenType.CLOSE_TAG)

        return GlobalVarNode(name=name_token.value, position=start_pos)

    def _parse_variable(self) -> VariableNode:
        """Parse a variable reference with optional transforms."""
        start_pos = self._current().position

        # Parse path: trigger.deal.amount
        path = self._parse_path()

        # Parse optional index: [0]
        index = None
        if self._check(TokenType.LBRACKET):
            self._advance()
            num_token = self._expect(TokenType.NUMBER)
            index = int(num_token.value)
            self._expect(TokenType.RBRACKET)

        # Parse optional transforms: | transform:param
        transforms = []
        while self._check(TokenType.PIPE):
            self._advance()
            transforms.append(self._parse_transform())

        self._expect(TokenType.CLOSE_TAG)

        return VariableNode(
            path=path,
            transforms=transforms,
            index=index,
            position=start_pos
        )

    def _parse_path(self) -> List[str]:
        """Parse a dotted path: trigger.deal.amount"""
        path = []

        token = self._expect(TokenType.IDENTIFIER)
        path.append(token.value)

        while self._check(TokenType.DOT):
            self._advance()
            token = self._expect(TokenType.IDENTIFIER)
            path.append(token.value)

        return path

    def _parse_transform(self) -> TransformNode:
        """Parse a transform: name:param1:param2"""
        start_pos = self._current().position

        name_token = self._expect(TokenType.IDENTIFIER)
        params = []

        # Parse parameters after colon
        while self._check(TokenType.COLON):
            self._advance()
            param = self._parse_transform_param()
            params.append(param)

        return TransformNode(name=name_token.value, params=params, position=start_pos)

    def _parse_transform_param(self):
        """Parse a transform parameter (string, number, or identifier)."""
        token = self._current()

        if token.type == TokenType.STRING:
            self._advance()
            return token.value

        if token.type == TokenType.NUMBER:
            self._advance()
            return float(token.value) if '.' in token.value else int(token.value)

        if token.type == TokenType.IDENTIFIER:
            self._advance()
            return token.value

        raise ParseError(f"Expected transform parameter, got {token.type}", token)

    def _parse_conditional(self) -> ConditionalNode:
        """
        Parse a conditional block:
        {{IF condition}}
        true content
        {{ELSE}}
        false content
        {{ENDIF}}
        """
        start_pos = self._current().position
        self._expect(TokenType.IF)

        # Parse condition
        condition = self._parse_condition()

        self._expect(TokenType.CLOSE_TAG)

        # Parse true branch until ELSE or ENDIF
        true_branch = []
        false_branch = []

        while not self._is_at_end():
            # Check for ELSE or ENDIF
            if self._check(TokenType.OPEN_TAG):
                # Peek ahead to see what keyword follows
                saved_pos = self.pos
                self._advance()  # Skip {{

                if self._check(TokenType.ELSE):
                    self._advance()  # Skip ELSE
                    self._expect(TokenType.CLOSE_TAG)
                    break
                elif self._check(TokenType.ENDIF):
                    self._advance()  # Skip ENDIF
                    self._expect(TokenType.CLOSE_TAG)
                    return ConditionalNode(
                        condition=ConditionNode(expression=condition),
                        true_branch=true_branch,
                        false_branch=[],
                        position=start_pos
                    )
                else:
                    # Not a block keyword, restore position
                    self.pos = saved_pos

            node = self._parse_content()
            if node:
                true_branch.append(node)

        # Parse false branch until ENDIF
        while not self._is_at_end():
            if self._check(TokenType.OPEN_TAG):
                saved_pos = self.pos
                self._advance()

                if self._check(TokenType.ENDIF):
                    self._advance()
                    self._expect(TokenType.CLOSE_TAG)
                    break
                else:
                    self.pos = saved_pos

            node = self._parse_content()
            if node:
                false_branch.append(node)

        return ConditionalNode(
            condition=ConditionNode(expression=condition),
            true_branch=true_branch,
            false_branch=false_branch,
            position=start_pos
        )

    def _parse_condition(self) -> TagNode:
        """Parse a condition expression."""
        return self._parse_logical_or()

    def _parse_logical_or(self) -> TagNode:
        """Parse OR expressions."""
        left = self._parse_logical_and()

        while self._check(TokenType.OR):
            self._advance()
            right = self._parse_logical_and()
            left = LogicalOpNode(left=left, operator=LogicalOp.OR, right=right)

        return left

    def _parse_logical_and(self) -> TagNode:
        """Parse AND expressions."""
        left = self._parse_comparison()

        while self._check(TokenType.AND):
            self._advance()
            right = self._parse_comparison()
            left = LogicalOpNode(left=left, operator=LogicalOp.AND, right=right)

        return left

    def _parse_comparison(self) -> TagNode:
        """Parse comparison expressions."""
        left = self._parse_expression()

        if self._current().type in self.COMPARISON_OPS:
            op = self.COMPARISON_OPS[self._current().type]
            self._advance()
            right = self._parse_expression()
            return BinaryOpNode(left=left, operator=op, right=right)

        return left

    def _parse_expression(self) -> TagNode:
        """Parse a mathematical expression."""
        return self._parse_additive()

    def _parse_additive(self) -> TagNode:
        """Parse addition and subtraction."""
        left = self._parse_multiplicative()

        while self._current().type in (TokenType.PLUS, TokenType.MINUS):
            op = self.MATH_OPS[self._current().type]
            self._advance()
            right = self._parse_multiplicative()
            left = BinaryOpNode(left=left, operator=op, right=right)

        return left

    def _parse_multiplicative(self) -> TagNode:
        """Parse multiplication, division, modulo."""
        left = self._parse_unary()

        while self._current().type in (TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO):
            op = self.MATH_OPS[self._current().type]
            self._advance()
            right = self._parse_unary()
            left = BinaryOpNode(left=left, operator=op, right=right)

        return left

    def _parse_unary(self) -> TagNode:
        """Parse unary operators (-, !)."""
        if self._check(TokenType.MINUS):
            self._advance()
            operand = self._parse_unary()
            return UnaryOpNode(operator='-', operand=operand)

        if self._check(TokenType.NOT):
            self._advance()
            operand = self._parse_unary()
            return UnaryOpNode(operator='!', operand=operand)

        return self._parse_primary()

    def _parse_primary(self) -> TagNode:
        """Parse primary expressions (literals, variables, function calls, parentheses)."""
        token = self._current()

        # Number literal
        if token.type == TokenType.NUMBER:
            self._advance()
            value = float(token.value) if '.' in token.value else int(token.value)
            return NumberNode(value=value, position=token.position)

        # String literal
        if token.type == TokenType.STRING:
            self._advance()
            return StringNode(value=token.value, position=token.position)

        # Global variable
        if token.type == TokenType.DOLLAR:
            self._advance()
            name_token = self._expect(TokenType.IDENTIFIER)
            return GlobalVarNode(name=name_token.value, position=token.position)

        # Identifier (variable or function call)
        if token.type == TokenType.IDENTIFIER:
            return self._parse_identifier_or_call()

        # Parenthesized expression
        if token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        raise ParseError(f"Unexpected token in expression: {token.type}", token)

    def _parse_identifier_or_call(self) -> TagNode:
        """Parse an identifier (variable path) or function call."""
        token = self._current()

        # Check if it's a function call: NAME(args)
        if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.LPAREN:
            return self._parse_function_call()

        # Otherwise it's a variable path
        path = self._parse_path()

        # Check for array index
        index = None
        if self._check(TokenType.LBRACKET):
            self._advance()
            num_token = self._expect(TokenType.NUMBER)
            index = int(num_token.value)
            self._expect(TokenType.RBRACKET)

        return VariableNode(path=path, index=index, position=token.position)

    def _parse_function_call(self) -> FunctionCallNode:
        """Parse a function call: NAME(arg1, arg2, ...)"""
        name_token = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.LPAREN)

        arguments = []

        if not self._check(TokenType.RPAREN):
            arguments.append(self._parse_expression())

            while self._check(TokenType.COMMA):
                self._advance()
                arguments.append(self._parse_expression())

        self._expect(TokenType.RPAREN)

        return FunctionCallNode(
            name=name_token.value.upper(),  # Normalize to uppercase
            arguments=arguments,
            position=name_token.position
        )

    def _parse_loop(self) -> LoopNode:
        """
        Parse a loop block:
        {{FOR item IN collection}}
        body
        {{ENDFOR}}
        """
        start_pos = self._current().position
        self._expect(TokenType.FOR)

        # Parse item name
        item_token = self._expect(TokenType.IDENTIFIER)

        # Expect IN keyword
        self._expect(TokenType.IN)

        # Parse collection path
        collection_path = self._parse_path()

        self._expect(TokenType.CLOSE_TAG)

        # Parse body until ENDFOR
        body = []

        while not self._is_at_end():
            if self._check(TokenType.OPEN_TAG):
                saved_pos = self.pos
                self._advance()

                if self._check(TokenType.ENDFOR):
                    self._advance()
                    self._expect(TokenType.CLOSE_TAG)
                    break
                else:
                    self.pos = saved_pos

            node = self._parse_content()
            if node:
                body.append(node)

        return LoopNode(
            item_name=item_token.value,
            collection=VariableNode(path=collection_path),
            body=body,
            position=start_pos
        )

    def _parse_block_keyword(self) -> TagNode:
        """
        Handle standalone block keywords (ELSE, ENDIF, ENDFOR).
        These should be consumed by their parent parsers.
        """
        token = self._current()
        raise ParseError(f"Unexpected {token.type.name} outside of block", token)

    # Helper methods

    def _current(self) -> Token:
        """Get current token."""
        if self.pos >= len(self.tokens):
            return Token(TokenType.EOF, '', len(self.tokens))
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        """Advance and return previous token."""
        token = self._current()
        if not self._is_at_end():
            self.pos += 1
        return token

    def _check(self, token_type: TokenType) -> bool:
        """Check if current token is of given type."""
        return self._current().type == token_type

    def _expect(self, token_type: TokenType) -> Token:
        """Expect current token to be of given type, advance, and return it."""
        token = self._current()
        if token.type != token_type:
            raise ParseError(f"Expected {token_type.name}, got {token.type.name}", token)
        return self._advance()

    def _is_at_end(self) -> bool:
        """Check if we've reached end of tokens."""
        return self._current().type == TokenType.EOF
