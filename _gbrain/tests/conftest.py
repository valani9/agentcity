"""Pytest configuration for the vstack gbrain test suite.

gbrain is an external CLI that may or may not be installed. Tests
mock ``shutil.which`` and ``subprocess.run`` to exercise both the
"gbrain present" and "gbrain absent" code paths without requiring
the binary to exist on the test machine.
"""
