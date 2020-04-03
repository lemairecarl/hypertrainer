from setuptools import find_packages, setup

setup(
    name='hypertrainer',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'pytest',
        'numpy',
        'bokeh==2.0.1',
        'flask>=1.0.0',
        'ruamel.yaml',
        'peewee',
        'pandas',
        'rq',
        'IPython',
        'termcolor',
        'tabulate'
    ],
)
