"""LoopGrid Python SDK - Setup for PyPI"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="loopgrid",
    version="0.1.0",
    author="Cybertechsoft",
    author_email="hello@loopgrid.dev",
    description="Control plane for AI decision reliability",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cybertechsoft/loopgrid",
    project_urls={
        "Bug Tracker": "https://github.com/cybertechsoft/loopgrid/issues",
        "Documentation": "https://github.com/cybertechsoft/loopgrid#readme",
        "Source Code": "https://github.com/cybertechsoft/loopgrid",
    },
    package_dir={"": "sdk/python"},
    packages=find_packages(where="sdk/python"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="ai, llm, decisions, replay, compliance, eu-ai-act, infrastructure",
    python_requires=">=3.8",
    install_requires=["requests>=2.25.0"],
    extras_require={
        "llm": ["openai>=1.0.0", "anthropic>=0.18.0"],
        "dev": ["pytest>=7.0.0", "pytest-cov>=4.0.0", "black>=23.0.0", "httpx>=0.24.0"],
    },
)
