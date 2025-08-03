#!/usr/bin/env python3
"""
Dependency Verification Script for CarbonCast Automation System

This script verifies that all required dependencies are properly installed
and can be imported. It provides clear error messages if dependencies are
missing and suggests solutions.

Usage:
    python verify_dependencies.py [--verbose] [--fix]
    
Options:
    --verbose: Show detailed information about each dependency
    --fix: Attempt to install missing dependencies automatically
"""

import sys
import os
import subprocess
import importlib
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@dataclass
class Dependency:
    """Represents a Python dependency with import and package information."""
    import_name: str
    package_name: str
    description: str
    required: bool = True
    min_version: Optional[str] = None

# Define all dependencies
DEPENDENCIES = [
    # Core dependencies
    Dependency("requests", "requests>=2.28.0", "HTTP requests for RDA API communication", True),
    Dependency("flask", "flask>=2.2.0", "Web framework for dashboard", True),
    Dependency("flask_cors", "flask-cors>=4.0.0", "Cross-Origin Resource Sharing support", True),
    Dependency("psutil", "psutil>=5.9.0", "System and process utilities", True),
    Dependency("yaml", "pyyaml>=6.0", "YAML configuration file parsing", True),
    Dependency("jsonschema", "jsonschema>=3.2.0", "JSON schema validation", True),
    
    # Data processing dependencies
    Dependency("numpy", "numpy>=1.21.0", "Numerical computing for data processing", True),
    Dependency("pandas", "pandas>=1.5.0", "Data manipulation and analysis", True),
    Dependency("matplotlib", "matplotlib>=3.6.0", "Plotting and visualization", True),
    
    # Testing dependencies
    Dependency("pytest", "pytest>=7.0.0", "Testing framework", False),
    Dependency("pytest_mock", "pytest-mock>=3.10.0", "Mocking support for tests", False),
    Dependency("pytest_cov", "pytest-cov>=4.0.0", "Coverage reporting for tests", False),
    
    # Development dependencies
    Dependency("black", "black>=22.0.0", "Code formatter", False),
    Dependency("flake8", "flake8>=5.0.0", "Linting and style checking", False),
    Dependency("isort", "isort>=5.10.0", "Import sorting", False),
    Dependency("mypy", "mypy>=0.991", "Static type checking", False),
]

# Project-specific modules that should be available
PROJECT_MODULES = [
    "fix_completed_requests",
    "rdams_client",
    "coordinate_utils",
    "date_utils",
    "directory_utils",
]

class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color

def print_colored(message: str, color: str = Colors.NC) -> None:
    """Print a colored message to the terminal."""
    print(f"{color}{message}{Colors.NC}")

def print_header(title: str) -> None:
    """Print a formatted header."""
    print_colored(f"\n{'='*60}", Colors.BLUE)
    print_colored(f"{title:^60}", Colors.BLUE)
    print_colored(f"{'='*60}\n", Colors.BLUE)

