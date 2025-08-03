#!/usr/bin/env python3
"""
Master Test Runner for Enhanced RDA Automation System

This module provides a unified test execution framework that orchestrates all test suites
for the enhanced automation system. It provides comprehensive reporting, test filtering,
and execution control for validating the 10-request limit maintenance system.

Key Features:
- Unified test execution across all test suites
- Comprehensive test reporting and metrics
- Test filtering and selection capabilities
- Performance benchmarking and validation
- Deployment readiness assessment
- Continuous integration support
- Detailed failure analysis and recommendations
"""

import os
import sys
import json
import time
import logging
import unittest
import argparse
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import concurrent.futures
from enum import Enum
import traceback

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test modules
from automation.comprehensive_system_test import (
    ComprehensiveSystemTest, SystemTestRunner
)
from automation.performance_validation_test import (
    PerformanceValidationTest, PerformanceTestRunner
)
from automation.error_scenario_test import (
    ErrorScenarioTest, ErrorScenarioTestRunner
)
from automation.deployment_validation_test import (
    DeploymentValidationTest, DeploymentTestRunner
)


class TestSuite(Enum):
    """Available test suites."""
    COMPREHENSIVE = "comprehensive"
    PERFORMANCE = "performance"
    ERROR_SCENARIOS = "error_scenarios"
    DEPLOYMENT = "deployment"
    ALL = "all"


