from setuptools import setup, find_packages

setup(
    name='krpc_scheduler',
    version='0.0.2',
    author='Andrea Briganti',
    author_email='kbytesys@gmail.com',
    namespace_packages=['kbyte'],
    packages=find_packages(exclude=['docs', 'samples', 'tests']),
    url='https://github.com/kbytesys/krpc',
    license='GNU GPL v3',
    keywords=['kerbal', 'krpc'],
    description='Simple scheduler library for kRPC (Kerbal Remote Procedure Call)',
    install_requires=['krpc >= 0.3.0'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: Unix',
        'Topic :: Communications',
        'Topic :: Games/Entertainment :: Simulation',
        'Topic :: Internet'
    ],
)
