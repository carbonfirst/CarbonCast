# Contributing to RDA Automation System

Thank you for your interest in contributing to the RDA Automation System! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

We welcome contributions of all kinds:

- **🐛 Bug Reports**: Help us identify and fix issues
- **✨ Feature Requests**: Suggest new functionality
- **📝 Documentation**: Improve or add documentation
- **🔧 Code Contributions**: Fix bugs or add features
- **🧪 Testing**: Add tests or improve test coverage
- **💡 Ideas**: Share ideas for improvements

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/your-username/rda-apps-clients.git
cd rda-apps-clients

# Add upstream remote
git remote add upstream https://github.com/original-repo/rda-apps-clients.git
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv dev_env
source dev_env/bin/activate  # On Windows: dev_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install black flake8 pytest mypy isort pre-commit

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

### 3. Verify Setup

```bash
# Run tests to ensure everything works
python -m pytest test/ -v

# Test the system
cd src/python
python simple_automation.py --mode test
```

## 🔧 Development Workflow

### Branch Strategy

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description

# Keep your branch up to date
git fetch upstream
git rebase upstream/main
```

### Making Changes

1. **Write Code**: Follow our coding standards (see below)
2. **Add Tests**: Include tests for new functionality
3. **Update Documentation**: Update relevant documentation
4. **Test Locally**: Ensure all tests pass
5. **Commit Changes**: Use clear, descriptive commit messages

### Commit Message Format

```
type(scope): brief description

Detailed explanation of the change (if needed)

Fixes #issue-number
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `style`: Code style changes
- `chore`: Maintenance tasks

**Examples:**
```
feat(automation): add support for new weather variable

Add support for humidity data processing with automatic
region detection and file organization.

Fixes #123

fix(dashboard): resolve WebSocket connection issues

The dashboard WebSocket connections were dropping after
30 seconds due to timeout configuration.

Fixes #456
```

## 📝 Coding Standards

### Python Code Style

We follow PEP 8 with some specific guidelines:

#### 1. Code Formatting
```python
# Use Black for automatic formatting
black src/

# Use isort for import sorting
isort src/

# Check with flake8
flake8 src/
```

