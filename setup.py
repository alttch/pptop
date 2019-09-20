__version__ = '0.5.13'

import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

pptop_injector = setuptools.Extension('__pptop_injector',
                                      sources=['src/__pptop_injector.c'])

setuptools.setup(
    name='pptop',
    version=__version__,
    author='Altertech',
    author_email='div@altertech.com',
    description='Open, extensible Python injector/profiler/analyzer',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://pptop.io/',
    packages=setuptools.find_packages(),
    license='MIT',
    scripts=['bin/pptop'],
    include_package_data=True,
    ext_modules=[pptop_injector],
    install_requires=[
        'wheel', 'unipath', 'psutil', 'rapidtables', 'atasker>=0.3.28',
        'pyyaml', 'yappi', 'neotermcolor', 'pygments'
    ],
    classifiers=('Programming Language :: Python :: 3',
                 'License :: OSI Approved :: MIT License',
                 'Topic :: Software Development :: Debuggers',
                 'Topic :: Software Development :: Testing'),
)
