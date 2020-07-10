import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="flux-accounting",
    version="0.1.0",
    author="Christopher Moussa",
    author_email="moussa1@llnl.gov",
    description="User accounting interface for Flux framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/flux-framework/flux-accounting",
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': [
            'flux-account.py = accounting.accounting_cli:main',
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Lesser General Public License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires='>=3.6',
)
