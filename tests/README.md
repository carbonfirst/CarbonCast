# RDA Automation System Test Suite

This directory contains comprehensive tests for the RDA (Research Data Archive) Automation System. The test suite is organized to ensure thorough coverage of all system components and workflows.

## Test Structure

```
tests/
├── README.md                    # This file - test documentation
├── conftest.py                  # Pytest configuration and shared fixtures
├── __init__.py                  # Package initialization
├── unit/                        # Unit tests for individual components
│   ├── __init__.py
│   └── test_*.py               # Unit test files
├── integration/                 # Integration tests for system workflows
│   ├── __init__.py
│   ├── test_auto_upload_integration.py
│   └── test_retry_manager_integration.py
└── fixtures/                    # Test data and sample files
    ├── __init__.py
    ├── sample_config.json       # Sample configuration file
    └── sample_control.ctl       # Sample control file
```

## Running Tests

### Prerequisites

1. **Python Environment**: Ensure you have Python 3.8+ installed
2. **Dependencies**: Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. **Test Dependencies**: Install pytest and related packages:
   ```bash
   pip install pytest pytest-cov pytest-mock
   ```

### Running All Tests

From the project root directory:

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src/python --cov-report=html
```

### Running Specific Test Categories

```bash
# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run tests with specific markers
pytest -m "integration" -v
pytest -m "unit" -v
pytest -m "requires_db" -v
```

### Running Individual Test Files

```bash
# Run specific test file
pytest tests/integration/test_auto_upload_integration.py -v

# Run specific test method
pytest tests/integration/test_auto_upload_integration.py::TestAutoUploadIntegration::test_auto_upload_when_slots_available -v
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests focus on testing individual components in isolation with mocked dependencies. These tests are:
- **Fast**: Execute quickly with minimal setup
- **Isolated**: Test single functions/classes without external dependencies
- **Focused**: Test specific functionality and edge cases

**Current Unit Tests:**
- *To be added as components are developed*

### Integration Tests (`tests/integration/`)

Integration tests verify that multiple components work together correctly. These tests:
- **Realistic**: Use actual component interactions
- **Comprehensive**: Test complete workflows and data flows
- **Database-aware**: May use temporary databases for testing

**Current Integration Tests:**
- `test_auto_upload_integration.py`: Tests the auto-upload functionality that triggers when request slots are available
- `test_retry_manager_integration.py`: Tests the retry manager's integration with error handling and batch systems

## Test Configuration

### Shared Fixtures (`conftest.py`)

The `conftest.py` file provides shared fixtures used across all tests:

- **`test_config`**: Standard test configuration dictionary
- **`temp_config_file`**: Temporary configuration file for testing
- **`temp_database`**: Temporary SQLite database with test schema
- **`mock_batch_system`**: Mock batch automation system
- **`mock_queue_manager`**: Mock queue manager
- **`mock_upload_files`**: Mock upload_files module
- **`sample_test_data`**: Sample data for various test scenarios
- **`test_directories`**: Temporary test directories
- **`populated_database`**: Database pre-populated with test data

### Test Markers

Tests are automatically marked based on their location and fixtures:

- `@pytest.mark.unit`: Unit tests (in `tests/unit/`)
- `@pytest.mark.integration`: Integration tests (in `tests/integration/`)
- `@pytest.mark.requires_db`: Tests requiring database fixtures
- `@pytest.mark.slow`: Long-running tests

## Writing New Tests

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, patch
from src.python.automation.component import ComponentClass

class TestComponentClass:
    """Unit tests for ComponentClass."""
    
    def test_component_method(self, test_config):
        """Test component method with mocked dependencies."""
        # Arrange
        component = ComponentClass(test_config)
        
        # Act
        result = component.method()
        
        # Assert
        assert result is not None
```

### Integration Test Example

```python
import pytest
from src.python.automation.system import SystemClass

@pytest.mark.integration
class TestSystemIntegration:
    """Integration tests for system workflows."""
    
    def test_complete_workflow(self, temp_database, mock_batch_system):
        """Test complete system workflow."""
        # Arrange
        system = SystemClass(temp_database, mock_batch_system)
        
        # Act
        result = system.run_workflow()
        
        # Assert
        assert result['success'] is True
```

## Test Data and Fixtures

### Sample Configuration

The `tests/fixtures/sample_config.json` provides a standard configuration for testing with:
- Automation settings (request limits, intervals, retry configuration)
- Upload configuration (rate limits, file discovery)
- Directory paths for test environments
- Database configuration
- Logging configuration
- Region and parameter definitions

### Sample Control Files

The `tests/fixtures/sample_control.ctl` provides a sample GrADS control file for testing file processing functionality.

## Coverage Requirements

- **Minimum Coverage**: 80% overall code coverage
- **Critical Components**: 90%+ coverage for core automation components
- **Integration Paths**: All major workflow paths should be tested

### Generating Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/ --cov=src/python --cov-report=html

# Generate terminal coverage report
pytest tests/ --cov=src/python --cov-report=term-missing

# Generate XML coverage report (for CI/CD)
pytest tests/ --cov=src/python --cov-report=xml
```

## Continuous Integration

### GitHub Actions Integration

The test suite is designed to work with GitHub Actions CI/CD:

```yaml
# Example .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ --cov=src/python --cov-report=xml
```

## Debugging Tests

### Running Tests in Debug Mode

```bash
# Run with Python debugger
pytest tests/ --pdb

# Run with detailed output
pytest tests/ -vvv --tb=long

# Run specific test with debugging
pytest tests/integration/test_auto_upload_integration.py::TestAutoUploadIntegration::test_auto_upload_when_slots_available -vvv --pdb
```

### Common Issues and Solutions

1. **Import Errors**: Ensure `src/python` is in the Python path
2. **Database Errors**: Check that temporary databases are properly cleaned up
3. **Mock Issues**: Verify that mocks are properly configured and reset between tests
4. **Path Issues**: Use relative paths and proper path joining for cross-platform compatibility

## Best Practices

### Test Organization

1. **One test class per component**: Keep tests organized by the component they test
2. **Descriptive test names**: Use clear, descriptive names that explain what is being tested
3. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification phases
4. **Independent tests**: Each test should be able to run independently

### Mock Usage

1. **Mock external dependencies**: Mock file systems, databases, network calls
2. **Use fixtures for common mocks**: Leverage `conftest.py` for frequently used mocks
3. **Verify mock calls**: Assert that mocks are called with expected parameters
4. **Reset mocks**: Ensure mocks are reset between tests

### Test Data

1. **Use fixtures**: Leverage pytest fixtures for test data
2. **Minimal test data**: Use the smallest dataset that validates the functionality
3. **Realistic data**: Ensure test data represents real-world scenarios
4. **Clean up**: Always clean up temporary files and databases

## Contributing

When adding new tests:

1. **Follow naming conventions**: `test_*.py` for test files, `test_*` for test methods
2. **Add appropriate markers**: Use `@pytest.mark.unit` or `@pytest.mark.integration`
3. **Update documentation**: Update this README when adding new test categories
4. **Maintain coverage**: Ensure new code is adequately tested
5. **Run full test suite**: Verify that new tests don't break existing functionality

## Support

For questions about the test suite:

1. **Check this documentation**: Most common questions are answered here
2. **Review existing tests**: Look at similar tests for patterns and examples
3. **Check pytest documentation**: [pytest.org](https://pytest.org/) for pytest-specific questions
4. **Review conftest.py**: Check available fixtures and configuration options

---

**Last Updated**: January 2025  
**Test Suite Version**: 1.0.0  
**Python Version**: 3.8+  
**Pytest Version**: 6.0+