def get_package_version(package_name: str) -> Optional[str]:
    """Get the version of an installed package."""
    try:
        import pkg_resources
        return pkg_resources.get_distribution(package_name).version
    except:
        try:
            # Alternative method for newer pip versions
            result = subprocess.run([sys.executable, "-m", "pip", "show", package_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        return line.split(':', 1)[1].strip()
        except:
            pass
    return None

def check_dependency(dep: Dependency, verbose: bool = False) -> Tuple[bool, str]:
    """
    Check if a dependency can be imported and return status.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Try to import the module
        importlib.import_module(dep.import_name)
        
        # Get version if available
        version = get_package_version(dep.package_name.split('>=')[0])
        version_info = f" (v{version})" if version else ""
        
        if verbose:
            return True, f"✅ {dep.import_name}{version_info} - {dep.description}"
        else:
            return True, f"✅ {dep.import_name}{version_info}"
            
    except ImportError as e:
        error_msg = str(e)
        if verbose:
            return False, f"❌ {dep.import_name} - MISSING: {error_msg}"
        else:
            return False, f"❌ {dep.import_name} - MISSING"

def check_project_modules(verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Check project-specific modules."""
    results = []
    
    for module_name in PROJECT_MODULES:
        try:
            importlib.import_module(module_name)
            if verbose:
                results.append((module_name, True, f"✅ {module_name} - Project module available"))
            else:
                results.append((module_name, True, f"✅ {module_name}"))
        except ImportError as e:
            if verbose:
                results.append((module_name, False, f"❌ {module_name} - {str(e)}"))
            else:
                results.append((module_name, False, f"❌ {module_name} - MISSING"))
    
    return results

def check_python_version() -> Tuple[bool, str]:
    """Check if Python version meets requirements."""
    version = sys.version_info
    required_major, required_minor = 3, 8
    
    if version.major >= required_major and version.minor >= required_minor:
        return True, f"✅ Python {version.major}.{version.minor}.{version.micro} (>= {required_major}.{required_minor} required)"
    else:
        return False, f"❌ Python {version.major}.{version.minor}.{version.micro} (>= {required_major}.{required_minor} required)"

def check_virtual_environment() -> Tuple[bool, str]:
    """Check if running in a virtual environment."""
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if in_venv:
        return True, "✅ Running in virtual environment"
    else:
        return False, "⚠️  Not running in virtual environment (recommended)"

def install_missing_dependencies(missing_deps: List[Dependency]) -> bool:
    """Attempt to install missing dependencies."""
    if not missing_deps:
        return True
    
    print_colored("\n🔧 Attempting to install missing dependencies...", Colors.YELLOW)
    
    success = True
    for dep in missing_deps:
        try:
            print_colored(f"Installing {dep.package_name}...", Colors.BLUE)
            result = subprocess.run([sys.executable, "-m", "pip", "install", dep.package_name], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print_colored(f"✅ Successfully installed {dep.package_name}", Colors.GREEN)
            else:
                print_colored(f"❌ Failed to install {dep.package_name}: {result.stderr}", Colors.RED)
                success = False
                
        except Exception as e:
            print_colored(f"❌ Error installing {dep.package_name}: {e}", Colors.RED)
            success = False
    
    return success

def generate_requirements_file(missing_deps: List[Dependency]) -> None:
    """Generate a requirements file for missing dependencies."""
    if not missing_deps:
        return
    
    filename = "missing_requirements.txt"
    with open(filename, 'w') as f:
        f.write("# Missing dependencies for CarbonCast Automation System\n")
        f.write("# Install with: pip install -r missing_requirements.txt\n\n")
        for dep in missing_deps:
            f.write(f"{dep.package_name}  # {dep.description}\n")
    
    print_colored(f"\n📝 Generated {filename} with missing dependencies", Colors.CYAN)
    print_colored(f"Install with: pip install -r {filename}", Colors.CYAN)

def main():
    """Main verification function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify CarbonCast dependencies")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Show detailed information about each dependency")
    parser.add_argument("--fix", action="store_true",
                       help="Attempt to install missing dependencies automatically")
    parser.add_argument("--generate-requirements", action="store_true",
                       help="Generate requirements file for missing dependencies")
    
    args = parser.parse_args()
    
    print_header("CarbonCast Dependency Verification")
    
    # Check Python version
    python_ok, python_msg = check_python_version()
    print_colored(python_msg, Colors.GREEN if python_ok else Colors.RED)
    
    # Check virtual environment
    venv_ok, venv_msg = check_virtual_environment()
    print_colored(venv_msg, Colors.GREEN if venv_ok else Colors.YELLOW)
    
    print_colored("\n🔍 Checking required dependencies...", Colors.BLUE)
    
    # Check dependencies
    required_missing = []
    optional_missing = []
    all_good = True
    
    for dep in DEPENDENCIES:
        success, message = check_dependency(dep, args.verbose)
        print_colored(message, Colors.GREEN if success else Colors.RED)
        
        if not success:
            all_good = False
            if dep.required:
                required_missing.append(dep)
            else:
                optional_missing.append(dep)
    
    # Check project modules
    print_colored("\n🔍 Checking project modules...", Colors.BLUE)
    project_results = check_project_modules(args.verbose)
    
    project_missing = []
    for module_name, success, message in project_results:
        print_colored(message, Colors.GREEN if success else Colors.YELLOW)
        if not success:
            project_missing.append(module_name)
    
    # Summary
    print_header("Verification Summary")
    
    if all_good and not project_missing:
        print_colored("🎉 All dependencies are properly installed!", Colors.GREEN)
        print_colored("✅ Your CarbonCast environment is ready to use!", Colors.GREEN)
        return 0
    
    # Report issues
    if required_missing:
        print_colored(f"❌ {len(required_missing)} required dependencies are missing:", Colors.RED)
        for dep in required_missing:
            print_colored(f"   • {dep.package_name} - {dep.description}", Colors.RED)
    
    if optional_missing:
        print_colored(f"⚠️  {len(optional_missing)} optional dependencies are missing:", Colors.YELLOW)
        for dep in optional_missing:
            print_colored(f"   • {dep.package_name} - {dep.description}", Colors.YELLOW)
    
    if project_missing:
        print_colored(f"⚠️  {len(project_missing)} project modules could not be imported:", Colors.YELLOW)
        for module in project_missing:
            print_colored(f"   • {module}", Colors.YELLOW)
        print_colored("   (This is normal if you haven't run the full setup yet)", Colors.CYAN)
    
    # Provide solutions
    print_colored("\n🔧 Recommended actions:", Colors.BLUE)
    
    if required_missing:
        print_colored("1. Install missing required dependencies:", Colors.BLUE)
        print_colored("   pip install -r requirements.txt", Colors.CYAN)
        print_colored("   OR run the setup script: ./setup.sh", Colors.CYAN)
    
    if args.fix and required_missing:
        print_colored("\n🚀 Attempting automatic fix...", Colors.YELLOW)
        if install_missing_dependencies(required_missing):
            print_colored("✅ All missing dependencies installed successfully!", Colors.GREEN)
            return 0
        else:
            print_colored("❌ Some dependencies could not be installed automatically", Colors.RED)
    
    if args.generate_requirements:
        generate_requirements_file(required_missing + optional_missing)
    
    if not python_ok:
        print_colored("⚠️  Please upgrade Python to version 3.8 or higher", Colors.YELLOW)
    
    if not venv_ok:
        print_colored("💡 Consider using a virtual environment:", Colors.BLUE)
        print_colored("   python3 -m venv venv", Colors.CYAN)
        print_colored("   source venv/bin/activate", Colors.CYAN)
    
    return 1 if required_missing else 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_colored("\n\n⚠️  Verification interrupted by user", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n❌ Unexpected error during verification: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)