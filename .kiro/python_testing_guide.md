# 🐍 Guía de Testing con Python (pytest)

## 📋 Configuración de Testing

### Estructura de Tests
```
apps/backend/
├── tests/
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_ballot_encryption.py
│   │   ├── test_election_validation.py
│   │   └── test_member_eligibility.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_auth_api.py
│   │   ├── test_election_api.py
│   │   └── test_voting_api.py
│   ├── fixtures/
│   │   ├── __init__.py
│   │   ├── ballot_fixtures.py
│   │   ├── election_fixtures.py
│   │   └── member_fixtures.py
│   └── conftest.py          # Configuración global de pytest
```

### pytest Configuration (conftest.py)
```python
# apps/backend/tests/conftest.py
import pytest
import asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.main import app
from app.db.session import get_db

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_password@localhost:5432/evoting_test"

# Create test engine
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestAsyncSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def client(db_session: AsyncSession):
    """Create a test client with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def test_election(db_session: AsyncSession):
    """Fixture for creating a test election."""
    from app.models.election import Election
    from app.schemas.election import ElectionCreate
    
    election_data = ElectionCreate(
        title="Test Election 2026",
        voting_type="SLATE_PLURALITY",
        start_time="2026-09-01T08:00:00Z",
        end_time="2026-09-07T20:00:00Z",
        quorum_threshold_pct=30.0
    )
    
    election = Election(**election_data.dict())
    db_session.add(election)
    await db_session.commit()
    await db_session.refresh(election)
    
    return election
```

## 🧪 Ejemplos de Tests

### Unit Tests
```python
# tests/unit/test_ballot_encryption.py
import pytest
from app.services.ballot import encrypt_ballot, verify_ballot_proof
from app.exceptions import EncryptionError, ValidationError
from app.schemas.ballot import BallotCreate

class TestBallotEncryption:
    def test_encrypt_ballot_success(self):
        """Test successful ballot encryption."""
        ballot_data = BallotCreate(
            election_id="election_123",
            slate_id="slate_456",
            positions=["PRESIDENT", "SECRETARY"]
        )
        
        result = encrypt_ballot(ballot_data)
        
        assert "encrypted_payload" in result
        assert "receipt_hash" in result
        assert len(result["receipt_hash"]) == 64  # SHA-256 length
        assert "zkp_proof" in result
        
    def test_encrypt_ballot_invalid_data(self):
        """Test encryption fails with invalid data."""
        with pytest.raises(ValidationError, match="Invalid ballot data"):
            encrypt_ballot(None)
            
    def test_encrypt_ballot_missing_required_fields(self):
        """Test encryption fails with missing required fields."""
        incomplete_data = {"election_id": "election_123"}
        
        with pytest.raises(ValidationError, match="Missing required field"):
            encrypt_ballot(incomplete_data)
    
    @pytest.mark.parametrize("slate_id", [None, "", " "])
    def test_encrypt_ballot_invalid_slate_id(self, slate_id):
        """Test encryption fails with invalid slate IDs."""
        ballot_data = BallotCreate(
            election_id="election_123",
            slate_id=slate_id,
            positions=["PRESIDENT"]
        )
        
        with pytest.raises(ValidationError, match="Invalid slate ID"):
            encrypt_ballot(ballot_data)
```

### Integration Tests (API)
```python
# tests/integration/test_voting_api.py
import pytest
from httpx import AsyncClient

class TestVotingAPI:
    @pytest.mark.asyncio
    async def test_vote_eligibility_check(self, client: AsyncClient, auth_token: str):
        """Test voter eligibility check."""
        response = await client.post(
            "/api/v1/ballots/eligibility",
            json={"election_id": "election_123"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "eligible" in data
        assert "reason" in data
        assert "election" in data
        assert "slates" in data
        
    @pytest.mark.asyncio
    async def test_submit_encrypted_ballot(self, client: AsyncClient, auth_token: str):
        """Test submitting an encrypted ballot."""
        ballot_data = {
            "election_id": "election_123",
            "encrypted_payload": "base64_encrypted_data_here",
            "zkp_proof": "base64_zkp_proof_here",
            "client_public_key": "base64_public_key_here"
        }
        
        response = await client.post(
            "/api/v1/ballots/vote",
            json=ballot_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "receipt_hash" in data
        assert len(data["receipt_hash"]) == 64
        assert "timestamp" in data
        assert "ballot_id" in data
        
    @pytest.mark.asyncio
    async def test_vote_twice_prevention(self, client: AsyncClient, auth_token: str):
        """Test that users cannot vote twice."""
        # First vote
        ballot_data = {...}
        response1 = await client.post(
            "/api/v1/ballots/vote",
            json=ballot_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response1.status_code == 200
        
        # Second vote attempt
        response2 = await client.post(
            "/api/v1/ballots/vote",
            json=ballot_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response2.status_code == 409  # Conflict
        assert response2.json()["detail"] == "User has already voted"
```

