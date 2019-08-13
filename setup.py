__version__ = "0.0.9"

import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='pptop',
    version=__version__,
    author='Altertech Group',
    author_email='div@altertech.com',
    description='Python profiler/analyzer',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/alttch/pptop',
    packages=setuptools.find_packages(),
    data_files=[
        ('pptop/config', ['pptop/config/pptop.yml']),
        ('pptop/config/scripts', ['pptop/config/scripts/hello.py']),
        ('pptop/config/scripts', ['pptop/config/scripts/test1.py']),
    ],
    license='MIT',
    scripts=['bin/pptop'],
    install_requires=['psutil', 'tabulate', 'atasker', 'pyyaml', 'yappi'],
    classifiers=('Programming Language :: Python :: 3',
                 'License :: OSI Approved :: MIT License',
                 'Topic :: Software Development :: Debuggers',
                 'Topic :: Software Development :: Testing'),
)
