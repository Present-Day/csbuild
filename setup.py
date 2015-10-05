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
      url="https://github.com/ShadauxCat/csbuild",
      description="C/C++ build tool",
      long_description="""CSB (pronounced "cusp") is a python makefile program that's written to be both efficient and easy to use. Unlike GNU make, the syntax for csbuild is very simple and easy to approach, while still being powerful. No deep understanding of g++'s hundreds of flags is required.

Additionally, CSB is designed to prevent doing more work than necessary whenever possible. Rather than specifying every file you want to compile, you specify files and directories you DON'T want to compile, so adding a new file to your project is as easy as creating it. And when compiling, CSB checks the header files in each of your source files, recompiling every necessary source file when an included header changes, but leaving alone the files that the header can't affect. Further, it keeps md5 records of source and header files within the project, so that it doesn't recompile files if the modified date has changed but the contents haven't.

CSB is also intelligently multi-threaded and will use threads for compilation to enable maximum efficiency based on the hardware of your machine.

One very big advantage imparted by CSB is the intelligent use of the "Unity Build" concept, in an implementation I call "chunked build." With chunked builds, the project is divided into larger compilation units, created by joining multiple source files into a single file. This speeds up compilation considerably when doing full builds; however, where unity builds often fail is in iterative programming involving multiple sequential small changes to few files, in which case unity builds often end up building far more than is necessary.

To avoid this issue, CSB takes a sequential approach to building. When doing a full build, CSB uses the unity approach, combining small compilation units into larger ones to increase the build time. However, when doing incremental builds, CSB takes advantage of small builds to split these larger units back down into their base components. When a build only consists of a small number of files, CSB will discard the chunk those files are in if it exists, and compile them as individual files - then the next time any file in that chunk is compiled, only it will be compiled, rather than the entire chunk. The end result is a build that starts out with the unity approach, and gradually shifts back to a more traditional approach over time. (However, any time you need to build a sufficiently large number of files in a chunk, CSB will return to building the whole chunk - so when working with header files, or when changing many files at once, you may find that the build shifts back and forth between chunks and individual files to try and keep all builds to the minimum possible time.)

Finally, CSB combines "./configure" and "make" into one call, checking dependencies as part of its build process and alerting at the very start of the build if it can't find a required library, rather than waiting until the linker is invoked to alert of this.""",
      classifiers=[
         "Development Status :: 4 - Beta",
         "Environment :: Console",
         "Intended Audience :: Developers",
         "License :: OSI Approved :: MIT License",
         "Natural Language :: English",
         "Operating System :: POSIX :: Linux",
         "Programming Language :: C",
         "Programming Language :: C++",
         "Programming Language :: Python :: 2.7",
         "Programming Language :: Python :: 3.2",
         "Programming Language :: Python :: 3.3",
         "Topic :: Software Development :: Build Tools"
      ]
      )
