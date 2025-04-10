#!/usr/bin/env python3
"""
Test runner for the TUI component tests.
This script runs all the tests in the tests directory.
"""

import unittest
import sys
import os
import importlib

def run_tests():
    """
    Discover and run all tests in the tests directory.
    """
    # Add parent directory to path to import modules
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(parent_dir)
    
    # Get list of test modules
    test_files = [f[:-3] for f in os.listdir('.') if f.startswith('test_') and f.endswith('.py')]
    
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add all tests to the suite
    for test_file in test_files:
        try:
            # Import the test module
            module = importlib.import_module(test_file)
            
            # Add all test cases from the module
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj != unittest.TestCase:
                    test_suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(obj))
        except Exception as e:
            print(f"Error importing {test_file}: {e}")
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests()) 