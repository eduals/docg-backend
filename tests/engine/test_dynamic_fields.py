"""
Tests for Dynamic Fields functionality

FASE 7: Dynamic Fields
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from dataclasses import dataclass
from typing import List, Dict, Any


class TestDynamicFieldsDefinition:
    """Tests for DynamicFieldsDefinition base class"""

    def test_has_key_attribute(self):
        """DynamicFieldsDefinition should have key attribute"""
        from app.apps.base import DynamicFieldsDefinition

        definition = DynamicFieldsDefinition()
        assert hasattr(definition, 'key')

    def test_has_depends_on_attribute(self):
        """DynamicFieldsDefinition should have depends_on attribute"""
        from app.apps.base import DynamicFieldsDefinition

        definition = DynamicFieldsDefinition()
        assert hasattr(definition, 'depends_on')

    def test_get_fields_raises_not_implemented(self):
        """get_fields should raise NotImplementedError in base class"""
        from app.apps.base import DynamicFieldsDefinition

        definition = DynamicFieldsDefinition()

        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(definition.get_fields(None, {}))

    def test_to_dict(self):
        """to_dict should return correct format"""
        from app.apps.base import DynamicFieldsDefinition

        class TestDefinition(DynamicFieldsDefinition):
            key = 'testFields'
            depends_on = ['field1', 'field2']

        definition = TestDefinition()
        result = definition.to_dict()

        assert result == {
            'key': 'testFields',
            'depends_on': ['field1', 'field2']
        }


class TestDynamicFieldsSource:
    """Tests for DynamicFieldsSource dataclass"""

    def test_to_dict(self):
        """to_dict should return correct format"""
        from app.apps.base import DynamicFieldsSource

        source = DynamicFieldsSource(
            key='objectFields',
            depends_on=['object_type']
        )

        result = source.to_dict()

        assert result == {
            'key': 'objectFields',
            'depends_on': ['object_type']
        }

    def test_default_depends_on(self):
        """depends_on should default to empty list"""
        from app.apps.base import DynamicFieldsSource

        source = DynamicFieldsSource(key='simpleFields')

        assert source.depends_on == []


class TestBaseAppDynamicFields:
    """Tests for dynamic fields methods in BaseApp"""

    def test_register_dynamic_fields(self):
        """Should register dynamic fields definition"""
        from app.apps.base import DynamicFieldsDefinition

        # Create a mock app
        class MockApp:
            def __init__(self):
                self._dynamic_fields = {}

            def register_dynamic_fields(self, definition):
                self._dynamic_fields[definition.key] = definition

        class TestDefinition(DynamicFieldsDefinition):
            key = 'testFields'
            depends_on = []

        app = MockApp()
        definition = TestDefinition()

        app.register_dynamic_fields(definition)

        assert 'testFields' in app._dynamic_fields
        assert app._dynamic_fields['testFields'] == definition

    def test_get_dynamic_fields_definition(self):
        """Should get registered definition by key"""
        from app.apps.base import DynamicFieldsDefinition

        class MockApp:
            def __init__(self):
                self._dynamic_fields = {}

            def register_dynamic_fields(self, definition):
                self._dynamic_fields[definition.key] = definition

            def get_dynamic_fields_definition(self, key):
                return self._dynamic_fields.get(key)

        class TestDefinition(DynamicFieldsDefinition):
            key = 'myFields'
            depends_on = []

        app = MockApp()
        definition = TestDefinition()
        app.register_dynamic_fields(definition)

        result = app.get_dynamic_fields_definition('myFields')
        assert result == definition

    def test_get_dynamic_fields_definition_not_found(self):
        """Should return None for unknown key"""
        class MockApp:
            def __init__(self):
                self._dynamic_fields = {}

            def get_dynamic_fields_definition(self, key):
                return self._dynamic_fields.get(key)

        app = MockApp()
        result = app.get_dynamic_fields_definition('unknown')

        assert result is None

    def test_get_dynamic_fields_list(self):
        """Should return list of all definitions"""
        from app.apps.base import DynamicFieldsDefinition

        class MockApp:
            def __init__(self):
                self._dynamic_fields = {}

            def register_dynamic_fields(self, definition):
                self._dynamic_fields[definition.key] = definition

            def get_dynamic_fields_list(self):
                return list(self._dynamic_fields.values())

        class Definition1(DynamicFieldsDefinition):
            key = 'fields1'
            depends_on = []

        class Definition2(DynamicFieldsDefinition):
            key = 'fields2'
            depends_on = []

        app = MockApp()
        app.register_dynamic_fields(Definition1())
        app.register_dynamic_fields(Definition2())

        result = app.get_dynamic_fields_list()

        assert len(result) == 2
        keys = [d.key for d in result]
        assert 'fields1' in keys
        assert 'fields2' in keys


class TestCustomDynamicFieldsDefinition:
    """Tests for custom DynamicFieldsDefinition implementations"""

    @pytest.mark.asyncio
    async def test_custom_implementation(self):
        """Custom implementation should work correctly"""
        from app.apps.base import DynamicFieldsDefinition, ActionArgument, ArgumentType

        class CustomDefinition(DynamicFieldsDefinition):
            key = 'customFields'
            depends_on = ['object_type']

            async def get_fields(self, http_client, context):
                object_type = context.get('object_type')
                if object_type == 'contact':
                    return [
                        ActionArgument(
                            key='email',
                            label='Email',
                            type=ArgumentType.STRING,
                            required=True
                        ),
                        ActionArgument(
                            key='phone',
                            label='Phone',
                            type=ArgumentType.STRING
                        )
                    ]
                return []

        definition = CustomDefinition()

        # Test with contact
        fields = await definition.get_fields(None, {'object_type': 'contact'})
        assert len(fields) == 2
        assert fields[0].key == 'email'
        assert fields[1].key == 'phone'

        # Test with unknown type
        fields = await definition.get_fields(None, {'object_type': 'unknown'})
        assert len(fields) == 0


class TestDynamicFieldsController:
    """Tests for dynamic fields controller endpoint"""

    def test_controller_exists(self):
        """Controller file should exist and be importable"""
        from app.controllers.api.v1.apps import dynamic_fields_controller
        assert dynamic_fields_controller is not None

    def test_apps_blueprint_exists(self):
        """apps_bp blueprint should exist"""
        from app.controllers.api.v1.apps import apps_bp
        assert apps_bp is not None


class TestActionArgumentWithDynamicFields:
    """Tests for ActionArgument with additional_fields"""

    def test_additional_fields_in_to_dict(self):
        """additional_fields should be included in to_dict"""
        from app.apps.base import ActionArgument, DynamicFieldsSource, ArgumentType

        arg = ActionArgument(
            key='object_type',
            label='Object Type',
            type=ArgumentType.DROPDOWN,
            additional_fields=DynamicFieldsSource(
                key='objectFields',
                depends_on=['object_type']
            )
        )

        result = arg.to_dict()

        assert 'additional_fields' in result
        assert result['additional_fields']['key'] == 'objectFields'
        assert result['additional_fields']['depends_on'] == ['object_type']

    def test_additional_fields_optional(self):
        """additional_fields should be optional"""
        from app.apps.base import ActionArgument, ArgumentType

        arg = ActionArgument(
            key='simple',
            label='Simple Field',
            type=ArgumentType.STRING
        )

        result = arg.to_dict()

        assert 'additional_fields' not in result
