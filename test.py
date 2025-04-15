import unittest
from pathlib import Path
from PySideAbdhUI import get_icon,get_stylesheet,get_resource_path

class TestResourceAccess(unittest.TestCase):
   
    def test_get_icon_resource(self):
        """
        Tests the get_resource_path function for retrieving an icon resource.
        
        Make sure that a file named 'test_icon.svg' exists in
        PySideAbdhUI/resources/icons/svg before running this test.
        """
        package = "PySideAbdhUI.resources.icons.svg"
        resource_name = "settings.svg"  # Ensure this file exists for the test
        
        # Attempt to retrieve the resource path
        resource_path = get_resource_path(package, resource_name)
        
        # Check that the returned object is a pathlib.Path instance
        self.assertIsInstance(resource_path, Path, "Expected a pathlib.Path instance.")
        # Verify that the resource file exists at that path
        self.assertTrue(resource_path.exists(), f"Resource file '{resource_name}' does not exist at {resource_path}.")
    
    def test_get_style_resource(self):
        """
        Tests the get_resource_path function for retrieving a style resource.
        
        Make sure that a file named 'default.qss' exists in
        PySideAbdhUI/resources/styles before running this test.
        """
        package = "PySideAbdhUI.resources.styles"
        resource_name = "default-dark.qss"  # Ensure this file exists for the test
        
        # Attempt to retrieve the resource path
        resource_path = get_resource_path(package, resource_name)
        
        # Check that the returned object is a pathlib.Path instance
        self.assertIsInstance(resource_path, Path, "Expected a pathlib.Path instance.")
        # Verify that the resource file exists at that path
        self.assertTrue(resource_path.exists(), f"Resource file '{resource_name}' does not exist at {resource_path}.")

if __name__ == "__main__":
    
    unittest.main()

# BIULD: python setup.py sdist bdist_wheel
# INSTALL: pip install path\to\dist\PySideAbdhUI-1.0.0-py3-none-any.whl
