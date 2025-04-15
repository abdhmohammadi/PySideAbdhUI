
import os
import re
import logging
from typing import Optional
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QtStyleSheetManager:
    
    def __init__(self, accent_color_template='@accent-color'):
        
        #string data type : stores style sheet loaded from a qss file
        #type annotation Optional[str] indicates that stylesheet can either be a string or None.
        # Initially, it is set to None.
        self.stylesheet: Optional[str] = None
        # placeholder template for accent color, and is used when the qss file be included accent color
        self.accent_color_template = accent_color_template
    
    def add_property_to_widget(self, widget_name: str, property_name: str, property_value: str):
        """
            Add or update a property for a specific widget in the stylesheet.

        Args:
            widget_name (str): The name of the widget (e.g., "QPushButton").
            property_name (str): The name of the property (e.g., "font-family").
            property_value (str): The value of the property (e.g., "'Arial'").
        """
        if self.stylesheet is None:
            logger.warning("No stylesheet loaded.")
            return

        # Create the new property string
        new_property = f"{property_name}: {property_value};"

        # Check if the widget already has a stylesheet definition
        widget_pattern = re.compile(rf'{widget_name}\s*{{[^}}]*}}')
        match = widget_pattern.search(self.stylesheet)

        if match:
            # Extract the existing stylesheet block for the widget
            widget_style = match.group(0)

            # Check if the property already exists in the widget's stylesheet
            property_pattern = re.compile(rf'{property_name}\s*:\s*[^;]+;')
            property_match = property_pattern.search(widget_style)

            if property_match:
                # If the property exists, update its value
                updated_style = widget_style.replace(property_match.group(0), new_property)
                self.stylesheet = self.stylesheet.replace(widget_style, updated_style)
                logger.info(f"Updated property '{property_name}' to '{property_value}' for widget '{widget_name}'.")
            else:
                # If the property does not exist, append it to the widget's stylesheet
                updated_style = widget_style.rstrip('}') + f"\n    {new_property}\n}}"
                self.stylesheet = self.stylesheet.replace(widget_style, updated_style)
                logger.info(f"Added property '{property_name}: {property_value}' to widget '{widget_name}'.")
        else:
            # If the widget does not exist, create a new stylesheet definition
            new_style = f"{widget_name} {{\n    {new_property}\n}}"
            self.stylesheet += "\n" + new_style
            logger.info(f"Created new stylesheet for widget '{widget_name}' with property '{property_name}: {property_value}'.")

        self.save_stylesheet()

    def remove_stylesheet_by_name(self, name: str) -> str:
        #
        #Remove all stylesheets specified with a given name, including pseudo-states.
        #
        #Args:
        #    name (str): The name of the stylesheet to remove.
        #
        #Returns:
        #    str: The updated stylesheet content without the specified stylesheets.
        #
        if self.stylesheet is None:
            logger.warning(f"No stylesheet loaded.")
            return ""
        
        # Use regex to find and remove all stylesheets with the given name and its pseudo-states
        pattern = re.compile(rf'{name}(:\w+)?\s*{{[\s\S]*?}}')
        self.stylesheet = re.sub(pattern, '', self.stylesheet)
        
        logger.info(f"Removed all stylesheets with name: {name}")
        
    def add_stylesheet(self,stylesheet:str=None):
        self.stylesheet = self.stylesheet + '\n' + stylesheet

    def load_stylesheet(self,qss_path:str) -> str:
        
        self.qss_file = qss_path

        if os.path.exists(self.qss_file):
            with open(self.qss_file, "r", encoding="utf-8") as file:
                self.stylesheet = file.read()
                file.close()
        else:
            logger.error(f"Failed to open stylesheet file: {self.qss_file}")
            
    def check_accent_color_placeholder(self) -> tuple[bool, str]:
        # 
        # Check if the accent-color placeholder exists in the stylesheet.
        # If it exists, extract its value.
        # Returns a tuple containing:
        # - A boolean indicating whether the placeholder exists.
        # - The value of the accent color (if found), otherwise an empty string.
        # 
        if self.stylesheet is None or not os.path.exists(self.qss_file):
            logger.warning(f"No stylesheet loaded.")
            return False, ''  # Placeholder does not exist
             
        if self.accent_color_template in self.stylesheet:

            # Extract the value of @accent-color
            accent_color_value = self.extract_accent_color_value()

            if accent_color_value:
                return True, accent_color_value
            else:
                logger.warning(f"Failed to extract {self.accent_color_template} value from the stylesheet.")
                return True, ''  # Placeholder exists, but value extraction failed
        else:
            logger.warning(f"No {self.accent_color_template} placeholder found in the stylesheet.")
            return False, ""  # Placeholder does not exist

    def extract_accent_color_value(self) -> str:
        # Extract the value of @accent-color from the stylesheet.
        # Handles both commented and uncommented definitions.
        # As default we store accent color place holder in a separate line of qss file
        # and comment it by:
        #  /* @accent-color: #0078d7;  Define the accent color placeholder */

        # Use a regular expression to find the value of @accent-color
        # This regex handles both commented and uncommented lines
        match = re.search(r"/\*\s*" + self.accent_color_template + r":\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\s*;\s*\*/|"
                  + self.accent_color_template + r":\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\s*;", self.stylesheet)
        
        if match:
            # Return the first non-None group (either from the commented or uncommented match)
            return next(group for group in match.groups() if group is not None)
        else:
            return ""  # Return an empty string if no match is found

    def replace_placeholder(self, accent_color: str) -> str:
        # 
        # Preprocess the stylesheet by replacing placeholders with actual values.
        # 
        # Replace @accent-color with the provided accent color
        self.stylesheet = self.stylesheet.replace(self.accent_color_template, accent_color)
    
    def validate(self) -> bool:
        """
        Validate the class member stylesheet for common syntax errors.
        
        Returns:
            bool: True if the stylesheet is valid, False otherwise.
        """
        return self.validate_stylesheet(self.stylesheet)
    
    @staticmethod
    def validate_stylesheet(stylesheet) -> bool:
        """
        Validate the given stylesheet for common syntax errors.
    
        Returns:
            bool: True if the stylesheet is valid, False otherwise.
        """
        if stylesheet is None:
            logger.warning("No stylesheet loaded.")
            return False

        # Check for unclosed curly braces
        if stylesheet.count('{') != stylesheet.count('}'):
            logger.error("Stylesheet has unmatched curly braces.")
            return False
    
        # Remove comments and the accent color placeholder to avoid false positives during validation
        cleaned_stylesheet = re.sub(r'/\*.*?\*/', '', stylesheet, flags=re.DOTALL)
        cleaned_stylesheet = cleaned_stylesheet.replace('@accent-color', '#0078d7')  # Temporary replacement

        # Check for missing semicolons within style definitions
        patterns = re.findall(r'{[^}]*}', cleaned_stylesheet)
        for pattern in patterns:
            properties = re.findall(r'[^;\s][^;]*;', pattern.strip('{}'))
            if len(properties) == 0:
                logger.error("Stylesheet has missing semicolon(s) in the property: %s", pattern.strip('{}'))
                return False

        # Check for invalid property names or values (basic check)
        invalid_chars = re.findall(r'[^\w\s:\-;#.%{}(),@""]', cleaned_stylesheet)
        if invalid_chars:
            logger.error("Stylesheet contains invalid characters: %s", ''.join(invalid_chars))
            return False

        logger.info("Stylesheet is valid.")
        return True

    def saveas_stylesheet(self,qss_file:str=''):
        
        if os.path.exists(qss_file):
            with open(qss_file, "w", encoding="utf-8") as file:
                file.write(self.stylesheet)
                file.close()
                logger.info(f"Stylesheet saved to {qss_file}")
        else:
            logger.error(f"Failed to save stylesheet file: {qss_file}")
    
    def save_stylesheet(self):
        # Save the updated stylesheet back to the file.
        if os.path.exists(self.qss_file):
             with open(self.qss_file, "w", encoding="utf-8") as file:
                file.write(self.stylesheet)
                file.close()
                logger.info(f"Stylesheet saved to {self.qss_file}")
        else:
            logger.error(f"Failed to save stylesheet to {self.qss_file}")

