##CSB

CSBuild is a python makefile program that's written to be both efficient and easy to use. Unlike GNU make, the syntax for CSB is very simple and easy to approach, while still being powerful. No deep understanding of g++'s hundreds of flags is required.

Additionally, CSB is designed to prevent doing more work than necessary whenever possible. Rather than specifying every file you want to compile, you specify files and directories you DON'T want to compile, so adding a new file to your project is as easy as creating it. And when compiling, CSB checks the header files in each of your source files, recompiling every necessary source file when an included header changes, but leaving alone the files that the header can't affect. Further, it keeps md5 records of source and header files within the project, so that it doesn't recompile files if the modified date has changed but the contents haven't.

CSB is also intelligently multi-threaded and will use threads for compilation to enable maximum efficiency based on the hardware of your machine.

One very big advantage imparted by CSB is the *intelligent* use of the "Unity Build" concept, in an implementation I call "chunked build." With chunked builds, the project is divided into larger compilation units, created by joining multiple source files into a single file. This speeds up compilation considerably when doing full builds; however, where unity builds often fail is in iterative programming involving multiple sequential small changes to few files, in which case unity builds often end up building far more than is necessary.

To avoid this issue, CSB takes a sequential approach to building. When doing a full build, CSB uses the unity approach, combining small compilation units into larger ones to increase the build time. However, when doing incremental builds, CSB takes advantage of small builds to split these larger units back down into their base components. When a build only consists of a small number of files, CSB will discard the chunk those files are in if it exists, and compile them as individual files - then the next time any file in that chunk is compiled, only it will be compiled, rather than the entire chunk. The end result is a build that starts out with the unity approach, and gradually shifts back to a more traditional approach over time. (However, any time you need to build a sufficiently large number of files in a chunk, CSB will return to building the whole chunk - so when working with header files, or when changing many files at once, you may find that the build shifts back and forth between chunks and individual files to try and keep all builds to the minimum possible time.)

Finally, CSB combines "./configure" and "make" into one call, checking dependencies as part of its build process and alerting at the very start of the build if it can't find a required library, rather than waiting until the linker is invoked to alert of this.

##Contents

