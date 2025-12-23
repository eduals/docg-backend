"""
Tests for app/engine/validate_parameters.py

FASE 2: Validacao de Arguments
"""

import pytest
from dataclasses import dataclass
from typing import Optional
from enum import Enum


# Mock ArgumentType enum
class MockArgumentType(Enum):
    STRING = 'string'
    NUMBER = 'number'
    BOOLEAN = 'boolean'
    JSON = 'json'
    DROPDOWN = 'dropdown'


# Mock ActionArgument class
@dataclass
class MockActionArgument:
    key: str
    label: str
    type: MockArgumentType = MockArgumentType.STRING
    required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None


class TestValidateParameters:
    """Tests for validate_parameters()"""

    def test_required_field_missing(self):
        """Required field with None value should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='email', label='Email', required=True)
        ]
        params = {}

        errors = validate_parameters(params, args)
        assert 'email' in errors
        assert "'Email' is required" in errors['email'][0]

    def test_required_field_empty_string(self):
        """Required field with empty string should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='name', label='Name', required=True)
        ]
        params = {'name': ''}

        errors = validate_parameters(params, args)
        assert 'name' in errors

    def test_required_field_valid(self):
        """Required field with value should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='email', label='Email', required=True)
        ]
        params = {'email': 'test@example.com'}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_optional_field_missing(self):
        """Optional field missing should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='nickname', label='Nickname', required=False)
        ]
        params = {}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_number_type_invalid(self):
        """Number field with string should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='age', label='Age', type=MockArgumentType.NUMBER)
        ]
        params = {'age': 'not a number'}

        errors = validate_parameters(params, args)
        assert 'age' in errors

    def test_number_type_valid_int(self):
        """Number field with int should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='count', label='Count', type=MockArgumentType.NUMBER)
        ]
        params = {'count': 42}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_number_type_valid_float(self):
        """Number field with float should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='price', label='Price', type=MockArgumentType.NUMBER)
        ]
        params = {'price': 19.99}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_number_type_string_number(self):
        """Number field with string number should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='quantity', label='Quantity', type=MockArgumentType.NUMBER)
        ]
        params = {'quantity': '123'}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_boolean_type_invalid(self):
        """Boolean field with invalid string should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='active', label='Active', type=MockArgumentType.BOOLEAN)
        ]
        params = {'active': 'maybe'}

        errors = validate_parameters(params, args)
        assert 'active' in errors

    def test_boolean_type_valid_bool(self):
        """Boolean field with bool should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='active', label='Active', type=MockArgumentType.BOOLEAN)
        ]
        params = {'active': True}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_boolean_type_valid_string(self):
        """Boolean field with 'true'/'false' string should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='active', label='Active', type=MockArgumentType.BOOLEAN)
        ]

        for val in ['true', 'false', 'True', 'False', '1', '0']:
            params = {'active': val}
            errors = validate_parameters(params, args)
            assert errors == {}

    def test_json_type_invalid(self):
        """JSON field with invalid JSON should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='config', label='Config', type=MockArgumentType.JSON)
        ]
        params = {'config': '{invalid json}'}

        errors = validate_parameters(params, args)
        assert 'config' in errors

    def test_json_type_valid(self):
        """JSON field with valid JSON should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='config', label='Config', type=MockArgumentType.JSON)
        ]
        params = {'config': '{"key": "value"}'}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_min_value_validation(self):
        """Number below min_value should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='quantity', label='Quantity', min_value=1)
        ]
        params = {'quantity': 0}

        errors = validate_parameters(params, args)
        assert 'quantity' in errors
        assert '>= 1' in errors['quantity'][0]

    def test_max_value_validation(self):
        """Number above max_value should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='percentage', label='Percentage', max_value=100)
        ]
        params = {'percentage': 150}

        errors = validate_parameters(params, args)
        assert 'percentage' in errors
        assert '<= 100' in errors['percentage'][0]

    def test_min_length_validation(self):
        """String below min_length should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='password', label='Password', min_length=8)
        ]
        params = {'password': '123'}

        errors = validate_parameters(params, args)
        assert 'password' in errors
        assert 'at least 8' in errors['password'][0]

    def test_max_length_validation(self):
        """String above max_length should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='code', label='Code', max_length=5)
        ]
        params = {'code': 'TOOLONG'}

        errors = validate_parameters(params, args)
        assert 'code' in errors
        assert 'at most 5' in errors['code'][0]

    def test_pattern_validation_invalid(self):
        """String not matching pattern should fail"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(
                key='email',
                label='Email',
                pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$'
            )
        ]
        params = {'email': 'not-an-email'}

        errors = validate_parameters(params, args)
        assert 'email' in errors
        assert 'format is invalid' in errors['email'][0]

    def test_pattern_validation_valid(self):
        """String matching pattern should pass"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(
                key='email',
                label='Email',
                pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$'
            )
        ]
        params = {'email': 'test@example.com'}

        errors = validate_parameters(params, args)
        assert errors == {}

    def test_multiple_errors(self):
        """Multiple fields with errors should all be reported"""
        from app.engine.validate_parameters import validate_parameters

        args = [
            MockActionArgument(key='name', label='Name', required=True),
            MockActionArgument(key='age', label='Age', type=MockArgumentType.NUMBER),
        ]
        params = {'age': 'invalid'}

        errors = validate_parameters(params, args)
        assert 'name' in errors
        assert 'age' in errors


class TestValidationError:
    """Tests for ValidationError exception"""

    def test_error_message_format(self):
        """Error message should include all field errors"""
        from app.engine.validate_parameters import ValidationError

        errors = {
            'email': ['Email is required'],
            'age': ['Age must be a number']
        }
        error = ValidationError(errors)

        assert 'email' in str(error)
        assert 'age' in str(error)
        assert 'Validation failed' in str(error)

    def test_errors_attribute(self):
        """ValidationError should store errors dict"""
        from app.engine.validate_parameters import ValidationError

        errors = {'field': ['error1', 'error2']}
        error = ValidationError(errors)

        assert error.errors == errors


class TestValidateAndRaise:
    """Tests for validate_and_raise()"""

    def test_raises_on_invalid(self):
        """Should raise ValidationError on invalid params"""
        from app.engine.validate_parameters import validate_and_raise, ValidationError

        args = [
            MockActionArgument(key='name', label='Name', required=True)
        ]
        params = {}

        with pytest.raises(ValidationError) as exc_info:
            validate_and_raise(params, args)

        assert 'name' in exc_info.value.errors

    def test_no_raise_on_valid(self):
        """Should not raise on valid params"""
        from app.engine.validate_parameters import validate_and_raise

        args = [
            MockActionArgument(key='name', label='Name', required=True)
        ]
        params = {'name': 'John'}

        # Should not raise
        validate_and_raise(params, args)
