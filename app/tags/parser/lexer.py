"""
Lexer for the Tag System

Tokenizes tag syntax into tokens for parsing.

Supported syntax:
- Variables: {{trigger.deal.amount}}
- Pipes: {{value | transform:param}}
- Formulas: {{= expression}}
- Global vars: {{$timestamp}}
- Conditionals: {{IF}}, {{ELSE}}, {{ENDIF}}
- Loops: {{FOR item IN items}}, {{ENDFOR}}
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import re


class TokenType(Enum):
    """Token types for the tag lexer."""
    # Literals
    TEXT = 'TEXT'
    STRING = 'STRING'
    NUMBER = 'NUMBER'
    IDENTIFIER = 'IDENTIFIER'

    # Delimiters
    OPEN_TAG = 'OPEN_TAG'       # {{
    CLOSE_TAG = 'CLOSE_TAG'     # }}
    PIPE = 'PIPE'               # |
    COLON = 'COLON'             # :
    DOT = 'DOT'                 # .
    COMMA = 'COMMA'             # ,
    LPAREN = 'LPAREN'           # (
    RPAREN = 'RPAREN'           # )
    LBRACKET = 'LBRACKET'       # [
    RBRACKET = 'RBRACKET'       # ]

    # Operators
    EQUALS = 'EQUALS'           # = (formula marker or comparison)
    EQUALS_EQUALS = 'EQUALS_EQUALS'  # ==
    NOT_EQUALS = 'NOT_EQUALS'   # !=
    GT = 'GT'                   # >
    GTE = 'GTE'                 # >=
    LT = 'LT'                   # <
    LTE = 'LTE'                 # <=
    CONTAINS = 'CONTAINS'       # ~
    AND = 'AND'                 # &&
    OR = 'OR'                   # ||
    NOT = 'NOT'                 # !

    # Math operators
    PLUS = 'PLUS'               # +
    MINUS = 'MINUS'             # -
    MULTIPLY = 'MULTIPLY'       # *
    DIVIDE = 'DIVIDE'           # /
    MODULO = 'MODULO'           # %

    # Special
    DOLLAR = 'DOLLAR'           # $ (global var marker)

    # Keywords
    IF = 'IF'
    ELSE = 'ELSE'
    ENDIF = 'ENDIF'
    FOR = 'FOR'
    IN = 'IN'
    ENDFOR = 'ENDFOR'

    # End of input
    EOF = 'EOF'


@dataclass
class Token:
    """A token produced by the lexer."""
    type: TokenType
    value: str
    position: int
    line: int = 1
    column: int = 1

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, pos={self.position})"


class LexerError(Exception):
    """Error during lexing."""
    def __init__(self, message: str, position: int, line: int = 1, column: int = 1):
        self.position = position
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


class Lexer:
    """
    Lexer for tag syntax.

    Operates in two modes:
    - Outside tags: collects TEXT tokens
    - Inside tags: tokenizes tag content
    """

    KEYWORDS = {
        'IF': TokenType.IF,
        'ELSE': TokenType.ELSE,
        'ENDIF': TokenType.ENDIF,
        'FOR': TokenType.FOR,
        'IN': TokenType.IN,
        'ENDFOR': TokenType.ENDFOR,
    }

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.inside_tag = False

    def tokenize(self) -> List[Token]:
        """
        Tokenize the entire input text.

        Returns:
            List of tokens
        """
        self.tokens = []
        self.pos = 0
        self.line = 1
        self.column = 1
        self.inside_tag = False

        while self.pos < len(self.text):
            if self.inside_tag:
                self._tokenize_inside_tag()
            else:
                self._tokenize_outside_tag()

        self.tokens.append(Token(TokenType.EOF, '', self.pos, self.line, self.column))
        return self.tokens

    def _tokenize_outside_tag(self):
        """Collect text until we hit {{ or end of input."""
        start_pos = self.pos
        start_line = self.line
        start_col = self.column
        text_content = []

        while self.pos < len(self.text):
            # Check for tag opening
            if self._peek(2) == '{{':
                break

            char = self._advance()
            text_content.append(char)

        if text_content:
            self.tokens.append(Token(
                TokenType.TEXT,
                ''.join(text_content),
                start_pos,
                start_line,
                start_col
            ))

        # Handle tag opening if found
        if self._peek(2) == '{{':
            self._advance()  # {
            self._advance()  # {
            self.tokens.append(Token(
                TokenType.OPEN_TAG,
                '{{',
                self.pos - 2,
                self.line,
                self.column - 2
            ))
            self.inside_tag = True

    def _tokenize_inside_tag(self):
        """Tokenize content inside a tag."""
        self._skip_whitespace()

        if self.pos >= len(self.text):
            raise LexerError("Unclosed tag", self.pos, self.line, self.column)

        # Check for tag closing
        if self._peek(2) == '}}':
            self._advance()  # }
            self._advance()  # }
            self.tokens.append(Token(
                TokenType.CLOSE_TAG,
                '}}',
                self.pos - 2,
                self.line,
                self.column - 2
            ))
            self.inside_tag = False
            return

        char = self._current()

        # Two-character operators (must check before single char)
        if self._peek(2) == '==':
            self._advance()
            self._advance()
            self.tokens.append(Token(TokenType.EQUALS_EQUALS, '==', self.pos - 2, self.line, self.column - 2))
        elif self._peek(2) == '!=':
            self._advance()
            self._advance()
            self.tokens.append(Token(TokenType.NOT_EQUALS, '!=', self.pos - 2, self.line, self.column - 2))
        elif self._peek(2) == '>=':
            self._advance()
            self._advance()
            self.tokens.append(Token(TokenType.GTE, '>=', self.pos - 2, self.line, self.column - 2))
        elif self._peek(2) == '<=':
            self._advance()
            self._advance()
            self.tokens.append(Token(TokenType.LTE, '<=', self.pos - 2, self.line, self.column - 2))
        elif self._peek(2) == '&&':
            self._advance()
            self._advance()
            self.tokens.append(Token(TokenType.AND, '&&', self.pos - 2, self.line, self.column - 2))
        elif self._peek(2) == '||':
            self._advance()
            self._advance()
            self.tokens.append(Token(TokenType.OR, '||', self.pos - 2, self.line, self.column - 2))

        # Single character tokens
        elif char == '|':
            self._advance()
            self.tokens.append(Token(TokenType.PIPE, '|', self.pos - 1, self.line, self.column - 1))
        elif char == ':':
            self._advance()
            self.tokens.append(Token(TokenType.COLON, ':', self.pos - 1, self.line, self.column - 1))
        elif char == '.':
            self._advance()
            self.tokens.append(Token(TokenType.DOT, '.', self.pos - 1, self.line, self.column - 1))
        elif char == ',':
            self._advance()
            self.tokens.append(Token(TokenType.COMMA, ',', self.pos - 1, self.line, self.column - 1))
        elif char == '(':
            self._advance()
            self.tokens.append(Token(TokenType.LPAREN, '(', self.pos - 1, self.line, self.column - 1))
        elif char == ')':
            self._advance()
            self.tokens.append(Token(TokenType.RPAREN, ')', self.pos - 1, self.line, self.column - 1))
        elif char == '[':
            self._advance()
            self.tokens.append(Token(TokenType.LBRACKET, '[', self.pos - 1, self.line, self.column - 1))
        elif char == ']':
            self._advance()
            self.tokens.append(Token(TokenType.RBRACKET, ']', self.pos - 1, self.line, self.column - 1))
        elif char == '=':
            self._advance()
            self.tokens.append(Token(TokenType.EQUALS, '=', self.pos - 1, self.line, self.column - 1))
        elif char == '>':
            self._advance()
            self.tokens.append(Token(TokenType.GT, '>', self.pos - 1, self.line, self.column - 1))
        elif char == '<':
            self._advance()
            self.tokens.append(Token(TokenType.LT, '<', self.pos - 1, self.line, self.column - 1))
        elif char == '~':
            self._advance()
            self.tokens.append(Token(TokenType.CONTAINS, '~', self.pos - 1, self.line, self.column - 1))
        elif char == '!':
            self._advance()
            self.tokens.append(Token(TokenType.NOT, '!', self.pos - 1, self.line, self.column - 1))
        elif char == '+':
            self._advance()
            self.tokens.append(Token(TokenType.PLUS, '+', self.pos - 1, self.line, self.column - 1))
        elif char == '-':
            self._advance()
            self.tokens.append(Token(TokenType.MINUS, '-', self.pos - 1, self.line, self.column - 1))
        elif char == '*':
            self._advance()
            self.tokens.append(Token(TokenType.MULTIPLY, '*', self.pos - 1, self.line, self.column - 1))
        elif char == '/':
            self._advance()
            self.tokens.append(Token(TokenType.DIVIDE, '/', self.pos - 1, self.line, self.column - 1))
        elif char == '%':
            self._advance()
            self.tokens.append(Token(TokenType.MODULO, '%', self.pos - 1, self.line, self.column - 1))
        elif char == '$':
            self._advance()
            self.tokens.append(Token(TokenType.DOLLAR, '$', self.pos - 1, self.line, self.column - 1))

        # String literals
        elif char == '"' or char == "'":
            self._read_string(char)

        # Numbers
        elif char.isdigit():
            self._read_number()

        # Identifiers and keywords
        elif char.isalpha() or char == '_':
            self._read_identifier()

        else:
            raise LexerError(f"Unexpected character: {char!r}", self.pos, self.line, self.column)

    def _read_string(self, quote_char: str):
        """Read a string literal."""
        start_pos = self.pos
        start_line = self.line
        start_col = self.column

        self._advance()  # Opening quote
        chars = []

        while self.pos < len(self.text):
            char = self._current()

            if char == quote_char:
                self._advance()  # Closing quote
                self.tokens.append(Token(
                    TokenType.STRING,
                    ''.join(chars),
                    start_pos,
                    start_line,
                    start_col
                ))
                return

            if char == '\\' and self.pos + 1 < len(self.text):
                # Escape sequence
                self._advance()
                next_char = self._advance()
                if next_char == 'n':
                    chars.append('\n')
                elif next_char == 't':
                    chars.append('\t')
                elif next_char == 'r':
                    chars.append('\r')
                else:
                    chars.append(next_char)
            else:
                chars.append(self._advance())

        raise LexerError("Unterminated string", start_pos, start_line, start_col)

    def _read_number(self):
        """Read a number literal (int or float)."""
        start_pos = self.pos
        start_line = self.line
        start_col = self.column
        chars = []
        has_dot = False

        while self.pos < len(self.text):
            char = self._current()

            if char.isdigit():
                chars.append(self._advance())
            elif char == '.' and not has_dot:
                # Check if next char is also a digit (to distinguish from dot access)
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit():
                    has_dot = True
                    chars.append(self._advance())
                else:
                    break
            else:
                break

        self.tokens.append(Token(
            TokenType.NUMBER,
            ''.join(chars),
            start_pos,
            start_line,
            start_col
        ))

    def _read_identifier(self):
        """Read an identifier or keyword."""
        start_pos = self.pos
        start_line = self.line
        start_col = self.column
        chars = []

        while self.pos < len(self.text):
            char = self._current()
            if char.isalnum() or char == '_':
                chars.append(self._advance())
            else:
                break

        value = ''.join(chars)

        # Check if it's a keyword
        token_type = self.KEYWORDS.get(value.upper(), TokenType.IDENTIFIER)

        self.tokens.append(Token(
            token_type,
            value,
            start_pos,
            start_line,
            start_col
        ))

    def _current(self) -> str:
        """Get current character."""
        if self.pos >= len(self.text):
            return ''
        return self.text[self.pos]

    def _peek(self, count: int = 1) -> str:
        """Peek ahead without advancing."""
        return self.text[self.pos:self.pos + count]

    def _advance(self) -> str:
        """Advance position and return current character."""
        if self.pos >= len(self.text):
            return ''

        char = self.text[self.pos]
        self.pos += 1

        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return char

    def _skip_whitespace(self):
        """Skip whitespace characters inside tags."""
        while self.pos < len(self.text) and self.text[self.pos] in ' \t\n\r':
            self._advance()
