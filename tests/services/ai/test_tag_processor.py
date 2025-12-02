"""
Testes para funcionalidades de IA no TagProcessor
"""

import pytest
from app.services.document_generation.tag_processor import TagProcessor


class TestExtractAITags:
    """Testes para extract_ai_tags()"""
    
    def test_extract_single_ai_tag(self):
        text = "Hello {{ai:intro}} world"
        result = TagProcessor.extract_ai_tags(text)
        assert result == ['intro']
    
    def test_extract_multiple_ai_tags(self):
        text = "Start {{ai:intro}} middle {{ai:body}} end {{ai:conclusion}}"
        result = TagProcessor.extract_ai_tags(text)
        assert set(result) == {'intro', 'body', 'conclusion'}
    
    def test_no_ai_tags(self):
        text = "Hello {{name}} world {{date}}"
        result = TagProcessor.extract_ai_tags(text)
        assert result == []
    
    def test_duplicate_ai_tags(self):
        text = "Start {{ai:intro}} middle {{ai:intro}} end"
        result = TagProcessor.extract_ai_tags(text)
        assert result == ['intro']
    
    def test_mixed_tags(self):
        text = "Hello {{name}}, {{ai:greeting}}, bye {{farewell}}"
        result = TagProcessor.extract_ai_tags(text)
        assert result == ['greeting']
    
    def test_ai_tag_with_underscore(self):
        text = "Text {{ai:paragraph_one}} more text"
        result = TagProcessor.extract_ai_tags(text)
        assert result == ['paragraph_one']


class TestExtractTagsExcludesAI:
    """Testes para verificar que extract_tags exclui tags AI"""
    
    def test_excludes_ai_tags(self):
        text = "Hello {{name}}, {{ai:greeting}}, date: {{date}}"
        result = TagProcessor.extract_tags(text)
        assert 'name' in result
        assert 'date' in result
        assert 'ai:greeting' not in result
        assert 'greeting' not in result


class TestReplaceAITag:
    """Testes para replace_ai_tag()"""
    
    def test_replace_single_tag(self):
        text = "Hello {{ai:intro}} world"
        result = TagProcessor.replace_ai_tag(text, 'intro', 'REPLACED')
        assert result == "Hello REPLACED world"
    
    def test_replace_multiple_occurrences(self):
        text = "Start {{ai:tag}} middle {{ai:tag}} end"
        result = TagProcessor.replace_ai_tag(text, 'tag', 'X')
        assert result == "Start X middle X end"
    
    def test_replace_only_matching_tag(self):
        text = "A {{ai:one}} B {{ai:two}} C"
        result = TagProcessor.replace_ai_tag(text, 'one', 'FIRST')
        assert result == "A FIRST B {{ai:two}} C"
    
    def test_replace_with_special_characters(self):
        text = "Test {{ai:intro}}"
        result = TagProcessor.replace_ai_tag(text, 'intro', 'Text with $pecial ch@rs!')
        assert result == "Text with $pecial ch@rs!"


class TestBuildAIPrompt:
    """Testes para build_ai_prompt()"""
    
    def test_build_with_template(self):
        template = "Describe the deal {{dealname}} worth {{amount}}"
        data = {'dealname': 'Project X', 'amount': '50000'}
        
        result = TagProcessor.build_ai_prompt(template, data)
        
        assert result == "Describe the deal Project X worth 50000"
    
    def test_build_with_nested_data(self):
        template = "Company: {{company.name}}, Contact: {{contact.email}}"
        data = {
            'company': {'name': 'Acme Inc'},
            'contact': {'email': 'john@acme.com'}
        }
        
        result = TagProcessor.build_ai_prompt(template, data)
        
        assert 'Acme Inc' in result
        assert 'john@acme.com' in result
    
    def test_build_without_template_uses_source_fields(self):
        data = {'name': 'Test', 'value': '100'}
        source_fields = ['name', 'value']
        
        result = TagProcessor.build_ai_prompt(None, data, source_fields)
        
        assert 'name' in result
        assert 'value' in result
    
    def test_build_without_template_and_fields(self):
        result = TagProcessor.build_ai_prompt(None, {})
        
        assert 'texto' in result.lower() or 'text' in result.lower()
    
    def test_missing_data_replaced_with_empty(self):
        template = "Name: {{name}}, Missing: {{missing}}"
        data = {'name': 'Test'}
        
        result = TagProcessor.build_ai_prompt(template, data)
        
        assert 'Test' in result
        assert '{{missing}}' not in result  # Deve ter sido substituído por vazio


class TestFormatSourceData:
    """Testes para _format_source_data()"""
    
    def test_format_all_data(self):
        data = {'name': 'John', 'age': 30}
        result = TagProcessor._format_source_data(data)
        
        assert 'name: John' in result
        assert 'age: 30' in result
    
    def test_format_filtered_fields(self):
        data = {'name': 'John', 'age': 30, 'city': 'NYC'}
        result = TagProcessor._format_source_data(data, ['name', 'city'])
        
        assert 'name: John' in result
        assert 'city: NYC' in result
        assert 'age' not in result
    
    def test_format_excludes_none(self):
        data = {'name': 'John', 'empty': None}
        result = TagProcessor._format_source_data(data)
        
        assert 'name: John' in result
        assert 'empty' not in result
    
    def test_format_empty_data(self):
        result = TagProcessor._format_source_data({})
        
        assert 'Nenhum dado' in result or 'disponível' in result

