from distutils.core import setup
from distutils.sysconfig import get_python_lib
import datetime

with open("csbuild/version", "r") as f:
      csbuild_version = f.read().strip()

setup(name='csbuild',
      version=csbuild_version,
      #py_modules=['csbuild'],
      packages=["csbuild"],
      package_data={"csbuild":["version", "*.py", "*/*.py", "*/*/*.py"]},
      author="Jaedyn K. Draper",
      author_email="jaedyn.pypi@jaedyn.co",
      url="https://github.com/3Jade/csbuild",
      description="C/C++ build tool",
      long_description="""CSBuild is a C/C++-oriented cross-platform build and project generation system written in Python. CSBuild attempts to address a number of issues with existing build systems, including performance, maintainability, and usability. CSBuild focuses on providing an easy, understandable, readable syntax for defining a build structure, and then providing your builds to you in the shortest possible amount of time.""",
      classifiers=[
         "Development Status :: 4 - Beta",
         "Environment :: Console",
         "Intended Audience :: Developers",
         "License :: OSI Approved :: MIT License",
         "Natural Language :: English",
         "Operating System :: Microsoft :: Windows",
         "Operating System :: MacOS :: MacOS X",
         "Operating System :: POSIX :: Linux",
         "Programming Language :: C",
         "Programming Language :: C++",
         "Programming Language :: Objective C",
         "Programming Language :: Python :: 2.7",
         "Programming Language :: Python :: 3.3",
         "Programming Language :: Python :: 3.4",
         "Programming Language :: Python :: 3.5",
         "Topic :: Software Development :: Build Tools"
      ]
      )
