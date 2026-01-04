"""
Base classes for Pieces/Apps system
Inspired by Activepieces architecture
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Awaitable, Union
from enum import Enum
import abc


class PropertyType(str, Enum):
    """Types of properties for piece configuration"""
    SHORT_TEXT = "SHORT_TEXT"
    LONG_TEXT = "LONG_TEXT"
    NUMBER = "NUMBER"
    CHECKBOX = "CHECKBOX"
    DROPDOWN = "DROPDOWN"
    DYNAMIC_DROPDOWN = "DYNAMIC_DROPDOWN"
    ARRAY = "ARRAY"
    OBJECT = "OBJECT"
    JSON = "JSON"
    DATE_TIME = "DATE_TIME"
    FILE = "FILE"
    MARKDOWN = "MARKDOWN"


class AuthType(str, Enum):
    """Types of authentication"""
    OAUTH2 = "OAUTH2"
    PLATFORM_OAUTH2 = "PLATFORM_OAUTH2"
    CLOUD_OAUTH2 = "CLOUD_OAUTH2"
    SECRET_TEXT = "SECRET_TEXT"
    BASIC_AUTH = "BASIC_AUTH"
    CUSTOM_AUTH = "CUSTOM_AUTH"
    NO_AUTH = "NO_AUTH"


@dataclass
class Property:
    """
    Property definition for piece configuration
    """
    name: str
    display_name: str
    description: str
    type: PropertyType
    required: bool = False
    default_value: Any = None
    placeholder: str = ""

    # For DROPDOWN
    options: Optional[List[Dict[str, str]]] = None  # [{"label": "...", "value": "..."}]

    # For DYNAMIC_DROPDOWN
    refresh_on_search: bool = False
    refresh_params: List[str] = field(default_factory=list)


@dataclass
class OAuth2Config:
    """OAuth2 configuration"""
    auth_url: str
    token_url: str
    required: bool = True
    scope: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Auth:
    """Authentication configuration for a piece"""
    type: AuthType
    required: bool = True

    # For OAuth2
    oauth2_config: Optional[OAuth2Config] = None

    # For SECRET_TEXT, BASIC_AUTH, CUSTOM_AUTH
    properties: List[Property] = field(default_factory=list)


@dataclass
class ExecutionContext:
    """
    Context provided to piece actions during execution
    """
    # Credentials for this piece
    credentials: Dict[str, Any]

    # Store for persistent data
    store: Dict[str, Any]

    # Project ID
    project_id: str

    # Trigger output (for accessing trigger data)
    trigger_output: Optional[Dict[str, Any]] = None

    # Previous steps output
    steps_output: Dict[str, Any] = field(default_factory=dict)

    # Files (for file handling)
    files: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result from executing an action"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None  # {"message": "..."}


# Type aliases
ActionHandler = Callable[[Dict[str, Any], ExecutionContext], Awaitable[ActionResult]]
TriggerHandler = Callable[[Dict[str, Any], ExecutionContext], Awaitable[ActionResult]]


@dataclass
class Action:
    """
    Action definition - an operation a piece can perform
    """
    name: str
    display_name: str
    description: str
    properties: List[Property]
    handler: ActionHandler

    # UI hints
    require_auth: bool = True
    icon: Optional[str] = None  # Icon name or SVG


@dataclass
class Trigger:
    """
    Trigger definition - an event that starts a workflow
    """
    name: str
    display_name: str
    description: str
    type: str  # "WEBHOOK", "POLLING", "APP", "PIECE_TRIGGER"
    properties: List[Property]
    handler: Optional[TriggerHandler] = None

    # For webhook triggers
    handshake_config: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None


@dataclass
class Piece:
    """
    Piece definition - a complete integration/app
    """
    name: str  # Unique ID (e.g., "hubspot", "gmail")
    display_name: str
    description: str
    version: str
    logo_url: Optional[str] = None

    # Authentication
    auth: Optional[Auth] = None

    # Capabilities
    actions: List[Action] = field(default_factory=list)
    triggers: List[Trigger] = field(default_factory=list)

    # Categories for organization
    categories: List[str] = field(default_factory=list)

    # Minimum plan required (free, pro, enterprise)
    min_plan: str = "free"


class PieceRegistry:
    """
    Registry for all pieces
    Singleton pattern
    """
    _instance = None
    _pieces: Dict[str, Piece] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._pieces = {}
        return cls._instance

    def register(self, piece: Piece):
        """Register a piece"""
        self._pieces[piece.name] = piece

    def get(self, piece_name: str) -> Optional[Piece]:
        """Get a piece by name"""
        return self._pieces.get(piece_name)

    def get_all(self) -> Dict[str, Piece]:
        """Get all registered pieces"""
        return self._pieces.copy()

    def get_action(self, piece_name: str, action_name: str) -> Optional[Action]:
        """Get an action from a piece"""
        piece = self.get(piece_name)
        if not piece:
            return None

        for action in piece.actions:
            if action.name == action_name:
                return action

        return None

    def get_trigger(self, piece_name: str, trigger_name: str) -> Optional[Trigger]:
        """Get a trigger from a piece"""
        piece = self.get(piece_name)
        if not piece:
            return None

        for trigger in piece.triggers:
            if trigger.name == trigger_name:
                return trigger

        return None


# Global registry instance
registry = PieceRegistry()


def register_piece(piece: Piece):
    """Register a piece in the global registry"""
    registry.register(piece)


def get_piece(piece_name: str) -> Optional[Piece]:
    """Get a piece from the global registry"""
    return registry.get(piece_name)


def get_all_pieces() -> Dict[str, Piece]:
    """Get all pieces from the global registry"""
    return registry.get_all()


# Helper functions for creating common properties
def short_text_property(
    name: str,
    display_name: str,
    description: str,
    required: bool = False,
    placeholder: str = ""
) -> Property:
    """Create a short text property"""
    return Property(
        name=name,
        display_name=display_name,
        description=description,
        type=PropertyType.SHORT_TEXT,
        required=required,
        placeholder=placeholder
    )


def long_text_property(
    name: str,
    display_name: str,
    description: str,
    required: bool = False,
    placeholder: str = ""
) -> Property:
    """Create a long text property"""
    return Property(
        name=name,
        display_name=display_name,
        description=description,
        type=PropertyType.LONG_TEXT,
        required=required,
        placeholder=placeholder
    )


def dropdown_property(
    name: str,
    display_name: str,
    description: str,
    options: List[Dict[str, str]],
    required: bool = False
) -> Property:
    """Create a dropdown property"""
    return Property(
        name=name,
        display_name=display_name,
        description=description,
        type=PropertyType.DROPDOWN,
        required=required,
        options=options
    )


def checkbox_property(
    name: str,
    display_name: str,
    description: str,
    default_value: bool = False
) -> Property:
    """Create a checkbox property"""
    return Property(
        name=name,
        display_name=display_name,
        description=description,
        type=PropertyType.CHECKBOX,
        required=False,
        default_value=default_value
    )
