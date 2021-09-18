import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="kabuki",
    version="0.0.1",
    author="Benjamin Black",
    author_email="benblack769@gmail.com",
    description="Automated minimal-setup ssh based job scheduling designed for ML",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/benblack769/kabuki",
    keywords=["Machine Learning", "Job Scheduling"],
    packages=setuptools.find_packages(),
    install_requires=[],
    python_requires='>=3.6',
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    scripts=['bin/execute_batch', 'bin/execute_remote', 'bin/execute_on'],
    include_package_data=True,
)