### Async Tests
```python
# tests/integration/test_async_operations.py
import pytest
import asyncio
from app.services.tally import tally_election_results

class TestAsyncOperations:
    @pytest.mark.asyncio
    async def test_async_tally_processing(self, db_session):
        """Test async tally processing."""
        election_id = "election_123"
        
        # Start tally process
        tally_task = asyncio.create_task(
            tally_election_results(election_id, db_session)
        )
        
        # Wait for completion
        results = await tally_task
        
        assert results["status"] == "completed"
        assert "total_votes" in results
        assert "results_by_slate" in results
        assert "validation_hash" in results
        
    @pytest.mark.asyncio
    async def test_concurrent_vote_processing(self, client: AsyncClient):
        """Test handling concurrent vote submissions."""
        auth_tokens = ["token1", "token2", "token3"]
        ballot_data = {...}
        
        # Create concurrent vote tasks
        tasks = []
        for token in auth_tokens:
            task = client.post(
                "/api/v1/ballots/vote",
                json=ballot_data,
                headers={"Authorization": f"Bearer {token}"}
            )
            tasks.append(task)
        
        # Execute concurrently
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all succeeded
        success_count = 0
        for response in responses:
            if not isinstance(response, Exception) and response.status_code == 200:
                success_count += 1
                
        assert success_count == len(auth_tokens)
```

## 🔧 Configuración Avanzada

### pytest.ini
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --tb=short
    --color=yes
    -v
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    e2e: marks tests as end-to-end tests
    asyncio: marks tests that use asyncio
```

### pyproject.toml (Testing Section)
```toml
# pyproject.toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "--strict-markers",
    "--strict-config",
    "--tb=short",
    "-v",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html:coverage_html",
    "--cov-report=xml:coverage.xml",
    "--cov-fail-under=90"
]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

[tool.coverage.run]
source = ["app"]
omit = [
    "app/migrations/*",
    "app/tests/*",
    "app/__pycache__/*"
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod"
]
```

## 📊 Cobertura de Código

### Comandos de Cobertura
```bash
# Cobertura básica
pytest --cov=app

# Cobertura con reporte HTML
pytest --cov=app --cov-report=html

# Cobertura mínima requerida (90%)
pytest --cov=app --cov-fail-under=90

# Cobertura por módulo
pytest --cov=app.services --cov-report=term-missing

# Cobertura con exclusión de archivos
pytest --cov=app --cov-omit="*/migrations/*,*/tests/*"
```

### GitHub Actions para Testing
```yaml
# .github/workflows/test.yml
name: Python Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: evoting_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
        
    - name: Run tests with coverage
      run: |
        pytest --cov=app --cov-fail-under=90 --cov-report=xml
        
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
```

## 🚀 Best Practices

### 1. Fixtures Reutilizables
```python
# tests/fixtures/member_fixtures.py
import pytest
from app.models.member import Member
from app.schemas.member import MemberCreate

@pytest.fixture
def active_member_data():
    """Fixture for active member data."""
    return MemberCreate(
        email="active.member@example.com",
        full_name="Active Member",
        dni="12345678A",
        status="ACTIVE",
        membership_months=24
    )

@pytest.fixture
async def active_member(db_session, active_member_data):
    """Fixture for creating an active member in database."""
    member = Member(**active_member_data.dict())
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    return member
```

### 2. Parametrización de Tests
```python
@pytest.mark.parametrize("status,expected_count", [
    ("ACTIVE", 5),
    ("INACTIVE", 2),
    ("SANCTIONED", 1),
    (None, 8),  # All members
])
def test_get_members_by_status(status, expected_count, db_session, member_fixtures):
    """Test filtering members by status."""
    members = get_members_by_status(db_session, status)
    assert len(members) == expected_count
```

### 3. Mocking de Servicios Externos
```python
from unittest.mock import Mock, patch
import pytest

def test_encryption_service_with_mock():
    """Test using mocked encryption service."""
    mock_crypto = Mock()
    mock_crypto.encrypt.return_value = "mock_encrypted_data"
    
    with patch("app.services.ballot.crypto_service", mock_crypto):
        result = encrypt_ballot(test_data)
        
        mock_crypto.encrypt.assert_called_once_with(test_data)
        assert result == {"encrypted": "mock_encrypted_data"}
```

### 4. Testing de Errores
```python
def test_invalid_election_transition():
    """Test invalid election state transition."""
    election = Election(status="CLOSED")
    
    with pytest.raises(StateTransitionError) as exc_info:
        election.activate()
        
    assert "Cannot activate a closed election" in str(exc_info.value)
    assert exc_info.value.current_state == "CLOSED"
    assert exc_info.value.target_state == "ACTIVE"
```

## 🎯 Checklist de Testing

### Para Cada PR:
- [ ] Tests unitarios para nueva funcionalidad
- [ ] Tests de integración para APIs afectadas
- [ ] Cobertura de código mantenida (≥90%)
- [ ] Tests async funcionan correctamente
- [ ] Fixtures apropiadamente configuradas
- [ ] Mocking de servicios externos
- [ ] Tests de errores y casos límite
- [ ] Performance testing para operaciones críticas

### Para Cada Feature:
- [ ] Tests E2E para flujos de usuario
- [ ] Tests de seguridad y permisos
- [ ] Tests de concurrencia
- [ ] Tests de datos geoespaciales (si aplica)
- [ ] Tests de cifrado/descifrado
- [ ] Tests de auditoría y logging

---

**Responsable:** Nico (Test Automation Engineer)  
**Última actualización:** 2026-07-21  
**Herramientas:** pytest, pytest-cov, pytest-asyncio, httpx, factory-boy, freezegun
