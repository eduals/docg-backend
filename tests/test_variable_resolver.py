"""
Tests for VariableResolver
"""

import pytest
from app.flow_engine.variable_resolver import VariableResolver


class TestVariableResolver:
    """Test variable resolution"""

    def test_simple_trigger_variable(self):
        """Test resolving simple trigger variable"""
        resolver = VariableResolver(trigger_output={'name': 'John'})

        result = resolver.resolve('{{trigger.name}}')
        assert result == 'John'

    def test_nested_trigger_variable(self):
        """Test resolving nested trigger variable"""
        resolver = VariableResolver(trigger_output={
            'contact': {'email': 'john@example.com'}
        })

        result = resolver.resolve('{{trigger.contact.email}}')
        assert result == 'john@example.com'

    def test_array_access(self):
        """Test array access in variables"""
        resolver = VariableResolver(trigger_output={
            'items': [{'name': 'Item 1'}, {'name': 'Item 2'}]
        })

        result = resolver.resolve('{{trigger.items[0].name}}')
        assert result == 'Item 1'

    def test_step_output_variable(self):
        """Test resolving step output variable"""
        resolver = VariableResolver(
            trigger_output={},
            steps_output={'getContact': {'id': '123', 'name': 'Jane'}}
        )

        result = resolver.resolve('{{getContact.name}}')
        assert result == 'Jane'

    def test_preserve_type_int(self):
        """Test that integer types are preserved"""
        resolver = VariableResolver(trigger_output={'amount': 1000})

        result = resolver.resolve('{{trigger.amount}}')
        assert result == 1000
        assert isinstance(result, int)

    def test_string_interpolation(self):
        """Test string interpolation"""
        resolver = VariableResolver(trigger_output={'name': 'John', 'age': 30})

        result = resolver.resolve('Name: {{trigger.name}}, Age: {{trigger.age}}')
        assert result == 'Name: John, Age: 30'

    def test_dict_resolution(self):
        """Test resolving variables in dict"""
        resolver = VariableResolver(trigger_output={'email': 'test@example.com'})

        data = {
            'contact_email': '{{trigger.email}}',
            'subject': 'Hello {{trigger.email}}'
        }

        result = resolver.resolve(data)
        assert result['contact_email'] == 'test@example.com'
        assert result['subject'] == 'Hello test@example.com'

    def test_list_resolution(self):
        """Test resolving variables in list"""
        resolver = VariableResolver(trigger_output={'value': 'test'})

        data = ['{{trigger.value}}', 'static', '{{trigger.value}}']

        result = resolver.resolve(data)
        assert result == ['test', 'static', 'test']

    def test_validate_unresolved(self):
        """Test validation finds unresolved variables"""
        resolver = VariableResolver(trigger_output={'name': 'John'})

        unresolved = resolver.validate('{{trigger.missing_field}}')
        assert 'trigger.missing_field' in unresolved

    def test_validate_all_resolved(self):
        """Test validation passes when all variables resolve"""
        resolver = VariableResolver(trigger_output={'name': 'John'})

        unresolved = resolver.validate('{{trigger.name}}')
        assert len(unresolved) == 0

    def test_add_step_output(self):
        """Test adding step output"""
        resolver = VariableResolver(trigger_output={})

        resolver.add_step_output('step1', {'result': 'success'})

        result = resolver.resolve('{{step1.result}}')
        assert result == 'success'

    def test_get_available_variables(self):
        """Test getting available variable sources"""
        resolver = VariableResolver(
            trigger_output={},
            steps_output={'step1': {}, 'step2': {}}
        )

        available = resolver.get_available_variables()
        assert 'trigger' in available
        assert 'step1' in available
        assert 'step2' in available
