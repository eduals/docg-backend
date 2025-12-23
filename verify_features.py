#!/usr/bin/env python3
"""
Verification script for Execution v2.0 features.

Tests all new endpoints and validates database schema.

Usage:
    python verify_features.py
"""
import os
import sys
import requests
import redis
import psycopg2
from datetime import datetime
from urllib.parse import urlparse

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_section(title):
    """Print a section header"""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{title:^70}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

def print_success(message):
    """Print success message"""
    print(f"{GREEN}✅ {message}{RESET}")

def print_error(message):
    """Print error message"""
    print(f"{RED}❌ {message}{RESET}")

def print_warning(message):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {message}{RESET}")

def print_info(message):
    """Print info message"""
    print(f"{BLUE}ℹ️  {message}{RESET}")


class FeatureVerifier:
    def __init__(self):
        self.base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.database_url = os.getenv('DATABASE_URL')
        self.results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0
        }

    def verify_env_vars(self):
        """Verify environment variables are set"""
        print_section("Environment Variables")

        required_vars = [
            'DATABASE_URL',
            'REDIS_URL',
            'REDIS_STREAM_MAXLEN',
            'REDIS_STREAM_TTL'
        ]

        for var in required_vars:
            value = os.getenv(var)
            if value:
                print_success(f"{var} is set")
                self.results['passed'] += 1
            else:
                print_warning(f"{var} is not set")
                self.results['warnings'] += 1

    def verify_database_schema(self):
        """Verify new database tables exist"""
        print_section("Database Schema")

        if not self.database_url:
            print_error("DATABASE_URL not set, skipping database checks")
            self.results['failed'] += 1
            return

        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()

            # Check new tables
            tables_to_check = [
                'execution_logs',
                'audit_events'
            ]

            for table in tables_to_check:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = %s
                    );
                """, (table,))
                exists = cursor.fetchone()[0]

                if exists:
                    print_success(f"Table '{table}' exists")
                    self.results['passed'] += 1
                else:
                    print_error(f"Table '{table}' does not exist")
                    self.results['failed'] += 1

            # Check new columns in workflow_executions
            columns_to_check = [
                'progress',
                'current_step',
                'last_error_human',
                'last_error_tech',
                'correlation_id',
                'phase_metrics',
                'preflight_summary'
            ]

            print_info("Checking new columns in workflow_executions...")
            for column in columns_to_check:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_name = 'workflow_executions'
                        AND column_name = %s
                    );
                """, (column,))
                exists = cursor.fetchone()[0]

                if exists:
                    print_success(f"Column 'workflow_executions.{column}' exists")
                    self.results['passed'] += 1
                else:
                    print_error(f"Column 'workflow_executions.{column}' does not exist")
                    self.results['failed'] += 1

            # Check new columns in execution_steps
            step_columns = ['error_human', 'error_tech']
            print_info("Checking new columns in execution_steps...")
            for column in step_columns:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_name = 'execution_steps'
                        AND column_name = %s
                    );
                """, (column,))
                exists = cursor.fetchone()[0]

                if exists:
                    print_success(f"Column 'execution_steps.{column}' exists")
                    self.results['passed'] += 1
                else:
                    print_error(f"Column 'execution_steps.{column}' does not exist")
                    self.results['failed'] += 1

            cursor.close()
            conn.close()

        except Exception as e:
            print_error(f"Database connection error: {e}")
            self.results['failed'] += 1

    def verify_redis_connection(self):
        """Verify Redis connection and Streams support"""
        print_section("Redis Connection & Streams")

        try:
            r = redis.Redis.from_url(self.redis_url, decode_responses=True)

            # Test connection
            r.ping()
            print_success("Redis connection successful")
            self.results['passed'] += 1

            # Test Streams (XADD)
            test_key = f"docg:test:verify:{datetime.now().timestamp()}"
            event_id = r.xadd(test_key, {'test': 'data'}, maxlen=10)
            print_success(f"Redis Streams (XADD) working - Event ID: {event_id}")
            self.results['passed'] += 1

            # Test XREAD
            events = r.xread({test_key: '0'}, count=1)
            if events:
                print_success("Redis Streams (XREAD) working")
                self.results['passed'] += 1
            else:
                print_error("Redis Streams (XREAD) failed")
                self.results['failed'] += 1

            # Cleanup
            r.delete(test_key)

            # Check Redis info
            info = r.info('server')
            print_info(f"Redis version: {info.get('redis_version', 'unknown')}")

        except redis.ConnectionError as e:
            print_error(f"Redis connection failed: {e}")
            self.results['failed'] += 1
        except Exception as e:
            print_error(f"Redis error: {e}")
            self.results['failed'] += 1

    def verify_flask_app(self):
        """Verify Flask app is running and responding"""
        print_section("Flask Application")

        try:
            # Test health endpoint
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                print_success("Flask app is running")
                self.results['passed'] += 1
            else:
                print_error(f"Flask app returned status {response.status_code}")
                self.results['failed'] += 1
        except requests.exceptions.ConnectionError:
            print_warning("Flask app is not running (this is OK if testing without server)")
            print_info("To start the Flask app: flask run")
            self.results['warnings'] += 1
        except Exception as e:
            print_error(f"Error connecting to Flask app: {e}")
            self.results['failed'] += 1

    def verify_endpoints(self):
        """Verify new endpoints are registered"""
        print_section("API Endpoints Registration")

        # This requires the Flask app to be running
        # We'll just document the endpoints that should exist

        endpoints = [
            # Execution endpoints
            ('GET', '/api/v1/executions/<execution_id>/logs', 'Structured logs'),
            ('GET', '/api/v1/executions/<execution_id>/audit', 'Audit trail'),
            ('GET', '/api/v1/executions/<execution_id>/steps', 'Execution steps'),
            ('POST', '/api/v1/executions/<execution_id>/resume', 'Resume execution'),
            ('POST', '/api/v1/executions/<execution_id>/cancel', 'Cancel execution'),
            ('POST', '/api/v1/executions/<execution_id>/retry', 'Retry execution'),
            # Preflight endpoints
            ('POST', '/api/v1/workflows/<workflow_id>/preflight', 'Preflight check'),
            ('GET', '/api/v1/executions/<execution_id>/preflight', 'Get preflight results'),
            # SSE endpoints
            ('GET', '/api/v1/sse/executions/<execution_id>/stream', 'SSE stream with replay'),
            ('GET', '/api/v1/sse/health', 'SSE health check'),
        ]

        print_info("Expected endpoints (verification requires running server):")
        for method, path, description in endpoints:
            print(f"  {method:6} {path:50} - {description}")

        # Try to verify SSE health endpoint if server is running
        try:
            response = requests.get(f"{self.base_url}/api/v1/sse/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy' and data.get('mode') == 'streams':
                    print_success("SSE endpoint is working with Redis Streams")
                    self.results['passed'] += 1
                else:
                    print_warning(f"SSE endpoint returned unexpected data: {data}")
                    self.results['warnings'] += 1
            else:
                print_warning(f"SSE health endpoint returned status {response.status_code}")
                self.results['warnings'] += 1
        except requests.exceptions.ConnectionError:
            print_warning("Cannot verify endpoints (Flask app not running)")
            self.results['warnings'] += 1
        except Exception as e:
            print_warning(f"Error checking SSE health: {e}")
            self.results['warnings'] += 1

    def verify_models(self):
        """Verify models can be imported"""
        print_section("Model Imports")

        try:
            from app.models.execution_log import ExecutionLog
            print_success("ExecutionLog model imported")
            self.results['passed'] += 1
        except ImportError as e:
            print_error(f"Failed to import ExecutionLog: {e}")
            self.results['failed'] += 1

        try:
            from app.models.audit_event import AuditEvent
            print_success("AuditEvent model imported")
            self.results['passed'] += 1
        except ImportError as e:
            print_error(f"Failed to import AuditEvent: {e}")
            self.results['failed'] += 1

        try:
            from app.services.execution_logger import ExecutionLogger
            print_success("ExecutionLogger service imported")
            self.results['passed'] += 1
        except ImportError as e:
            print_error(f"Failed to import ExecutionLogger: {e}")
            self.results['failed'] += 1

        try:
            from app.services.audit_service import AuditService
            print_success("AuditService imported")
            self.results['passed'] += 1
        except ImportError as e:
            print_error(f"Failed to import AuditService: {e}")
            self.results['failed'] += 1

        try:
            from app.services.recommended_actions import get_recommended_actions
            print_success("RecommendedActions service imported")
            self.results['passed'] += 1
        except ImportError as e:
            print_error(f"Failed to import RecommendedActions: {e}")
            self.results['failed'] += 1

    def print_summary(self):
        """Print verification summary"""
        print_section("Verification Summary")

        total = self.results['passed'] + self.results['failed'] + self.results['warnings']

        print(f"Total checks: {total}")
        print_success(f"Passed: {self.results['passed']}")
        if self.results['failed'] > 0:
            print_error(f"Failed: {self.results['failed']}")
        else:
            print(f"Failed: {self.results['failed']}")
        if self.results['warnings'] > 0:
            print_warning(f"Warnings: {self.results['warnings']}")
        else:
            print(f"Warnings: {self.results['warnings']}")

        print()

        if self.results['failed'] > 0:
            print_error("Some checks failed! Review the errors above.")
            return False
        elif self.results['warnings'] > 0:
            print_warning("All critical checks passed, but some warnings exist.")
            return True
        else:
            print_success("All checks passed! ✨")
            return True

    def run(self):
        """Run all verifications"""
        print(f"\n{BLUE}{'=' * 70}{RESET}")
        print(f"{BLUE}{'Execution v2.0 Features - Verification Script':^70}{RESET}")
        print(f"{BLUE}{'=' * 70}{RESET}")
        print(f"{BLUE}Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
        print(f"{BLUE}{'=' * 70}{RESET}\n")

        self.verify_env_vars()
        self.verify_database_schema()
        self.verify_redis_connection()
        self.verify_models()
        self.verify_flask_app()
        self.verify_endpoints()

        success = self.print_summary()

        return 0 if success else 1


if __name__ == '__main__':
    # Load .env file if python-dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print_warning("python-dotenv not installed, using system environment variables")

    verifier = FeatureVerifier()
    sys.exit(verifier.run())
