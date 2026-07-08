from setuptools import setup
from glob import glob
import os

package_name = 'tongue_diagnosis'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'bin'), glob('bin/*.bin')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kunp',
    maintainer_email='1709038900@qq.com',
    description='Tongue diagnosis inference node for RDK X5',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'tongue_diagnosis_node = tongue_diagnosis.tongue_diagnosis_node:main',
        ],
    },
)
