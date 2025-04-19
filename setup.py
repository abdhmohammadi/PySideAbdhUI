from setuptools import setup, find_packages

setup(
    name="PySideAbdhUI",
    version="0.1.0",
    author="Abdullah Mohammadi",
    author_email="abdhmohammady@gmaile.com",
    description="Customized Python GUI components based on PySide6",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/abdhmohammadi/PySideAbdhUI",
    packages=find_packages(),
    include_package_data=True,  # ensure MANIFEST.in is used
    package_data={
        # Include all SVG and QSS files in the resources subdirectories.
        "PySideAbdhUI": [
            "resources/icons/svg/*.svg",
            "resources/styles/*.qss",
        ],
    },
    install_requires=[
        "PySide6",  # add any additional dependencies as needed
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Microsoft :: Windows",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.13",
)
