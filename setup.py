"""It is a tool for capturing images from a panoramatic IP camera. Images are captured during
 daylight period in a fixed interval of typically 10 seconds. Every image is pre-processed (masked)
 and uploaded to server.

See:
https://github.com/UCEEB/Sky-Imager-Aggregator
"""

from setuptools import setup, find_packages
from os import path


here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    description = f.read()


setup(
    name='SkyImagerAggregator',
    version='1.0.0',
    description='It is a software for capturing images from a panoramic IP camera',
    long_description=description,
    long_description_content_type='text/markdown',
    url='https://github.com/UCEEB/Sky-Imager-Aggregator',
    author='UCEEB, Czech Technical University',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=['requests', 'opencv-python', 'numpy', 'astral'],
)
