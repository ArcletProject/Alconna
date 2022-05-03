import setuptools

setuptools.setup(
    name="arclet-alconna-graia",
    url="https://github.com/ArcletProject/Alconna/blob/master/arclet/alconna/graia",
    version="0.0.10.2",
    author="ArcletProject",
    author_email="rf_tar_railt@qq.com",
    description="Support Alconna to GraiaProject",
    license='AGPL-3.0',
    packages=['arclet.alconna.graia'],
    install_requires=['graia-ariadne', 'graia-broadcast', 'arclet-alconna'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
    ],
    keywords=['alconna', 'graia', 'dispatcher', 'arclet'],
    python_requires='>=3.8',
    project_urls={
        'Documentation': 'https://arcletproject.github.io/docs/alconna/tutorial',
        'Bug Reports': 'https://github.com/ArcletProject/Alconna/issues',
        'Source': 'https://github.com/ArcletProject/Alconna',
    },
)