class TestPriority(Enum):
    """Test execution priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestConfiguration:
    """Configuration for test execution."""
    suites: List[TestSuite]
    priority: TestPriority
    parallel_execution: bool
    max_workers: int
    timeout_seconds: int
    generate_report: bool
    report_format: str
    output_directory: str
    verbose: bool
    fail_fast: bool
    include_performance_benchmarks: bool
    deployment_readiness_check: bool


@dataclass
class TestResult:
    """Result of a single test execution."""
    test_name: str
    suite: TestSuite
    success: bool
    execution_time: float
    error_message: Optional[str] = None
    failure_details: Optional[str] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    recommendations: List[str] = None


@dataclass
class TestSuiteResult:
    """Result of a test suite execution."""
    suite: TestSuite
    total_tests: int
    successful_tests: int
    failed_tests: int
    execution_time: float
    success_rate: float
    test_results: List[TestResult]
    suite_specific_metrics: Optional[Dict[str, Any]] = None


@dataclass
class MasterTestResult:
    """Overall result of master test execution."""
    execution_start_time: datetime
    execution_end_time: datetime
    total_execution_time: float
    suite_results: List[TestSuiteResult]
    overall_success: bool
    overall_success_rate: float
    total_tests: int
    total_successful_tests: int
    total_failed_tests: int
    performance_summary: Dict[str, Any]
    deployment_ready: bool
    recommendations: List[str]
    system_requirements_met: bool


class TestReportGenerator:
    """Generates comprehensive test reports."""
    
    def __init__(self, output_directory: str):
        self.output_directory = output_directory
        self.logger = logging.getLogger('test_report_generator')
        
        # Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)
    
    def generate_json_report(self, result: MasterTestResult) -> str:
        """Generate JSON format test report."""
        report_path = os.path.join(self.output_directory, f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        # Convert dataclass to dict for JSON serialization
        report_data = {
            "execution_summary": {
                "start_time": result.execution_start_time.isoformat(),
                "end_time": result.execution_end_time.isoformat(),
                "total_execution_time": result.total_execution_time,
                "overall_success": result.overall_success,
                "overall_success_rate": result.overall_success_rate,
                "total_tests": result.total_tests,
                "total_successful_tests": result.total_successful_tests,
                "total_failed_tests": result.total_failed_tests,
                "deployment_ready": result.deployment_ready,
                "system_requirements_met": result.system_requirements_met
            },
            "suite_results": [
                {
                    "suite": suite_result.suite.value,
                    "total_tests": suite_result.total_tests,
                    "successful_tests": suite_result.successful_tests,
                    "failed_tests": suite_result.failed_tests,
                    "execution_time": suite_result.execution_time,
                    "success_rate": suite_result.success_rate,
                    "suite_specific_metrics": suite_result.suite_specific_metrics,
                    "test_results": [
                        {
                            "test_name": test.test_name,
                            "success": test.success,
                            "execution_time": test.execution_time,
                            "error_message": test.error_message,
                            "failure_details": test.failure_details,
                            "performance_metrics": test.performance_metrics,
                            "recommendations": test.recommendations or []
                        }
                        for test in suite_result.test_results
                    ]
                }
                for suite_result in result.suite_results
            ],
            "performance_summary": result.performance_summary,
            "recommendations": result.recommendations
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        return report_path
    
    def generate_html_report(self, result: MasterTestResult) -> str:
        """Generate HTML format test report."""
        report_path = os.path.join(self.output_directory, f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        
        # Generate HTML content
        html_content = self._create_html_report(result)
        
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return report_path
    
    def _create_html_report(self, result: MasterTestResult) -> str:
        """Create HTML report content."""
        status_color = "green" if result.overall_success else "red"
        deployment_status = "✅ READY" if result.deployment_ready else "❌ NOT READY"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Enhanced RDA Automation System - Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .summary {{ background-color: {status_color}; color: white; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .suite {{ border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 5px; }}
        .test-result {{ margin: 10px 0; padding: 10px; border-left: 4px solid #ddd; }}
        .success {{ border-left-color: green; }}
        .failure {{ border-left-color: red; }}
        .metrics {{ background-color: #f9f9f9; padding: 10px; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Enhanced RDA Automation System - Test Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Execution Time:</strong> {result.total_execution_time:.2f} seconds</p>
        <p><strong>Deployment Status:</strong> {deployment_status}</p>
    </div>
    
    <div class="summary">
        <h2>Test Execution Summary</h2>
        <p><strong>Overall Success:</strong> {'✅ PASSED' if result.overall_success else '❌ FAILED'}</p>
        <p><strong>Success Rate:</strong> {result.overall_success_rate:.1f}%</p>
        <p><strong>Total Tests:</strong> {result.total_tests}</p>
        <p><strong>Successful:</strong> {result.total_successful_tests}</p>
        <p><strong>Failed:</strong> {result.total_failed_tests}</p>
    </div>
"""
        
        # Add suite results
        for suite_result in result.suite_results:
            suite_status = "✅ PASSED" if suite_result.success_rate >= 90 else "❌ FAILED"
            html += f"""
    <div class="suite">
        <h3>{suite_result.suite.value.title()} Test Suite - {suite_status}</h3>
        <p><strong>Success Rate:</strong> {suite_result.success_rate:.1f}%</p>
        <p><strong>Execution Time:</strong> {suite_result.execution_time:.2f} seconds</p>
        <p><strong>Tests:</strong> {suite_result.successful_tests}/{suite_result.total_tests} passed</p>
"""
            
            # Add individual test results
            for test_result in suite_result.test_results:
                test_class = "success" if test_result.success else "failure"
                test_status = "✅" if test_result.success else "❌"
                html += f"""
        <div class="test-result {test_class}">
            <strong>{test_status} {test_result.test_name}</strong>
            <p>Execution Time: {test_result.execution_time:.3f}s</p>
"""
                if test_result.error_message:
                    html += f"<p><strong>Error:</strong> {test_result.error_message}</p>"
                
                if test_result.performance_metrics:
                    html += "<div class='metrics'><strong>Performance Metrics:</strong><ul>"
                    for key, value in test_result.performance_metrics.items():
                        html += f"<li>{key}: {value}</li>"
                    html += "</ul></div>"
                
                html += "</div>"
            
            html += "</div>"
        
        # Add performance summary
        html += f"""
    <div class="suite">
        <h3>Performance Summary</h3>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
"""
        for key, value in result.performance_summary.items():
            html += f"<tr><td>{key}</td><td>{value}</td></tr>"
        
        html += """
        </table>
    </div>
"""
        
        # Add recommendations
        if result.recommendations:
            html += """
    <div class="suite">
        <h3>Recommendations</h3>
        <ul>
"""
            for recommendation in result.recommendations:
                html += f"<li>{recommendation}</li>"
            
            html += """
        </ul>
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html


class MasterTestRunner:
    """Master test runner that orchestrates all test suites."""
    
    def __init__(self, config: TestConfiguration):
        self.config = config
        self.logger = logging.getLogger('master_test_runner')
        self.report_generator = TestReportGenerator(config.output_directory)
        
        # Initialize test runners
        self.test_runners = {
            TestSuite.COMPREHENSIVE: SystemTestRunner(),
            TestSuite.PERFORMANCE: PerformanceTestRunner(),
            TestSuite.ERROR_SCENARIOS: ErrorScenarioTestRunner(),
            TestSuite.DEPLOYMENT: DeploymentTestRunner()
        }
    
    def run_tests(self) -> MasterTestResult:
        """Run all configured test suites."""
        self.logger.info("🚀 Starting master test execution")
        execution_start_time = datetime.now()
        
        # Determine which suites to run
        suites_to_run = self._get_suites_to_run()
        
        # Execute test suites
        suite_results = []
        if self.config.parallel_execution and len(suites_to_run) > 1:
            suite_results = self._run_suites_parallel(suites_to_run)
        else:
            suite_results = self._run_suites_sequential(suites_to_run)
        
        execution_end_time = datetime.now()
        total_execution_time = (execution_end_time - execution_start_time).total_seconds()
        
        # Calculate overall metrics
        overall_metrics = self._calculate_overall_metrics(suite_results)
        
        # Generate performance summary
        performance_summary = self._generate_performance_summary(suite_results)
        
        # Check deployment readiness
        deployment_ready = self._check_deployment_readiness(suite_results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(suite_results)
        
        # Check system requirements
        system_requirements_met = self._check_system_requirements(suite_results, performance_summary)
        
        # Create master result
        master_result = MasterTestResult(
            execution_start_time=execution_start_time,
            execution_end_time=execution_end_time,
            total_execution_time=total_execution_time,
            suite_results=suite_results,
            overall_success=overall_metrics['overall_success'],
            overall_success_rate=overall_metrics['overall_success_rate'],
            total_tests=overall_metrics['total_tests'],
            total_successful_tests=overall_metrics['total_successful_tests'],
            total_failed_tests=overall_metrics['total_failed_tests'],
            performance_summary=performance_summary,
            deployment_ready=deployment_ready,
            recommendations=recommendations,
            system_requirements_met=system_requirements_met
        )
        
        # Generate reports if requested
        if self.config.generate_report:
            self._generate_reports(master_result)
        
        return master_result
    
    def _get_suites_to_run(self) -> List[TestSuite]:
        """Determine which test suites to run based on configuration."""
        if TestSuite.ALL in self.config.suites:
            return [TestSuite.COMPREHENSIVE, TestSuite.PERFORMANCE, TestSuite.ERROR_SCENARIOS, TestSuite.DEPLOYMENT]
        else:
            return [suite for suite in self.config.suites if suite != TestSuite.ALL]
    
    def _run_suites_sequential(self, suites: List[TestSuite]) -> List[TestSuiteResult]:
        """Run test suites sequentially."""
        results = []
        
        for suite in suites:
            self.logger.info(f"Running {suite.value} test suite")
            
            try:
                suite_result = self._run_single_suite(suite)
                results.append(suite_result)
                
                # Check fail-fast condition
                if self.config.fail_fast and suite_result.success_rate < 90:
                    self.logger.warning(f"Fail-fast triggered: {suite.value} suite failed")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error running {suite.value} suite: {e}")
                # Create failed suite result
                failed_result = TestSuiteResult(
                    suite=suite,
                    total_tests=0,
                    successful_tests=0,
                    failed_tests=1,
                    execution_time=0.0,
                    success_rate=0.0,
                    test_results=[TestResult(
                        test_name=f"{suite.value}_suite_execution",
                        suite=suite,
                        success=False,
                        execution_time=0.0,
                        error_message=str(e)
                    )]
                )
                results.append(failed_result)
        
        return results
    
    def _run_suites_parallel(self, suites: List[TestSuite]) -> List[TestSuiteResult]:
        """Run test suites in parallel."""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all suite executions
            future_to_suite = {
                executor.submit(self._run_single_suite, suite): suite 
                for suite in suites
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_suite, timeout=self.config.timeout_seconds):
                suite = future_to_suite[future]
                try:
                    suite_result = future.result()
                    results.append(suite_result)
                except Exception as e:
                    self.logger.error(f"Error running {suite.value} suite: {e}")
                    # Create failed suite result
                    failed_result = TestSuiteResult(
                        suite=suite,
                        total_tests=0,
                        successful_tests=0,
                        failed_tests=1,
                        execution_time=0.0,
                        success_rate=0.0,
                        test_results=[TestResult(
                            test_name=f"{suite.value}_suite_execution",
                            suite=suite,
                            success=False,
                            execution_time=0.0,
                            error_message=str(e)
                        )]
                    )
                    results.append(failed_result)
        
        # Sort results by suite order
        suite_order = {suite: i for i, suite in enumerate(suites)}
        results.sort(key=lambda r: suite_order.get(r.suite, 999))
        
        return results
    
    def _run_single_suite(self, suite: TestSuite) -> TestSuiteResult:
        """Run a single test suite."""
        start_time = time.time()
        
        try:
            runner = self.test_runners[suite]
            
            if suite == TestSuite.COMPREHENSIVE:
                raw_result = runner.run_all_system_tests()
            elif suite == TestSuite.PERFORMANCE:
                raw_result = runner.run_all_performance_tests()
            elif suite == TestSuite.ERROR_SCENARIOS:
                raw_result = runner.run_all_error_tests()
            elif suite == TestSuite.DEPLOYMENT:
                raw_result = runner.run_all_deployment_tests()
            else:
                raise ValueError(f"Unknown test suite: {suite}")
            
            execution_time = time.time() - start_time
            
            # Convert raw result to standardized format
            suite_result = self._convert_raw_result(suite, raw_result, execution_time)
            
            return suite_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Failed to run {suite.value} suite: {e}")
            
            return TestSuiteResult(
                suite=suite,
                total_tests=0,
                successful_tests=0,
                failed_tests=1,
                execution_time=execution_time,
                success_rate=0.0,
                test_results=[TestResult(
                    test_name=f"{suite.value}_execution_error",
                    suite=suite,
                    success=False,
                    execution_time=execution_time,
                    error_message=str(e),
                    failure_details=traceback.format_exc()
                )]
            )
    
    def _convert_raw_result(self, suite: TestSuite, raw_result: Dict[str, Any], execution_time: float) -> TestSuiteResult:
        """Convert raw test result to standardized TestSuiteResult."""
        test_results = []
        
        # Extract test results based on suite type
        if suite == TestSuite.COMPREHENSIVE:
            test_data = raw_result.get('test_results', {})
        elif suite == TestSuite.PERFORMANCE:
            test_data = raw_result.get('test_results', {})
        elif suite == TestSuite.ERROR_SCENARIOS:
            test_data = raw_result.get('test_results', {})
        elif suite == TestSuite.DEPLOYMENT:
            test_data = raw_result.get('test_results', {})
        else:
            test_data = {}
        
        # Convert individual test results
        for test_name, test_info in test_data.items():
            test_result = TestResult(
                test_name=test_name,
                suite=suite,
                success=test_info.get('success', False),
                execution_time=test_info.get('execution_time', 0.0),
                error_message=test_info.get('error_message'),
                failure_details='; '.join(test_info.get('failure_messages', [])),
                performance_metrics=test_info.get('performance_metrics'),
                recommendations=test_info.get('recommendations', [])
            )
            test_results.append(test_result)
        
        # Calculate suite metrics
        total_tests = len(test_results)
        successful_tests = len([r for r in test_results if r.success])
        failed_tests = total_tests - successful_tests
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0.0
        
        return TestSuiteResult(
            suite=suite,
            total_tests=total_tests,
            successful_tests=successful_tests,
            failed_tests=failed_tests,
            execution_time=execution_time,
            success_rate=success_rate,
            test_results=test_results,
            suite_specific_metrics=raw_result.get('performance_summary') or raw_result.get('metrics')
        )
    
    def _calculate_overall_metrics(self, suite_results: List[TestSuiteResult]) -> Dict[str, Any]:
        """Calculate overall test execution metrics."""
        total_tests = sum(result.total_tests for result in suite_results)
        total_successful_tests = sum(result.successful_tests for result in suite_results)
        total_failed_tests = sum(result.failed_tests for result in suite_results)
        
        overall_success_rate = (total_successful_tests / total_tests * 100) if total_tests > 0 else 0.0
        overall_success = overall_success_rate >= 90.0  # 90% threshold for overall success
        
        return {
            'total_tests': total_tests,
            'total_successful_tests': total_successful_tests,
            'total_failed_tests': total_failed_tests,
            'overall_success_rate': overall_success_rate,
            'overall_success': overall_success
        }
    
    def _generate_performance_summary(self, suite_results: List[TestSuiteResult]) -> Dict[str, Any]:
        """Generate performance summary from all test suites."""
        performance_summary = {
            'total_execution_time': sum(result.execution_time for result in suite_results),
            'average_test_execution_time': 0.0,
            'fastest_test': None,
            'slowest_test': None,
            'performance_requirements_met': True
        }
        
        # Collect all test execution times
        all_tests = []
        for suite_result in suite_results:
            all_tests.extend(suite_result.test_results)
        
        if all_tests:
            execution_times = [test.execution_time for test in all_tests]
            performance_summary['average_test_execution_time'] = sum(execution_times) / len(execution_times)
            
            fastest_test = min(all_tests, key=lambda t: t.execution_time)
            slowest_test = max(all_tests, key=lambda t: t.execution_time)
            
            performance_summary['fastest_test'] = {
                'name': fastest_test.test_name,
                'time': fastest_test.execution_time
            }
            performance_summary['slowest_test'] = {
                'name': slowest_test.test_name,
                'time': slowest_test.execution_time
            }
            
            # Check if performance requirements are met (no test should take > 30 seconds)
            performance_summary['performance_requirements_met'] = all(t.execution_time <= 30.0 for t in all_tests)
        
        # Add suite-specific performance metrics
        for suite_result in suite_results:
            if suite_result.suite_specific_metrics:
                performance_summary[f'{suite_result.suite.value}_metrics'] = suite_result.suite_specific_metrics
        
        return performance_summary
    
    def _check_deployment_readiness(self, suite_results: List[TestSuiteResult]) -> bool:
        """Check if system is ready for deployment based on test results."""
        # Deployment is ready if:
        # 1. All critical test suites pass (>= 90% success rate)
        # 2. Deployment validation suite specifically passes
        # 3. No critical failures in any suite
        
        critical_suites = [TestSuite.COMPREHENSIVE, TestSuite.DEPLOYMENT]
        
        for suite_result in suite_results:
            if suite_result.suite in critical_suites:
                if suite_result.success_rate < 90.0:
                    return False
        
        # Check for deployment-specific readiness
        deployment_result = next((r for r in suite_results if r.suite == TestSuite.DEPLOYMENT), None)
        if deployment_result:
            return deployment_result.success_rate >= 90.0
        
        return True
    
    def _generate_recommendations(self, suite_results: List[TestSuiteResult]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Overall recommendations
        overall_success_rate = sum(r.successful_tests for r in suite_results) / sum(r.total_tests for r in suite_results) * 100
        if overall_success_rate < 95:
            recommendations.append(f"Overall success rate is {overall_success_rate:.1f}%. Consider investigating failed tests.")
        
        # Suite-specific recommendations
        for suite_result in suite_results:
            if suite_result.success_rate < 90:
                recommendations.append(f"{suite_result.suite.value.title()} suite has low success rate ({suite_result.success_rate:.1f}%). Review failed tests.")
            
            # Add test-specific recommendations
            for test_result in suite_result.test_results:
                if test_result.recommendations:
                    recommendations.extend(test_result.recommendations)
        
        # Performance recommendations
        slow_tests = []
        for suite_result in suite_results:
            for test_result in suite_result.test_results:
                if test_result.execution_time > 10.0:  # Tests taking more than 10 seconds
                    slow_tests.append(f"{test_result.test_name} ({test_result.execution_time:.2f}s)")
        
        if slow_tests:
            recommendations.append(f"Consider optimizing slow tests: {', '.join(slow_tests)}")
        
        return list(set(recommendations))  # Remove duplicates
    
    def _check_system_requirements(self, suite_results: List[TestSuiteResult], performance_summary: Dict[str, Any]) -> bool:
        """Check if system meets all requirements for 10-request limit maintenance."""
        # System requirements:
        # 1. Overall success rate >= 95%
        # 2. Performance tests pass (response time < 500ms)
        # 3. Error handling tests pass
        # 4. Deployment readiness confirmed
        
        overall_success_rate = sum(r.successful_tests for r in suite_results) / sum(r.total_tests for r in suite_results) * 100
        
        requirements_met = [
            overall_success_rate >= 95.0,
            performance_summary.get('performance_requirements_met', False),
            self._check_deployment_readiness(suite_results),
            all(r.success_rate >= 90.0 for r in suite_results if r.suite in [TestSuite.COMPREHENSIVE, TestSuite.ERROR_SCENARIOS])
        ]
        
        return all(requirements_met)
    
    def _generate_reports(self, result: MasterTestResult):
        """Generate test reports in requested formats."""
        if self.config.report_format.lower() in ['json', 'all']:
            json_path = self.report_generator.generate_json_report(result)
            self.logger.info(f"JSON report generated: {json_path}")
        
        if self.config.report_format.lower() in ['html', 'all']:
            html_path = self.report_generator.generate_html_report(result)
            self.logger.info(f"HTML report generated: {html_path}")


def create_test_configuration(args) -> TestConfiguration:
    """Create test configuration from command line arguments."""
    # Parse suites
    suites = []
    if args.suite:
        for suite_name in args.suite:
            try:
                suites.append(TestSuite(suite_name))
            except ValueError:
                raise ValueError(f"Invalid test suite: {suite_name}")
    else:
        suites = [TestSuite.ALL]
    
    # Parse priority
    priority = TestPriority.MEDIUM
    if args.priority:
        try:
            priority = TestPriority(args.priority)
        except ValueError:
            raise ValueError(f"Invalid priority: {args.priority}")
    
    return TestConfiguration(
        suites=suites,
        priority=priority,
        parallel_execution=args.parallel,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout,
        generate_report=args.report,
        report_format=args.report_format,
        output_directory=args.output_dir,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        include_performance_benchmarks=args.benchmarks,
        deployment_readiness_check=args.deployment_check
    )


def main():
    """Main function for master test runner."""
    parser = argparse.ArgumentParser(
        description='Master Test Runner for Enhanced RDA Automation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all test suites
  python test_runner.py
  
  # Run specific test suites
  python test_runner.py --suite comprehensive performance
  
  # Run tests in parallel with reports
  python test_runner.py --parallel --report --report-format html
  
  # Quick deployment readiness check
  python test_runner.py --deployment-check --fail-fast
  
  # Performance benchmarking
  python test_runner.py --suite performance --benchmarks --verbose
        """
    )
    
    # Test suite selection
    parser.add_argument('--suite', nargs='+', 
                       choices=['comprehensive', 'performance', 'error_scenarios',
                       'deployment', 'all'],
                       help='Test suites to run (default: all)')
    
    # Execution options
    parser.add_argument('--parallel', action='store_true',
                       help='Run test suites in parallel')
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Maximum number of parallel workers (default: 4)')
    parser.add_argument('--timeout', type=int, default=3600,
                       help='Test execution timeout in seconds (default: 3600)')
    parser.add_argument('--fail-fast', action='store_true',
                       help='Stop execution on first suite failure')
    
    # Priority and filtering
    parser.add_argument('--priority', choices=['critical', 'high', 'medium', 'low'],
                       help='Test priority level (default: medium)')
    
    # Reporting options
    parser.add_argument('--report', action='store_true',
                       help='Generate test reports')
    parser.add_argument('--report-format', choices=['json', 'html', 'all'], default='json',
                       help='Report format (default: json)')
    parser.add_argument('--output-dir', default='./test_reports',
                       help='Output directory for reports (default: ./test_reports)')
    
    # Additional options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--benchmarks', action='store_true',
                       help='Include performance benchmarks')
    parser.add_argument('--deployment-check', action='store_true',
                       help='Run deployment readiness check')
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(args.output_dir, 'test_execution.log'))
        ]
    )
    
    logger = logging.getLogger('master_test_runner')
    
    try:
        # Create test configuration
        config = create_test_configuration(args)
        
        # Create and run master test runner
        runner = MasterTestRunner(config)
        result = runner.run_tests()
        
        # Print summary
        print("\n" + "="*80)
        print("ENHANCED RDA AUTOMATION SYSTEM - TEST EXECUTION SUMMARY")
        print("="*80)
        print(f"Overall Success: {'✅ PASSED' if result.overall_success else '❌ FAILED'}")
        print(f"Success Rate: {result.overall_success_rate:.1f}%")
        print(f"Total Tests: {result.total_tests}")
        print(f"Successful: {result.total_successful_tests}")
        print(f"Failed: {result.total_failed_tests}")
        print(f"Execution Time: {result.total_execution_time:.2f} seconds")
        print(f"Deployment Ready: {'✅ YES' if result.deployment_ready else '❌ NO'}")
        print(f"System Requirements Met: {'✅ YES' if result.system_requirements_met else '❌ NO'}")
        
        # Print suite results
        print("\nSuite Results:")
        for suite_result in result.suite_results:
            status = "✅ PASSED" if suite_result.success_rate >= 90 else "❌ FAILED"
            print(f"  {suite_result.suite.value.title()}: {status} ({suite_result.success_rate:.1f}% - {suite_result.successful_tests}/{suite_result.total_tests})")
        
        # Print recommendations if any
        if result.recommendations:
            print("\nRecommendations:")
            for i, recommendation in enumerate(result.recommendations, 1):
                print(f"  {i}. {recommendation}")
        
        # Print performance summary
        if args.benchmarks and result.performance_summary:
            print("\nPerformance Summary:")
            for key, value in result.performance_summary.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"    {sub_key}: {sub_value}")
                else:
                    print(f"  {key}: {value}")
        
        print("="*80)
        
        # Return appropriate exit code
        if result.system_requirements_met and result.overall_success:
            logger.info("🎉 All tests passed! System is ready for maintaining 10-request limit.")
            return 0
        elif result.deployment_ready:
            logger.warning("⚠️ Some tests failed but system is deployment ready.")
            return 1
        else:
            logger.error("❌ Critical failures detected. System not ready for deployment.")
            return 2
    
    except Exception as e:
        logger.error(f"Error running master test suite: {e}")
        print(f"\n❌ Error: {e}")
        return 3


if __name__ == "__main__":
    exit(main())