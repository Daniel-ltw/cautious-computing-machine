"""
Setup script for the mud_agent package.
"""

from setuptools import find_packages, setup

setup(
    name="mud_agent",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "smolagents>=0.1.0",
        "telnetlib3>=1.0.4",
        "asyncio>=3.4.3",
        "python-dotenv>=1.0.0",
        "colorama>=0.4.6",
        "aiofiles>=23.2.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "ruff>=0.1.0",
        ],
    },
    python_requires=">=3.8",
    description="An intelligent agent for playing MUD games with MCP integration",
    author="Daniel",
    author_email="example@example.com",
    url="https://github.com/yourusername/mud_agent",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
