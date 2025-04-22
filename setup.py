from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="batchscan",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool for batch scanning and analyzing images using AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/batchscan",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "accelerate",
        "pillow",
        "requests",
        "torch",
        "transformers",
        "flask",
        "flask-socketio",
        "python-dotenv",
    ],
    entry_points={
        "console_scripts": [
            "batchscan=batchscan.__main__:main",
        ],
    },
)