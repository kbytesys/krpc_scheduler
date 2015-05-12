from setuptools import setup
import sys

setup(
    name='krpc_scheduler',
    version='0.0.1',
    author='kbyte',
    author_email='kbytesys@users.noreply.github.com',
    packages=['kbyte.krpc'],
    url='https://github.com/kbytesys/krpc',
    license='GNU GPL v3',
    description='Simple scheduler library for kRPC (Kerbal Remote Procedure Call)',
    install_requires=['krpc >= 0.1.8'],
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