#### 2. Type Hints
```python
# Always use type hints for function parameters and return values
def process_request(request_id: str, config: Dict[str, Any]) -> ProcessingResult:
    """Process a single request with proper error handling."""
    pass

# Use dataclasses for structured data
@dataclass
class RequestStatus:
    request_id: str
    status: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### 3. Error Handling
```python
# Comprehensive error handling with specific exceptions
async def sync_data(data_type: str) -> SyncResult:
    try:
        result = await perform_sync(data_type)
        return SyncResult(success=True, data=result)
    except APIError as e:
        logger.error(f"API error during sync: {e}")
        return SyncResult(success=False, error=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error during sync: {e}")
        return SyncResult(success=False, error="Internal error")
```

#### 4. Documentation
```python
def complex_function(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    """
    Brief description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (optional)
        
    Returns:
        Dictionary containing the results with keys:
        - 'status': Operation status
        - 'data': Processed data
        
    Raises:
        ValueError: If param1 is empty
        APIError: If external API call fails
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['status'])
        'success'
    """
    pass
```

### Code Organization

#### File Structure
```
src/python/automation/
├── __init__.py
├── core/                    # Core functionality
│   ├── __init__.py
│   ├── base_classes.py     # Base classes and interfaces
│   └── exceptions.py       # Custom exceptions
├── services/               # Business logic services
│   ├── __init__.py
│   ├── data_sync.py
│   └── status_monitor.py
├── utils/                  # Utility functions
│   ├── __init__.py
│   ├── coordinate_utils.py
│   └── date_utils.py
└── tests/                  # Tests alongside code
    ├── __init__.py
    ├── test_data_sync.py
    └── test_status_monitor.py
```

#### Import Organization
```python
# Standard library imports
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Third-party imports
import requests
import yaml
from flask import Flask

# Local imports
from automation.core.base_classes import BaseService
from automation.utils.coordinate_utils import extract_coordinates
```

## 🧪 Testing Guidelines

### Test Structure

```python
# test/test_example.py
import pytest
from unittest.mock import Mock, patch, AsyncMock

from automation.services.example_service import ExampleService


class TestExampleService:
    """Test suite for ExampleService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        config = {"test": True}
        return ExampleService(config)
    
    def test_basic_functionality(self, service):
        """Test basic service functionality."""
        result = service.process_data("test_input")
        assert result.success is True
        assert result.data == "expected_output"
    
    @pytest.mark.asyncio
    async def test_async_functionality(self, service):
        """Test async service functionality."""
        result = await service.async_process("test_input")
        assert result is not None
    
    @patch('automation.services.example_service.external_api_call')
    def test_with_mocked_api(self, mock_api, service):
        """Test functionality with mocked external API."""
        mock_api.return_value = {"status": "success"}
        result = service.call_external_api()
        assert result["status"] == "success"
        mock_api.assert_called_once()
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/python/automation --cov-report=html

# Run specific test file
python -m pytest test/test_data_sync.py -v

# Run tests matching pattern
python -m pytest -k "test_sync" -v

# Run tests with specific markers
python -m pytest -m "integration" -v
```

### Test Categories

Use pytest markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_unit_functionality():
    """Unit test - fast, no external dependencies."""
    pass

@pytest.mark.integration
def test_integration_functionality():
    """Integration test - may use external services."""
    pass

@pytest.mark.slow
def test_slow_functionality():
    """Slow test - takes significant time to run."""
    pass
```

## 📚 Documentation Guidelines

### Code Documentation

- **Docstrings**: All public functions and classes must have docstrings
- **Type Hints**: Use type hints for all function parameters and returns
- **Comments**: Explain complex logic, not obvious code
- **Examples**: Include usage examples in docstrings

### User Documentation

When updating user-facing documentation:

1. **Clear Language**: Use simple, clear language
2. **Examples**: Include practical examples
3. **Step-by-Step**: Break complex procedures into steps
4. **Screenshots**: Add screenshots for UI-related documentation
5. **Links**: Link to related documentation

### Documentation Structure

```markdown
# Title

Brief description of what this document covers.

## Section 1

Content with examples:

```bash
# Example command
python script.py --option value
```

### Subsection

More detailed information.

## Related Documentation

- [Link to related doc](path/to/doc.md)
```

## 🔍 Code Review Process

### Submitting Pull Requests

1. **Create Pull Request**: Use GitHub's PR template
2. **Describe Changes**: Clearly explain what and why
3. **Link Issues**: Reference related issues
4. **Add Screenshots**: For UI changes
5. **Request Review**: Tag relevant reviewers

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Other (please describe)

## Testing
- [ ] Tests pass locally
- [ ] Added new tests for new functionality
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

## Related Issues
Fixes #issue-number
```

### Review Criteria

Reviewers will check:

- **Functionality**: Does the code work as intended?
- **Style**: Does it follow coding standards?
- **Tests**: Are there adequate tests?
- **Documentation**: Is documentation updated?
- **Performance**: Are there performance implications?
- **Security**: Are there security considerations?

## 🐛 Bug Reports

### Before Reporting

1. **Search Existing Issues**: Check if already reported
2. **Try Latest Version**: Ensure you're using the latest code
3. **Minimal Reproduction**: Create minimal example that reproduces the bug

### Bug Report Template

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Ubuntu 20.04]
- Python Version: [e.g., 3.9.0]
- System Version: [e.g., commit hash or version]

## Additional Context
Any other relevant information

## Logs
```
Relevant log output
```
```

## ✨ Feature Requests

### Feature Request Template

```markdown
## Feature Description
Clear description of the proposed feature

## Use Case
Why is this feature needed? What problem does it solve?

## Proposed Solution
How should this feature work?

## Alternatives Considered
What other approaches were considered?

## Additional Context
Any other relevant information
```

## 🏗️ Architecture Guidelines

### Adding New Components

When adding new major components:

1. **Design Document**: Create design document first
2. **Interface Definition**: Define clear interfaces
3. **Error Handling**: Plan error handling strategy
4. **Testing Strategy**: Plan testing approach
5. **Documentation**: Plan documentation updates

### Component Structure

```python
# automation/services/new_service.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

from automation.core.base_classes import BaseService
from automation.core.exceptions import ServiceError


@dataclass
class ServiceConfig:
    """Configuration for the service."""
    setting1: str
    setting2: int = 10


class NewService(BaseService):
    """
    Service for handling new functionality.
    
    This service provides...
    """
    
    def __init__(self, config: ServiceConfig):
        super().__init__()
        self.config = config
        self._setup_logging()
    
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data.
        
        Args:
            data: Input data to process
            
        Returns:
            Processed data
            
        Raises:
            ServiceError: If processing fails
        """
        try:
            # Implementation here
            return {"status": "success", "data": processed_data}
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise ServiceError(f"Failed to process data: {e}")
```

## 🔒 Security Guidelines

### Security Considerations

- **Input Validation**: Always validate user input
- **Authentication**: Secure handling of RDA tokens
- **File Permissions**: Proper file and directory permissions
- **Logging**: Don't log sensitive information
- **Dependencies**: Keep dependencies updated

### Secure Coding Practices

```python
# Good: Input validation
def process_request_id(request_id: str) -> str:
    if not request_id or not request_id.isalnum():
        raise ValueError("Invalid request ID format")
    return request_id.upper()

# Good: Secure file handling
def read_token_file(token_path: str) -> str:
    if not os.path.exists(token_path):
        raise FileNotFoundError(f"Token file not found: {token_path}")
    
    # Check file permissions
    stat_info = os.stat(token_path)
    if stat_info.st_mode & 0o077:
        raise PermissionError("Token file has insecure permissions")
    
    with open(token_path, 'r') as f:
        return f.read().strip()

# Good: Don't log sensitive data
def log_request_info(request_id: str, token: str):
    # Don't do this: logger.info(f"Processing {request_id} with token {token}")
    logger.info(f"Processing request {request_id}")  # Good
```

## 📊 Performance Guidelines

### Performance Considerations

- **Async/Await**: Use async for I/O operations
- **Database**: Optimize database queries
- **Memory**: Be mindful of memory usage
- **Caching**: Use caching appropriately
- **Profiling**: Profile performance-critical code

### Performance Testing

```python
import time
import asyncio
from typing import List

async def benchmark_function(func, *args, iterations: int = 100) -> float:
    """Benchmark a function's performance."""
    start_time = time.time()
    
    for _ in range(iterations):
        if asyncio.iscoroutinefunction(func):
            await func(*args)
        else:
            func(*args)
    
    end_time = time.time()
    return (end_time - start_time) / iterations
```

## 🎯 Release Process

### Version Numbering

We use semantic versioning (SemVer):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version number bumped
- [ ] Release notes prepared
- [ ] Security review completed (for major releases)

## 📞 Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Pull Request Comments**: Code-specific discussions

### Asking Questions

When asking for help:

1. **Be Specific**: Describe the exact problem
2. **Provide Context**: Include relevant code and configuration
3. **Show Effort**: Explain what you've already tried
4. **Include Environment**: OS, Python version, etc.

## 🏆 Recognition

Contributors are recognized in:

- **README.md**: Major contributors listed
- **CHANGELOG.md**: Contributors mentioned in releases
- **GitHub**: Contributor statistics and graphs

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

---

## Quick Reference

### Common Commands

```bash
# Setup development environment
python -m venv dev_env && source dev_env/bin/activate
pip install -r requirements.txt
pip install black flake8 pytest mypy

# Code quality checks
black src/
isort src/
flake8 src/
mypy src/

# Run tests
python -m pytest
python -m pytest --cov=src/

# Create feature branch
git checkout -b feature/my-feature

# Commit changes
git add .
git commit -m "feat(component): add new functionality"

# Push and create PR
git push origin feature/my-feature
```

### Useful Links

- **[Architecture Overview](docs/developer-guides/architecture-overview.md)** - Understand the system
- **[Troubleshooting](docs/Troubleshooting_Guide.md)** - Common issues

---

*Thank you for contributing to the RDA Automation System! 🎉*