[Usage](#usage) 

[Default command line arguments](#default-command-line-arguments) 

[Adding targets](#adding-targets) 

[Parsing command line arguments](#parsing-command-line-targets)

[The options](#the-options)

[Example script](#example-script)

##Usage

Using CSB is easy: simply make a script in the top directory of your project named "make.py" (or any other name you'd like to use). Inside the script, you can set various options to control the build.

Because the build script is written in python, there's no limit to how you can control your build.

When you run CSB, it will automatically scan your current directory and all subdirectories for files to compile, following the philosophy that the files you DO want to compile are usually the norm, and the files you DON'T tend to be the exception - thus you should only need to specify the exceptions, not the full list of files in your project. It will also scan your computer for any required libraries (dictated by the make script) and will scan each c or cpp file for included headers. It then uses the information collected from this to intelligently determine which files need to be recompiled and which files don't - unlike other systems, which require you to specify what files to recompile when headers are changed, and often end up recompiling entire projects when you change a header used in only one source file, or do not detect at all that external headers or libraries have been modified.

Once CSB starts building your project, it will also intelligently determine the optimal number of threads to use for your hardware to minimize build time.

The result is that CSB creates a quick and efficient build environment that maximized turnaround and iteration time for your project.

##Default command line arguments

By default, CSB supports the following targets with the following default targets:

"debug": Debug level 3, optimization level 0, object directory ./Debug/obj, output file directory ./Debug
"release": Debug level 0, optimization level 3, object directory ./Release/obj, output file directory ./Release

Additionally, the following switches can be used by default to impact the behavior of the build:

python make.py --clean <target>: Deletes all generated files for the target build
python make.py --install <target>: Install the target build. (This does nothing unless the make script has used one or both of InstallOutput() or InstallHeaders())
python make.py -v <target>: Print extra information during processing (verbose)
python make.py -q <target>: Print less information - only prints WARN and ERROR log levels (quiet)
python make.py -qq <target>: Print no information - this option will only print output from the compiler (very quiet)
python make.py <target> --overrides="list;of;python;calls": The string passed to --overrides will be executed as python code, enabling the user to override any settings in the make script. For example, to customize the install directory, one method would be to use --overrides="InstallOutput('/path/to/output')"
python make.py -H
python make.py --makefile_help: Prints help information for the specific makefile script you are using (if any)
python make.py -h
python make.py --help: Print help information for the CSB system

##Adding targets

To add a target to your build, simply create a function with the name of your target (in all lower case - a capitalized target name won't work). For example, if you want to add a target named "all," simply create a function named "all" with your desired configuration in it.

##Parsing command line arguments

You can parse command line arguments in your script using the python argparse module, with one notable change to its functionality: because CSB parses some arguments itself, you need to pass the value "csbuild.args" to your parse_args function. I.e.:

##The options

To control the build, use the following options:

####csbuild.InstallOutput( s = "/usr/local/lib" )
Enables installation of the compiled output file. Default target is /usr/local/lib.

####csbuild.InstallHeaders( s = "/usr/local/include" )
Enables installation of the project's headers. Default target is /usr/local/include.

####csbuild.ExcludeDirs( *args )
Excludes the given subdirectories from the build. Accepts multiple string arguments.

####csbuild.ExcludeFiles( *args )
Excludes the given files from the build. Accepts multiple string arguments.

####csbuild.Libraries( *args )
List of libraries to link against. Multiple string arguments. gcc/g++ -l.

####csbuild.IncludeDirs( *args )
List of directories to search for included headers. Multiple string arguments. gcc/g++ -I
By default, this list contains /usr/include and /usr/local/include.
Using this function will add to the existing list, not replace it.

####csbuild.LibDirs( *args )
List of directories to search for libraries. Multiple string arguments. gcc/g++ -L 
By default, this list contains /usr/lib and /usr/local/lib
Using this function will add to the existing list, not replace it

####csbuild.ClearLibraries( )
Clears the list of libraries

####csbuild.ClearIncludeDirs( )
Clears the include directories, including the defaults.

####csbuild.ClearLibDirs( )
Clears the library directories, including the defaults

####csbuild.Opt(i)
Sets the optimization level. gcc/g++ -O

####csbuild.Debug(i)
Sets the debug level. gcc/g++ -g

####csbuild.Define( *args )
Sets defines for the project. Accepts multiple arguments. gcc/g++ -D

####csbuild.ClearDefines( *args )
clears the list of defines

####csbuild.Undefine( *args )
Sets undefines for the project. Multiple arguments. gcc/g++ -U

####csbuild.ClearUndefines( )
clears the list of undefines

####csbuild.Compiler(s)
Sets the compiler to use for the project. Default is g++.

####csbuild.Output(s)
Sets the output file for the project. If unset, the project will be compiled as "JMade"

####csbuild.OutDir(s)
Sets the directory to place the compiled result

####csbuild.ObjDir(s)
Sets the directory to place pre-link objects

####csbuild.WarnFlags( *args )
Sets warn flags for the project. Multiple arguments. gcc/g++ -W

####csbuild.ClearWarnFlags( )
Clears the list of warning flags

####csbuild.Flags( *args )
Sets miscellaneous flags for the project. Multiple arguments. gcc/g++ -f

####csbuild.ClearFlags( )
Clears the list of misc flags

####csbuild.DisableAutoMake()
Disables the automatic build of the project at conclusion of the script
If you turn this off, you will need to explicitly call either make() to build and link,
or build() and link() to take each step individually

####csbuild.EnableAutoMake()
Turns the automatic build back on after disabling it

####csbuild.Shared()
Builds the project as a shared library. Enables -shared in the linker and -fPIC in the compiler.

####csbuild.NotShared()
Turns shared object mode back off after it was enabled.

####csbuild.Profile()
Enables profiling optimizations. gcc/g++ -pg

####csbuild.Unprofile()
Turns profiling back off.

####csbuild.ExtraFlags(s)
Literal string of extra flags to be passed directly to the compiler

####csbuild.ClearExtraFlags()
Clears the extra flags string

####csbuild.Standard(s)
The C/C++ standard to be used when compiling. gcc/g++ --std

####csbuild.DisableChunkedBuild()
Turn off the chunked/unity build system and build using individual files.

####csbuild.EnableChunkedBuild()
Turn chunked/unity build on and build using larger compilation units. This is the default.

####csbuild.ChunkSize(i)
Set the size of the chunks used in the chunked build. This indicates the number of files per compilation unit.

####csbuild.ChunkTolerance(i)
Set the number of files above which the files will be built as a chunk.
For example, if you set this to 3 (the default), then a chunk will be built as a chunk
if more than three of its files need to be built; if three or less need to be built, they will
be built individually to save build time.

####csbuild.SetChunks(*chunks)
Explicitly set the chunks used as compilation units.
This accepts multiple arguments, each of which should be a list of files.
Each list is one chunk.
NOTE that setting this will disable the automatic file gathering, so any files you have

####csbuild.ClearChunks()
Clears the explicitly set list of chunks and returns the behavior to the default.

####csbuild.HeaderRecursionLevel(i):
Sets the depth to search for header files. If set to 0, it will search with unlimited recursion to find included
headers. Otherwise, it will travel to a depth of i to check headers. If set to 1, this will only check first-level
headers and not check headers included in other headers; if set to 2, this will check headers included in headers,
but not headers included by *those* headers; etc.

This is very useful if you're using a large library (such as boost) or a very large project and are experiencing
long waits prior to compilation.

####csbuild.IgnoreExternalHeaders()
If this option is set, external headers will not be checked or followed when building. Only headers within the
base project's directory and its subdirectories will be checked. This will speed up header checking, but if you
modify any external headers, you will need to manually --clean the project.

####csbuild.DisableWarnings()
Disables ALL warnings, including gcc/g++'s built-in warnings.

####csbuild.DefaultTarget(s)
Sets the default target if none is specified. The default value for this is release.

######A note...
Options that correlate to gcc/g++ flags do NOT need the flag passed with them. For example, if you're linking (i.e.) to the boost_thread library, you would simply call:

csbuild.Libraries("boost_thread")

##Example script

This script is used to compile the htt++ project, for which CSB was initially developed:

```python
#!/usr/bin/python

import csbuild

#Project's required libraries
csbuild.Libraries(
   "jnet",
   "jformat",
   "jhash",
   "boost_thread"
)

#Output file
csbuild.Output("libhttpp.so")

#htt++ uses c++11, so we need to specify the standard
csbuild.Standard("gnu++0x")

#htt++'s use of c++11 necessitates g++-4.7 or higher, so we need to specify that as well
csbuild.Compiler("g++-4.7")

#Compile as a shared library
csbuild.Shared()

#Let's be extra strict on the warning flags.
csbuild.WarnFlags("all", "extra", "ctor-dtor-privacy", "old-style-cast", "overloaded-virtual", "init-self", "missing-include-dirs", "switch-default", "switch-enum", "undef")

#And set our project to install both the output file and the headers
csbuild.InstallHeaders()
csbuild.InstallOutput()
```