################################################################################################################
##########   CUSTOMIZED STYLES TO APPLY IN CUSTOM PLACES   #####################################################
################################################################################################################


mini_button_stylesheet = """
            QPushButton 
            {
            font-family:Segoe Fluent Icons;
            font-size:16px;
            color: white;
            padding: 2px;
            text-align: center;
            max-width:40;
            max-height:40;
            width:30;
            height:30;
            }
            QPushButton:hover
            {
                background-color:rgb(28, 26, 26);
            }
            """
mini_Toolbutton_stylesheet = """
            QToolButton {
            font-family:Segoe Fluent Icons;
            color: white;
            padding: 2px;
            text-align: center;
            max-width:40;
            width:28;
            height:28;
            margin:0px 5px 0px 0px;
            }
            QPushButton:hover
            {
                background-color:rgb(28, 26, 26);
            }
            """

menu_button_style ='''
QPushButton 
{
    background-color:  transparent; 
    border: none; /* Bright blue border */ 
    border-radius: none; 
    padding: 5px 10px;
    text-align: left;
}
QPushButton:hover
{
    background-color: @accent-color; 
}

QPushButton:pressed 
{
    background-color: green;
}

QPushButton:disabled 
{
    background-color: transparent; /* Dark blue-gray */
    border: none;                  /* Bright blue    */
    color: #777777;                /* Gray text      */
}
'''