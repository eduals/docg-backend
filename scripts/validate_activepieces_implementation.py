#!/usr/bin/env python3
"""
Validation Script - Activepieces Implementation
Run this to validate that FASE 0 and FASE 1 were implemented correctly

Usage:
    python scripts/validate_activepieces_implementation.py
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all models can be imported"""
    print("🧪 Testing imports...")

    try:
        from app.models import (
            Platform, Project, Folder,
            ProjectRole, ProjectMember, UserInvitation,
            Flow, FlowVersion, FlowRun, FlowRunLog, TriggerEvent,
            AppConnection, ConnectionKey,
            PlatformRole, DefaultProjectRole, Permission, ROLE_PERMISSIONS
        )
        print("  ✅ All models import successfully")
        return True
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False


def test_pieces():
    """Test that pieces system works"""
    print("\n🧪 Testing pieces system...")

    try:
        from app.pieces.base import (
            Piece, Action, Property, ExecutionContext,
            ActionResult, PieceRegistry, registry
        )
        print("  ✅ Base pieces classes imported")

        # Test webhook piece
        from app.pieces.webhook import webhook_piece
        assert webhook_piece.name == "webhook"
        assert len(webhook_piece.triggers) == 1
        assert len(webhook_piece.actions) == 1
        print(f"  ✅ Webhook piece loaded: {len(webhook_piece.actions)} actions, {len(webhook_piece.triggers)} triggers")

        # Test hubspot piece
        from app.pieces.hubspot import hubspot_piece
        assert hubspot_piece.name == "hubspot"
        assert len(hubspot_piece.actions) == 3
        assert hubspot_piece.auth is not None
        assert hubspot_piece.auth.type.value == "OAUTH2"
        print(f"  ✅ HubSpot piece loaded: {len(hubspot_piece.actions)} actions")

        # Test registry
        all_pieces = registry.get_all()
        assert "webhook" in all_pieces
        assert "hubspot" in all_pieces
        print(f"  ✅ Registry has {len(all_pieces)} pieces registered")

        return True
    except Exception as e:
        print(f"  ❌ Pieces error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_encryption():
    """Test encryption system"""
    print("\n🧪 Testing encryption...")

    try:
        from app.utils.credentials_encryption import encrypt_credentials, decrypt_credentials

        # Test data
        test_data = {
            'access_token': 'test_token_123',
            'refresh_token': 'refresh_xyz',
            'expires_at': 1234567890
        }

        # Encrypt
        encrypted = encrypt_credentials(test_data)
        assert '_encrypted' in encrypted
        print("  ✅ Encryption works")

        # Decrypt
        decrypted = decrypt_credentials(encrypted)
        assert decrypted == test_data
        print("  ✅ Decryption works")

        return True
    except Exception as e:
        print(f"  ❌ Encryption error: {e}")
        if "INTEGRATION_ENCRYPTION_KEY" in str(e):
            print("  ⚠️  INTEGRATION_ENCRYPTION_KEY not set in .env")
            print("     Run: python app/utils/credentials_encryption.py generate-key")
        return False


def test_permissions():
    """Test permissions mapping"""
    print("\n🧪 Testing permissions...")

    try:
        from app.models.permissions import (
            DefaultProjectRole, Permission, ROLE_PERMISSIONS
        )

        # Check all roles have permissions
        assert DefaultProjectRole.ADMIN in ROLE_PERMISSIONS
        assert DefaultProjectRole.EDITOR in ROLE_PERMISSIONS
        assert DefaultProjectRole.OPERATOR in ROLE_PERMISSIONS
        assert DefaultProjectRole.VIEWER in ROLE_PERMISSIONS

        # Check Admin has all permissions
        admin_perms = ROLE_PERMISSIONS[DefaultProjectRole.ADMIN]
        assert len(admin_perms) == 28
        print(f"  ✅ Admin role has {len(admin_perms)} permissions")

        # Check Viewer has only READ permissions
        viewer_perms = ROLE_PERMISSIONS[DefaultProjectRole.VIEWER]
        assert all('READ' in p.value for p in viewer_perms)
        print(f"  ✅ Viewer role has {len(viewer_perms)} READ-only permissions")

        return True
    except Exception as e:
        print(f"  ❌ Permissions error: {e}")
        return False


def test_database():
    """Test database connection and tables"""
    print("\n🧪 Testing database...")

    try:
        from app.database import db
        from app import create_app

        # Create app context
        app = create_app()
        with app.app_context():
            # Test connection
            result = db.session.execute(db.text("SELECT 1")).scalar()
            assert result == 1
            print("  ✅ Database connection works")

            # Check if migration was applied
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            required_tables = [
                'platform', 'project', 'folder',
                'project_role', 'project_member', 'user_invitation',
                'flow', 'flow_version', 'flow_run', 'flow_run_log',
                'trigger_event', 'app_connection', 'connection_key'
            ]

            missing_tables = [t for t in required_tables if t not in tables]

            if missing_tables:
                print(f"  ⚠️  Missing tables: {missing_tables}")
                print("     Run: flask db upgrade")
                return False
            else:
                print(f"  ✅ All {len(required_tables)} tables exist")

            return True
    except Exception as e:
        print(f"  ⚠️  Database error: {e}")
        print("     This is OK if database is not set up yet")
        print("     Run: flask db upgrade")
        return False


def check_env_vars():
    """Check required environment variables"""
    print("\n🧪 Checking environment variables...")

    required_vars = {
        'DATABASE_URL': 'Database connection string',
        'INTEGRATION_ENCRYPTION_KEY': 'Encryption key for credentials'
    }

    all_ok = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var} is set")
        else:
            print(f"  ⚠️  {var} is NOT set ({description})")
            all_ok = False

    return all_ok


def test_model_relationships():
    """Test model relationships"""
    print("\n🧪 Testing model relationships...")

    try:
        from app.models import Platform, Project, Flow, User

        # Check relationships exist
        assert hasattr(Platform, 'projects')
        assert hasattr(Platform, 'users')
        assert hasattr(Project, 'flows')
        assert hasattr(Flow, 'versions')
        assert hasattr(Flow, 'runs')
        assert hasattr(User, 'platform')
        assert hasattr(User, 'project_memberships')

        print("  ✅ All model relationships defined")
        return True
    except Exception as e:
        print(f"  ❌ Relationships error: {e}")
        return False


def main():
    """Run all validations"""
    print("=" * 60)
    print("🚀 Validating Activepieces Implementation")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Pieces System", test_pieces()))
    results.append(("Encryption", test_encryption()))
    results.append(("Permissions", test_permissions()))
    results.append(("Model Relationships", test_model_relationships()))
    results.append(("Environment Variables", check_env_vars()))
    results.append(("Database", test_database()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} | {test_name}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 All validations passed!")
        print("✅ FASE 0 and FASE 1 implementation is correct!")
        print("\n📝 Next steps:")
        print("   1. Apply migration: flask db upgrade")
        print("   2. Seed default roles: python scripts/seed_default_roles.py")
        print("   3. Start implementing FASE 2 (Flow Engine)")
        print("\n📖 See RESUMO_IMPLEMENTACAO_ACTIVEPIECES.md for details")
        return 0
    else:
        print("\n⚠️  Some validations failed")
        print("📖 Check errors above and fix before continuing")
        return 1


if __name__ == '__main__':
    sys.exit(main())
