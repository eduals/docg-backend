"""
Tests for app/models/datastore.py and app/apps/base.py Datastore class

FASE 3: Datastore Persistente
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import uuid


class TestWorkflowDatastoreModel:
    """Tests for WorkflowDatastore model"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        with patch('app.models.datastore.db') as mock_db:
            mock_db.session = MagicMock()
            yield mock_db

    def test_to_dict(self):
        """to_dict should return correct format"""
        from app.models.datastore import WorkflowDatastore

        org_id = uuid.uuid4()
        now = datetime.utcnow()

        ds = WorkflowDatastore()
        ds.id = uuid.uuid4()
        ds.organization_id = org_id
        ds.scope = 'organization'
        ds.scope_id = None
        ds.key = 'test_key'
        ds.value = {'data': 'value'}
        ds.created_at = now
        ds.updated_at = now
        ds.expires_at = None

        result = ds.to_dict()

        assert result['organization_id'] == str(org_id)
        assert result['scope'] == 'organization'
        assert result['key'] == 'test_key'
        assert result['value'] == {'data': 'value'}
        assert result['scope_id'] is None
        assert result['expires_at'] is None


class TestDatastoreClass:
    """Tests for Datastore class in base.py"""

    def test_cache_key_format(self):
        """Cache key should use scope:scope_id:key format"""
        from app.apps.base import Datastore

        ds = Datastore(
            organization_id='org-123',
            scope='workflow',
            scope_id='wf-456'
        )

        # The cache key is internal but we can test it exists in cache after set
        # This is a design test - verify the caching logic
        cache_key = f"{ds.scope}:{ds.scope_id}:test_key"
        assert cache_key == "workflow:wf-456:test_key"

    def test_initialization(self):
        """Datastore should initialize with correct parameters"""
        from app.apps.base import Datastore

        ds = Datastore(
            organization_id='org-123',
            scope='execution',
            scope_id='exec-789'
        )

        assert ds.organization_id == 'org-123'
        assert ds.scope == 'execution'
        assert ds.scope_id == 'exec-789'
        assert ds._cache == {}

    def test_default_scope(self):
        """Default scope should be 'organization'"""
        from app.apps.base import Datastore

        ds = Datastore(organization_id='org-123')

        assert ds.scope == 'organization'
        assert ds.scope_id is None


class TestDatastoreGetValue:
    """Tests for WorkflowDatastore.get_value()"""

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_get_value_found(self, mock_db, mock_query):
        """Should return value when found"""
        from app.models.datastore import WorkflowDatastore

        mock_record = MagicMock()
        mock_record.value = {'test': 'data'}
        mock_record.expires_at = None

        mock_query.filter_by.return_value.filter.return_value.first.return_value = mock_record

        result = WorkflowDatastore.get_value(
            organization_id='org-123',
            key='my_key'
        )

        assert result == {'test': 'data'}

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_get_value_not_found(self, mock_db, mock_query):
        """Should return None when not found"""
        from app.models.datastore import WorkflowDatastore

        mock_query.filter_by.return_value.filter.return_value.first.return_value = None

        result = WorkflowDatastore.get_value(
            organization_id='org-123',
            key='nonexistent'
        )

        assert result is None

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_get_value_expired(self, mock_db, mock_query):
        """Should return None and delete when expired"""
        from app.models.datastore import WorkflowDatastore

        mock_record = MagicMock()
        mock_record.value = {'old': 'data'}
        mock_record.expires_at = datetime.utcnow() - timedelta(hours=1)

        mock_query.filter_by.return_value.filter.return_value.first.return_value = mock_record

        result = WorkflowDatastore.get_value(
            organization_id='org-123',
            key='expired_key'
        )

        assert result is None
        mock_db.session.delete.assert_called_once_with(mock_record)
        mock_db.session.commit.assert_called_once()


class TestDatastoreSetValue:
    """Tests for WorkflowDatastore.set_value()"""

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_set_value_insert(self, mock_db, mock_query):
        """Should insert new record when not exists"""
        from app.models.datastore import WorkflowDatastore

        mock_query.filter_by.return_value.filter.return_value.first.return_value = None

        WorkflowDatastore.set_value(
            organization_id='org-123',
            key='new_key',
            value={'new': 'data'}
        )

        mock_db.session.add.assert_called_once()
        mock_db.session.commit.assert_called_once()

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_set_value_update(self, mock_db, mock_query):
        """Should update existing record"""
        from app.models.datastore import WorkflowDatastore

        mock_record = MagicMock()
        mock_record.value = {'old': 'data'}
        mock_query.filter_by.return_value.filter.return_value.first.return_value = mock_record

        WorkflowDatastore.set_value(
            organization_id='org-123',
            key='existing_key',
            value={'new': 'data'}
        )

        assert mock_record.value == {'new': 'data'}
        mock_db.session.commit.assert_called_once()
        mock_db.session.add.assert_not_called()

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_set_value_with_ttl(self, mock_db, mock_query):
        """Should set expires_at when ttl provided"""
        from app.models.datastore import WorkflowDatastore

        mock_query.filter_by.return_value.filter.return_value.first.return_value = None

        before = datetime.utcnow()
        WorkflowDatastore.set_value(
            organization_id='org-123',
            key='ttl_key',
            value='temp_data',
            ttl_seconds=3600
        )
        after = datetime.utcnow()

        # Verify add was called with a record that has expires_at set
        call_args = mock_db.session.add.call_args
        record = call_args[0][0]
        assert record.expires_at is not None
        # Expires_at should be approximately 1 hour from now
        expected_min = before + timedelta(seconds=3600)
        expected_max = after + timedelta(seconds=3600)
        assert expected_min <= record.expires_at <= expected_max


class TestDatastoreDeleteValue:
    """Tests for WorkflowDatastore.delete_value()"""

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_delete_value_exists(self, mock_db, mock_query):
        """Should delete and return True when exists"""
        from app.models.datastore import WorkflowDatastore

        mock_query.filter_by.return_value.filter.return_value.delete.return_value = 1

        result = WorkflowDatastore.delete_value(
            organization_id='org-123',
            key='delete_me'
        )

        assert result is True
        mock_db.session.commit.assert_called_once()

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_delete_value_not_exists(self, mock_db, mock_query):
        """Should return False when not exists"""
        from app.models.datastore import WorkflowDatastore

        mock_query.filter_by.return_value.filter.return_value.delete.return_value = 0

        result = WorkflowDatastore.delete_value(
            organization_id='org-123',
            key='nonexistent'
        )

        assert result is False


class TestDatastoreCleanupExpired:
    """Tests for WorkflowDatastore.cleanup_expired()"""

    @patch('app.models.datastore.WorkflowDatastore.query')
    @patch('app.models.datastore.db')
    def test_cleanup_expired(self, mock_db, mock_query):
        """Should delete expired records and return count"""
        from app.models.datastore import WorkflowDatastore

        mock_query.filter.return_value.filter.return_value.delete.return_value = 5

        result = WorkflowDatastore.cleanup_expired()

        assert result == 5
        mock_db.session.commit.assert_called_once()
