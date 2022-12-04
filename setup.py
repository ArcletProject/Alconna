from setuptools import find_namespace_packages, setup

with open("README.rst", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name="arclet-alconna",
    version="1.4.2.1",
    author="RF-Tar-Railt",
    author_email="rf_tar_railt@qq.com",
    description="A High-performance, Generality, Humane Command Line Arguments Parser Library.",
    license='MIT',
    long_description=long_description,
    long_description_content_type="text/rst",
    url="https://github.com/ArcletProject/Alconna",
    package_dir={"": "src"},
    packages=find_namespace_packages(where="src"),
    install_requires=["typing-extensions>=4.4,<4.6", "nepattern>=0.3.2"],
    extras_require={
        'graia': [
            'arclet-alconna-graia',
        ],
        'cli': [
            'arclet-alconna-cli'
        ],
        'full': [
            'arclet-alconna-cli', 'arclet-alconna-graia'
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    keywords=['command', 'argparse', 'fast', 'alconna', 'cli', 'parsing', 'optparse', 'command-line', 'parser'],
    python_requires='>=3.8',
    project_urls={
        'Documentation': 'https://arcletproject.github.io/docs/alconna/tutorial',
        'Bug Reports': 'https://github.com/ArcletProject/Alconna/issues',
        'Source': 'https://github.com/ArcletProject/Alconna',
    },
)
