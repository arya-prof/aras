"""
Setup script for Aras Agent.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="aras-agent",
    version="0.1.0",
    author="Aras Agent",
    author_email="aras@example.com",
    description="A modular AI agent with Qt UI for smart home and system control",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/aras-agent",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Home Automation",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "aras=aras.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "aras": ["*.json", "*.yaml", "*.yml"],
    },
)
