import setuptools

with open("README.rst", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name="arclet-alconna",
    version="0.9.3.4",
    author="ArcletProject",
    author_email="rf_tar_railt@qq.com",
    description="A Fast Command Analyser based on Dict",
    license='MIT',
    long_description=long_description,
    long_description_content_type="text/rst",
    url="https://github.com/ArcletProject/Alconna",
    package_dir={"": "src"},
    packages=setuptools.find_namespace_packages(where="src"),
    entry_points={
        'console_scripts': [
            'alconna = arclet.alconna.__main__:main'
        ]
    },
    extras_require={
        'graia': [
            'arclet-alconna-graia',
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    keywords=['command', 'argparse', 'dict', 'fast', 'alconna', 'cli', 'parsing', 'optparse'],
    python_requires='>=3.8',
    project_urls={
        'Documentation': 'https://arcletproject.github.io/docs/alconna/tutorial',
        'Bug Reports': 'https://github.com/ArcletProject/Alconna/issues',
        'Source': 'https://github.com/ArcletProject/Alconna',
    },
)
