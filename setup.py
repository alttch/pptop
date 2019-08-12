__version__ = "0.0.4"

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
    license='MIT',
    scripts = 'bin/pptop',
    install_requires=['psutil', 'tabulate', 'atasker', 'pyyaml', 'yappi'],
    classifiers=('Programming Language :: Python :: 3',
                 'License :: OSI Approved :: MIT License',
                 'Topic :: Software Development :: Debuggers',
                 'Topic :: Software Development :: Testing'),
)
