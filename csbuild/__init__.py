# Copyright (C) 2013 Jaedyn K. Draper
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
.. module:: CSBuild
	:synopsis: cross-platform c/c++ build system

.. moduleauthor:: Jaedyn K. Draper, Brandon M. Bare
.. attention:: To support CSBuild's operation, Python's import lock is DISABLED once CSBuild has started.
This should not be a problem for most makefiles, but if you do any threading within your makefile, take note:
anything that's imported and used by those threads should always be implemented on the main thread before that
thread's execution starts. Otherwise, CSBuild does not guarantee that the import will have completed
once that thread tries to use it. Long story short: Don't import modules within threads.
"""

import argparse
import glob
import shlex
import shutil
import signal
import math
import subprocess
import os
import sys
import threading
import time
import platform
import imp
import re
import traceback

if sys.version_info < (3,0):
	import cPickle as pickle
else:
	import pickle

class ProjectType( object ):
	"""
	Specifies the type of project to compile
	"""
	Application = 0
	SharedLibrary = 1
	StaticLibrary = 2

class DebugLevel( object ):
	Disabled = 0
	EmbeddedSymbols = 1
	ExternalSymbols = 2
	ExternalSymbolsPlus = 3

class OptimizationLevel( object ):
	Disabled = 0
	Size = 1
	Speed = 2
	Max = 3

class ScopeDef( object ):
	Self = 1
	Intermediate = 2
	Final = 4

	DependentsOnly = Intermediate | Final
	All = Self | Intermediate | Final

class StaticLinkMode( object ):
	LinkLibs = 0
	LinkIntermediateObjects = 1

from . import _utils
from . import toolchain
from . import toolchain_msvc
from . import toolchain_gcc
from . import toolchain_android
from . import toolchain_ios
from . import log
from . import _shared_globals
from . import projectSettings
from . import project_generator_qtcreator
from . import project_generator_slickedit
from . import project_generator_visual_studio
from . import project_generator


__author__ = "Jaedyn K. Draper, Brandon M. Bare"
__copyright__ = 'Copyright (C) 2012-2014 Jaedyn K. Draper'
__credits__ = ["Jaedyn K. Draper", "Brandon M. Bare", "Jeff Grills", "Randy Culley"]
__license__ = 'MIT'

__maintainer__ = "Jaedyn K. Draper"
__email__ = "jaedyn.csbuild-contact@jaedyn.co"
__status__ = "Development"


with open( os.path.dirname( __file__ ) + "/version", "r" ) as f:
	__version__ = f.read( )

signal.signal( signal.SIGINT, signal.SIG_DFL )


def NoBuiltInTargets( ):
	"""
	Disable the built-in "debug" and "release" targets.
	"""
	if SetupDebugTarget in projectSettings.currentProject.targets["debug"]:
		arr = projectSettings.currentProject.targets["debug"]
		del arr[arr.index( SetupDebugTarget )]
	if SetupReleaseTarget in projectSettings.currentProject.targets["release"]:
		arr = projectSettings.currentProject.targets["release"]
		del arr[arr.index( SetupReleaseTarget )]


def EnableOutputInstall( ):
	"""
	Enables installation of the compiled output file.
	The default installation directory is /usr/local/lib.
	"""
	projectSettings.currentProject.SetValue("installOutput", True)


def EnableHeaderInstall( ):
	"""
	Enables installation of the project's headers.
	Default target is /usr/local/include, unless the --prefix option is specified.
	If --prefix is specified, the target will be *{prefix*}/include
	"""
	projectSettings.currentProject.SetValue("installHeaders", True)


def SetHeaderInstallSubdirectory( s ):
	"""
	Specifies a subdirectory of *{prefix*}/include in which to install the headers.

	:type s: str
	:param s: The desired subdirectory; i.e., if you specify this as "myLib", the headers will be
	installed under *{prefix*}/include/myLib.
	"""
	projectSettings.currentProject.SetValue("headerInstallSubdir", s)


def AddExcludeDirectories( *args ):
	"""
	Exclude the given directories from the project. This may be called multiple times to add additional excludes.
	Directories are relative to the location of the script itself, not the specified project working directory.

	:type args: an arbitrary number of strings
	:param args: The list of directories to be excluded.
	"""
	args = list( args )
	newargs = []
	for arg in args:
		if arg[0] != '/' and not arg.startswith( "./" ):
			arg = "./" + arg
		newargs.append( os.path.abspath( arg ) )
	projectSettings.currentProject.ExtendList("excludeDirs", newargs)


def AddExcludeFiles( *args ):
	"""
	Exclude the given files from the project. This may be called multiple times to add additional excludes.
	Files are relative to the location of the script itself, not the specified project working directory.

	:type args: an arbitrary number of strings
	:param args: The list of files to be excluded.
	"""
	args = list( args )
	newargs = []
	for arg in args:
		if arg[0] != '/' and not arg.startswith( "./" ):
			arg = "./" + arg
		newargs.append( os.path.abspath( arg ) )
	projectSettings.currentProject.ExtendList("excludeFiles", newargs)


def AddLibraries( *args ):
	"""
	When linking the project, link in the given libraries. This may be called multiple times to add additional libraries.

	In the gcc toolchain, these will all be prefixed with "lib" when looking for the file to link. I.e.,
	csbuild.Libraries("MyLib") will link libMyLib.so or libMyLib.a.

	For compatibility, the msvc toolchain will search for the library exactly as specified, and if it can't find it,
	will then search for it with the lib prefix. I.e., csbuild.Libraries("MyLib") will first search for MyLib.lib,
	and if that isn't found, will then search for libMyLib.lib.

	:type args: an arbitrary number of strings
	:param args: The list of libraries to link in.
	"""
	projectSettings.currentProject.UnionSet("libraries", set( args ))


def AddStaticLibraries( *args ):
	"""
	Similar to csbuild.Libraries, but forces these libraries to be linked statically.

	:type args: an arbitrary number of strings
	:param args: The list of libraries to link in.
	"""
	projectSettings.currentProject.UnionSet("staticLibraries", set( args ))


def AddSharedLibraries( *args ):
	"""
	Similar to csbuild.Libraries, but forces these libraries to be linked dynamically.

	:type args: an arbitrary number of strings
	:param args: The list of libraries to link in.
	"""
	projectSettings.currentProject.UnionSet("sharedLibraries", set( args ))


def AddFrameworks( *args ):
	"""
	Add frameworks for Objective-C/C++ compilations.

	:type args: an arbitrary number of strings
	:param args: The list of libraries to link in.
	"""
	projectSettings.currentProject.UnionSet("frameworks", set( args ))


def AddIncludeDirectories( *args ):
	"""
	Search the given directories for include headers. This may be called multiple times to add additional directories.
	Directories are relative to the location of the script itself, not the specified project working directory.

	In the gcc toolchain, /usr/include and /usr/local/include (or the platform appropriate equivalents) will always
	be appended to the end of this list.

	:type args: an arbitrary number of strings
	:param args: The list of directories to be searched.
	"""
	for arg in args:
		arg = os.path.abspath( arg )
		projectSettings.currentProject.AppendList("includeDirs",  arg )


def AddLibraryDirectories( *args ):
	"""
	Search the given directories for libraries to link. This may be called multiple times to add additional directories.
	Directories are relative to the location of the script itself, not the specified project working directory.

	In the gcc toolchain, /usr/lib and /usr/local/lib (or the platform appropriate equivalents) will always
	be appended to the end of this list.

	:type args: an arbitrary number of strings
	:param args: The list of directories to be searched.
	"""
	for arg in args:
		arg = os.path.abspath( arg )
		projectSettings.currentProject.AppendList("libraryDirs",  arg )


def AddFrameworkDirectories( *args ):
	"""
	Search the given directories for framworks to link. This may be called multiple times to add additional directories.
	Directories are relative to the location of the script itself, not the specified project working directory.

	:type args: an arbitrary number of strings
	:param args: The list of directories to be searched.
	"""
	for arg in args:
		arg = os.path.abspath( arg )
		projectSettings.currentProject.AddToSet("frameworkDirs",  arg )


def ClearLibraries( ):
	"""Clears the list of libraries"""
	projectSettings.currentProject.SetValue("libraries", set())


def ClearStaticLibraries( ):
	"""Clears the list of statically-linked libraries"""
	projectSettings.currentProject.SetValue("staticLibraries", set())


def ClearSharedibraries( ):
	"""Clears the list of dynamically-linked libraries"""
	projectSettings.currentProject.SetValue("sharedLibraries", set())


def ClearIncludeDirectories( ):
	"""Clears the include directories"""
	projectSettings.currentProject.SetValue("includeDirs", [])


def ClearLibraryDirectories( ):
	"""Clears the library directories"""
	projectSettings.currentProject.SetValue("libraryDirs", [])


def SetOptimizationLevel( i ):
	"""
	Sets the optimization level. Due to toolchain differences, this should be called per-toolchain, usually.

	:type i: OptimizationLevel
	:param i: The level of optimization to use
	"""
	projectSettings.currentProject.SetValue("optLevel", i)
	projectSettings.currentProject.SetValue("_optLevel_set", True)


def SetDebugLevel( i ):
	"""
	Sets the debug level. Due to toolchain differences, this should be called per-toolchain, usually.

	:type i: DebugLevel
	:param i: How (and if) symbols should be generated
	"""
	projectSettings.currentProject.SetValue("debugLevel", i)
	projectSettings.currentProject.SetValue("_debugLevel_set", True)


def AddDefines( *args ):
	"""
	Add additionally defined preprocessor directives, as if each file had a #define directive at the very top.

	:type args: an arbitrary number of strings
	:param args: The list of preprocessor directives to define
	"""
	projectSettings.currentProject.ExtendList("defines", list( args ))


def ClearDefines( ):
	"""Clear the list of defined preprocessor directives"""
	projectSettings.currentProject.SetValue("defines", [])


def AddUndefines( *args ):
	"""
	Add explicitly undefined preprocessor directives, as if each file had a #undef directive at the very top.

	:type args: an arbitrary number of strings
	:param args: The list of preprocessor directives to undefine
	"""
	projectSettings.currentProject.ExtendList("undefines", list( args ))


def ClearUndefines( ):
	"""Clear the list of undefined preprocessor directives"""
	projectSettings.currentProject.SetValue("undefines", [])


def SetCxxCommand( s ):
	"""
	Specify the compiler executable to be used for compiling C++ files. Ignored by the msvc toolchain.

	:type s: str
	:param s: Path to the executable to use for compilation
	"""
	projectSettings.currentProject.SetValue("cxx", s)


def SetCcCommand( s ):
	"""
	Specify the compiler executable to be used for compiling C files. Ignored by the msvc toolchain.

	:type s: str
	:param s: Path to the executable to use for compilation
	"""
	projectSettings.currentProject.SetValue("cc", s)


def SetOutput( name, projectType = ProjectType.Application ):
	"""
	Sets the output options for this project.

	:type name: str
	:param name: The output name. Do not include an extension, and do not include the "lib" prefix for libraries on
	Linux. These are added automatically.

	:type projectType: csbuild.ProjectType
	:param projectType: The type of project to compile. The options are:
		- ProjectType.Application - on Windows, this will be built with a .exe extension. On Linux, there is no extension.
		- ProjectType.SharedLibrary - on Windows, this will generate a .lib and a .dll.
		On Linux, this will generate a .so and prefix "lib" to the output name.
		- ProjectType.StaticLibrary - on Windows, this will generate a .lib. On Linux, this will generate a .a and prefix
		"lib" to the output name.
	"""
	projectSettings.currentProject.SetValue("outputName", name)
	projectSettings.currentProject.SetValue("type", projectType)


def SetOutputExtension( name ):
	"""
	This allows you to override the extension used for the output file.

	:type name: str
	:param name: The desired extension, including the .; i.e., csbuild.Extension( ".exe" )
	"""
	projectSettings.currentProject.SetValue("ext", name)


def SetOutputDirectory( s ):
	"""
	Specifies the directory in which to place the output file.

	:type s: str
	:param s: The output directory, relative to the current script location, NOT to the project working directory.
	"""
	projectSettings.currentProject.SetValue("outputDir", os.path.abspath( s ))
	projectSettings.currentProject.SetValue("_outputDir_set", True)


def SetIntermediateDirectory( s ):
	"""
	Specifies the directory in which to place the intermediate .o or .obj files.

	:type s: str
	:param s: The object directory, relative to the current script location, NOT to the project working directory.
	"""
	projectSettings.currentProject.SetValue("objDir", os.path.abspath( s ))
	projectSettings.currentProject.SetValue("_objDir_set", True)


def EnableProfiling( ):
	"""
	Optimize output for profiling
	"""
	projectSettings.currentProject.SetValue("profile", True)


def DisableProfiling( ):
	"""
	Turns profiling optimizations back off
	"""
	projectSettings.currentProject.SetValue("profile", False)


def AddCxxCompilerFlags( *args ):
	"""
	Specifies a list of literal strings to be passed to the C++ compiler. As this is toolchain-specific, it should be
	called on a per-toolchain basis.

	:type args: an arbitrary number of strings
	:param args: The list of flags to be passed
	"""
	projectSettings.currentProject.ExtendList("cxxCompilerFlags", list( args ))


def ClearCxxCompilerFlags( ):
	"""
	Clears the list of literal C++ compiler flags.
	"""
	projectSettings.currentProject.SetValue("cxxCompilerFlags", [])


def AddCcCompilerFlags( *args ):
	"""
	Specifies a list of literal strings to be passed to the C compiler. As this is toolchain-specific, it should be
	called on a per-toolchain basis.

	:type args: an arbitrary number of strings
	:param args: The list of flags to be passed
	"""
	projectSettings.currentProject.ExtendList("ccCompilerFlags", list( args ))


def ClearCcCompilerFlags( ):
	"""
	Clears the list of literal C compiler flags.
	"""
	projectSettings.currentProject.SetValue("ccCompilerFlags", [])


def AddCompilerFlags( *args ):
	"""
	Specifies a list of literal strings to be passed to the both the C compiler and the C++ compiler.
	As this is toolchain-specific, it should be called on a per-toolchain basis.

	:type args: an arbitrary number of strings
	:param args: The list of flags to be passed
	"""
	AddCcCompilerFlags( *args )
	AddCxxCompilerFlags( *args )


def ClearCompilerFlags( ):
	"""
	Clears the list of literal compiler flags.
	"""
	ClearCcCompilerFlags( )
	ClearCxxCompilerFlags( )


def AddLinkerFlags( *args ):
	"""
	Specifies a list of literal strings to be passed to the linker. As this is toolchain-specific, it should be
	called on a per-toolchain basis.

	:type args: an arbitrary number of strings
	:param args: The list of flags to be passed
	"""
	projectSettings.currentProject.ExtendList("linkerFlags", list( args ))


def ClearLinkerFlags( ):
	"""
	Clears the list of literal linker flags.
	"""
	projectSettings.currentProject.SetValue("linkerFlags", [])


def DisableChunkedBuild( ):
	"""Turn off the chunked/unity build system and build using individual files."""
	projectSettings.currentProject.SetValue("useChunks", False)


def EnableChunkedBuild( ):
	"""Turn chunked/unity build on and build using larger compilation units. This is the default."""
	projectSettings.currentProject.SetValue("useChunks", True)


def StopOnFirstError():
	"""
	Stop compilation when the first error is encountered.
	"""
	_shared_globals.stopOnError = True


def SetNumFilesPerChunk( i ):
	"""
	Set the size of the chunks used in the chunked build. This indicates the number of files per compilation unit.
	The default is 10.

	This value is ignored if SetChunks is called.

	Mutually exclusive with ChunkFilesize().

	:type i: int
	:param i: Number of files per chunk
	"""
	projectSettings.currentProject.SetValue("chunkSize", i)
	projectSettings.currentProject.SetValue("chunkFilesize", 0)


def SetMaxChunkFileSize( i ):
	"""
	Sets the maximum combined filesize for a chunk. The default is 500000, and this is the default behavior.

	This value is ignored if SetChunks is called.

	Mutually exclusive with ChunkNumFiles()

	:type i: int
	:param i: Maximum size per chunk in bytes.
	"""
	projectSettings.currentProject.SetValue("chunkFilesize", i)
	projectSettings.currentProject.SetValue("chunkSize", i)


def SetChunkTolerance( i ):
	"""
	Please see detailed description.

	**If building using ChunkSize():**

	Set the number of modified files below which a chunk will be split into individual files.

	For example, if you set this to 3 (the default), then a chunk will be built as a chunk
	if more than three of its files need to be built; if three or less need to be built, they will
	be built individually to save build time.

	**If building using ChunkFilesize():**

	Sets the total combined filesize of modified files within a chunk below which the chunk will be split into
	individual files.

	For example, if you set this to 150000 (the default), then a chunk will be built as a chunk if the total
	filesize of the files needing to be built exceeds 150kb. If less than 150kb worth of data needs to be built,
	they will be built individually to save time.

	:type i: int
	:param i: Number of files required to trigger chunk building.
	"""
	if projectSettings.currentProject.chunkFilesize > 0:
		projectSettings.currentProject.SetValue("chunkSizeTolerance", i)
	elif projectSettings.currentProject.chunkSize > 0:
		projectSettings.currentProject.SetValue("chunkTolerance", i)
	else:
		log.LOG_WARN( "Chunk size and chunk filesize are both zero or negative, cannot set a tolerance." )


def SetChunks( *chunks ):
	"""
	Explicitly set the chunks used as compilation units.

	NOTE that setting this will disable the automatic file gathering, so any files in the project directory that
	are not specified here will not be built.

	:type chunks: an arbitrary number of lists of strings
	:param chunks: Lists containing filenames of files to be built,
	relativel to the script's location, NOT the project working directory. Each list will be built as one chunk.
	"""
	chunks = list( chunks )
	projectSettings.currentProject.SetValue("forceChunks", chunks)


def ClearChunks( ):
	"""Clears the explicitly set list of chunks and returns the behavior to the default."""
	projectSettings.currentProject.SetValue("forceChunks", [])


def SetHeaderRecursionDepth( i ):
	"""
	Sets the depth to search for header files. If set to 0, it will search with unlimited recursion to find included
	headers. Otherwise, it will travel to a depth of i to check headers. If set to 1, this will only check first-level
	headers and not check headers included in other headers; if set to 2, this will check headers included in headers,
	but not headers included by *those* headers; etc.

	This is very useful if you're using a large library (such as boost) or a very large project and are experiencing
	long waits prior to compilation.

	:type i: int
	:param i: Recursion depth for header examination
	"""
	projectSettings.currentProject.SetValue("headerRecursionDepth", i)


def IgnoreExternalHeaders( ):
	"""
	If this option is set, external headers will not be checked or followed when building. Only headers within the
	base project's directory and its subdirectories will be checked. This will speed up header checking, but if you
	modify any external headers, you will need to manually --clean or --rebuild the project.
	"""
	projectSettings.currentProject.SetValue("ignoreExternalHeaders", True)


def DisableWarnings( ):
	"""
	Disables all warnings.
	"""
	projectSettings.currentProject.SetValue("noWarnings", True)


def SetDefaultTarget( s ):
	"""
	Sets the default target if none is specified. The default value for this is release.

	:type s: str
	:param s: Name of the target to build for this project if none is specified.
	"""
	projectSettings.currentProject.SetValue("defaultTarget", s.lower( ))


def Precompile( *args ):
	"""
	Explicit list of header files to precompile. Disables chunk precompile when called.

	:type args: an arbitrary number of strings
	:param args: The files to precompile.
	"""
	projectSettings.currentProject.SetValue("precompile", [])
	for arg in list( args ):
		projectSettings.currentProject.AppendList("precompile",  os.path.abspath( arg ) )
	projectSettings.currentProject.SetValue("chunkedPrecompile", False)


def PrecompileAsC( *args ):
	"""
	Specifies header files that should be compiled as C headers instead of C++ headers.

	:type args: an arbitrary number of strings
	:param args: The files to specify as C files.
	"""
	projectSettings.currentProject.SetValue("precompileAsC", [])
	for arg in list( args ):
		projectSettings.currentProject.AppendList("precompileAsC",  os.path.abspath( arg ) )


def EnableChunkedPrecompile( ):
	"""
	When this is enabled, all header files will be precompiled into a single "superheader" and included in all files.
	"""
	projectSettings.currentProject.SetValue("chunkedPrecompile", True)


def DisablePrecompile( *args ):
	"""
	Disables precompilation and handles headers as usual.

	:type args: an arbitrary number of strings
	:param args: A list of files to disable precompilation for.
	If this list is empty, it will disable precompilation entirely.
	"""
	args = list( args )
	if args:
		newargs = []
		for arg in args:
			if arg[0] != '/' and not arg.startswith( "./" ):
				arg = "./" + arg
			newargs.append( os.path.abspath( arg ) )
			projectSettings.currentProject.ExtendList("precompileExcludeFiles", newargs)
	else:
		projectSettings.currentProject.SetValue("chunkedPrecompile", False)
		projectSettings.currentProject.SetValue("precompile", [])
		projectSettings.currentProject.SetValue("precompileAsC", [])


def EnableUnityBuild( ):
	"""
	Turns on true unity builds, combining all files into only one compilation unit.
	"""
	projectSettings.currentProject.SetValue("unity", True)


def LinkStaticRuntime( ):
	"""
	Link against a static C/C++ runtime library.
	"""
	projectSettings.currentProject.SetValue("useStaticRuntime", True)


def LinkSharedRuntime( ):
	"""
	Link against a dynamic C/C++ runtime library.
	"""
	projectSettings.currentProject.SetValue("useStaticRuntime", False)


def SetOutputArchitecture( arch ):
	"""
	Set the output architecture.

	:type arch: str
	:param arch: The desired architecture. Choose from x86, x64, ARM.
	"""
	projectSettings.currentProject.SetValue("outputArchitecture", arch)


def AddExtraFiles( *args ):
	"""
	Adds additional files to be compiled that are not in the project directory.

	:type args: an arbitrary number of strings
	:param args: A list of files to add.
	"""
	for arg in list( args ):
		for file in glob.glob( arg ):
			projectSettings.currentProject.AppendList("extraFiles",  os.path.abspath( file ) )


def ClearExtraFiles():
	"""
	Clear the list of external files to compile.
	"""
	projectSettings.currentProject.SetValue("extraFiles", [])


def AddExtraDirectories( *args ):
	"""
	Adds additional directories to search for files in.

	:type args: an arbitrary number of strings
	:param args: A list of directories to search.
	"""
	for arg in list( args ):
		projectSettings.currentProject.AppendList("extraDirs",  os.path.abspath( arg ) )


def ClearExtraDirectories():
	"""
	Clear the list of external directories to search.
	"""
	projectSettings.currentProject.SetValue("extraDirs", [])


def AddExtraObjects( *args ):
	"""
	Adds additional objects to be passed to the linker that are not in the project directory.

	:type args: an arbitrary number of strings
	:param args: A list of objects to add.
	"""
	for arg in list( args ):
		for file in glob.glob( arg ):
			projectSettings.currentProject.UnionSet("extraObjs",  os.path.abspath( file ) )


def ClearExtraObjects():
	"""
	Clear the list of external objects to link.
	"""
	projectSettings.currentProject.SetValue("extraObjs", set())


def EnableWarningsAsErrors( ):
	"""
	Promote all warnings to errors.
	"""
	projectSettings.currentProject.SetValue("warningsAsErrors", True)


def DisableWarningsAsErrors( ):
	"""
	Disable the promotion of warnings to errors.
	"""
	projectSettings.currentProject.SetValue("warningsAsErrors", False)


def DoNotChunkTogether(pattern, *additionalPatterns):
	"""
	Makes files matching the given patterns mutually exclusive for chunking.
	I.e., if you call this with DoNotChunkTogether("File1.cpp", "File2.cpp"), it guarantees
	File1 and File2 will never appear together in the same chunk. If you specify more than two files,
	or a pattern that matches more than two files, no two files in the list will ever appear together.

	.. note:
		This setting is not eligible for scope inheritance.

	:type pattern: string
	:param pattern: Pattern to search for files with (i.e., Source/*_Unchunkable.cpp)
	:type additionalPatterns: arbitrary number of optional strings
	:param additionalPatterns: Additional patterns to compile the list of mutually exclusive files with
	"""
	patterns = [pattern] + list(additionalPatterns)
	mutexFiles = set()
	for patternToMatch in patterns:
		for filename in glob.glob(patternToMatch):
			mutexFiles.add(os.path.abspath(filename))

	for file1 in mutexFiles:
		for file2 in mutexFiles:
			if file1 == file2:
				continue
			if file1 not in projectSettings.currentProject.chunkMutexes:
				projectSettings.currentProject.chunkMutexes[file1] = { file2 }
			else:
				projectSettings.currentProject.chunkMutexes[file1].add(file2)


def DoNotChunk(*files):
	"""
	Prevents the listed files (or files matching the listed patterns) from ever being placed
	in a chunk, ever.

	:type files: arbitrary number of strings
	:param files: filenames or patterns to exclude from chunking
	"""

	for pattern in list(files):
		for filename in glob.glob(pattern):
			projectSettings.currentProject.AddToSet("chunkExcludes", os.path.abspath(filename))


def SetStaticLinkMode(mode):
	"""
	Determines how static links are handled. With the msvc toolchain, iterative link times of a project with many libraries
	can be significantly improved by setting this to :StaticLinkMode.LinkLibs:. This will cause the linker to link
	the .obj files used to make a library directly into the dependent project. Link times for full builds may be slightly slower,
	but this will allow incremental linking to function when libraries are being changed. (Usually, changing a .lib results
	in a full link.)

	On most toolchains, this defaults to :StaticLinkMode.LinkLibs:. In debug mode only for the msvc toolchain, this defaults
	to :StaticLinkMode.LinkIntermediateObjects:.

	:type mode: :StaticLinkMode:
	:param mode: The link mode to set
	"""
	projectSettings.currentProject.SetValue("linkMode", mode)
	projectSettings.currentProject.SetValue("linkModeSet", True)


def SetUserData(key, value):
	"""
	Adds miscellaneous data to a project. This can be used later in a build event or in a format string.

	This becomes an attribute on the project's userData member variable. As an example, to set a value:

	csbuild.SetUserData("someData", "someValue")

	Then to access it later:

	project.userData.someData

	.. note:
		This setting is not eligible for scope inheritance.

	:type key: str
	:param key: name of the variable to set
	:type value: any
	:param value: value to set to that variable
	"""
	projectSettings.currentProject.userData.dataDict[key] = value


def SetSupportedArchitectures(*architectures):
	"""
	Specifies the architectures that this project supports. This can be used to limit
	--all-architectures from building everything supported by the toolchain, if the project
	is not set up to support all of the toolchain's architectures.
	"""
	projectSettings.currentProject.SetValue("supportedArchitectures", set(architectures))


def SetSupportedToolchains(*toolchains):
	"""
	Specifies the toolchains that this project supports. This can be used to limit
	--all-toolchains from building everything supported by csbuild, if the project
	is not set up to support all of the toolchains.
	"""
	projectSettings.currentProject.SetValue("supportedToolchains", set(toolchains))


def RegisterToolchain( name, compiler, linker ):
	"""
	Register a new toolchain for use in the project.

	:type name: str
	:param name: The name of the toolchain being registered
	:type compiler: class derived from :class:`csbuild.toolchain.compilerBase`
	:param compiler: The compiler used in this toolchain
	:type linker: class derived from :class:`csbuild.toolchain.linkerBase`
	:param linker: The linker used in this toolchain
	"""
	class registeredToolchain(toolchain.toolchain):
		def __init__(self):
			toolchain.toolchain.__init__(self)
			self.tools["compiler"] = compiler()
			self.tools["linker"] = linker()

	# Format the name so that it can be used as part of its architecture command line option.
	# This generally means replacing all whitespace with dashes.
	toolchainArchString = name
	toolchainArchString = toolchainArchString.replace(" ", "-")
	toolchainArchString = toolchainArchString.replace(",", "-")
	toolchainArchString = toolchainArchString.replace("\t", "-")
	toolchainArchString = toolchainArchString.replace("\r", "") # Intentionally remove '\r'.
	toolchainArchString = toolchainArchString.replace("\n", "-")

	# Don't know how often it will occur, but if any quotes happen to be in the string, remove them.
	toolchainArchString = toolchainArchString.replace('"', "")
	toolchainArchString = toolchainArchString.replace("'", "")

	toolchainArchString = toolchainArchString.strip("-") # Remove any dashes at the start and end of the string.

	_shared_globals.alltoolchains[name] = registeredToolchain
	_shared_globals.allToolchainArchStrings[name] = (toolchainArchString + "-architecture", toolchainArchString + "-arch")

	projectSettings.currentProject.toolchains.update( { name : registeredToolchain() } )
	projectSettings.currentProject.intermediateToolchains.update( { name : registeredToolchain() } )
	projectSettings.currentProject.finalToolchains.update( { name : registeredToolchain() } )


def RegisterProjectGenerator( name, generator ):
	"""
	Register a new project generator for use in solution generation.

	:type name: str
	:param name: The name of the generator being registered
	:type generator: csbuild.project_generator.project_generator
	:param generator: The generator to associate with that name
	"""
	_shared_globals.allgenerators[name] = generator
	_shared_globals.project_generators[name] = generator


def Toolchain( *args ):
	"""
	Perform actions on the listed toolchains. Examples:

	csbuild.Toolchain("gcc").NoPrecompile()
	csbuild.Toolchain("gcc", "msvc").EnableWarningsAsErrors()

	:type args: arbitrary number of strings
	:param args: The list of toolchains to act on

	:return: A proxy object that enables functions to be applied to one or more specific toolchains.
	"""
	toolchains = []
	for arg in list( args ):
		scope = projectSettings.currentProject._currentScope
		if scope & ScopeDef.Self:
			toolchains.append( projectSettings.currentProject.toolchains[arg] )
		if scope & ScopeDef.Intermediate:
			toolchains.append( projectSettings.currentProject.intermediateToolchains[arg] )
		if scope & ScopeDef.Final:
			toolchains.append( projectSettings.currentProject.finalToolchains[arg] )
	return toolchain.ClassCombiner( toolchains )


def SetActiveToolchain( name ):
	"""
	Sets the active toolchain to be used when building the project.

	On Windows platforms, this is set to msvc by default.
	On Linux platforms, this is set to gcc by default.

	This will be overridden if the script is executed with the --toolchain option.

	:type name: str
	:param name: The toolchain to use to build the project
	"""
	_shared_globals.selectedToolchains.add(name)
	projectSettings.currentProject.SetValue("activeToolchainName", name)

#</editor-fold>

#<editor-fold desc="decorators">

scriptFiles = []

class Link(object):
	def __init__(self, libName, scope = ScopeDef.Final, includeToolchains=None, includeArchitectures=None, excludeToolchains=None, excludeArchitectures=None):
		self.libName = libName
		self.scope = scope
		self.includeToolchains = includeToolchains
		self.includeArchitectures = includeArchitectures
		self.excludeToolchains = excludeToolchains
		self.excludeArchitectures = excludeArchitectures

class Src(object):
	def __init__(self, libName, scope = ScopeDef.Final, includeToolchains=None, includeArchitectures=None, excludeToolchains=None, excludeArchitectures=None):
		self.libName = libName
		self.scope = scope
		self.includeToolchains = includeToolchains
		self.includeArchitectures = includeArchitectures
		self.excludeToolchains = excludeToolchains
		self.excludeArchitectures = excludeArchitectures

def scope( scope ):

	def wrap( func ):
		oldScope = projectSettings.currentProject._currentScope
		projectSettings.currentProject._currentScope = scope
		func()
		projectSettings.currentProject._currentScope = oldScope

	return wrap

def project( name, workingDirectory, depends = None, priority = -1, ignoreDependencyOrdering = False ):
	"""
	Decorator used to declare a project. linkDepends and srcDepends here will be used to determine project build order.

	:type name: str
	:param name: A unique name to be used to refer to this project

	:type workingDirectory: str
	:param workingDirectory: The directory in which to perform build operations. This directory
	(or a subdirectory) should contain the project's source files.

	:type depends: list
	:param linkDepends: A list of other projects. This project will not be linked until the dependent projects
	have completed their build process. These can be specified as either projName, Link(projName, scope), or Src(projName, scope).

	projName will be converted to Link(projName, ScopeDef.Final)
	Link will cause the project it applies to to link this dependency.
	Src will cause the project it applies to to wait until this project finishes before it starts its build at all.
	"""
	if not depends:
		depends = []
	if isinstance( depends, str ):
		linkDepends = [depends]

	def wrap( projectFunction ):
		if name in _shared_globals.tempprojects:
			log.LOG_ERROR( "Multiple projects with the same name: {}. Ignoring.".format( name ) )
			return
		previousProject = projectSettings.currentProject.copy( )
		projectFunction( )

		newProject = projectSettings.currentProject.copy( )

		newProject.key = name
		newProject.name = name
		newProject.workingDirectory = os.path.abspath( workingDirectory )
		newProject.scriptPath = os.getcwd( )
		newProject.scriptFile = scriptFiles[-1]

		newProject.libDepends = []
		newProject.libDependsIntermediate = []
		newProject.libDependsFinal = []

		newProject.srcDepends = []
		newProject.srcDependsIntermediate = []
		newProject.srcDependsFinal = []

		for depend in depends:
			if isinstance(depend, str):
				depend = Link(depend)

			if isinstance(depend, Link):
				if depend.scope & ScopeDef.Self:
					newProject.linkDepends.append(depend)
				if depend.scope & ScopeDef.Intermediate:
					newProject.linkDependsIntermediate.append(depend)
				if depend.scope & ScopeDef.Final:
					newProject.linkDependsFinal.append(depend)
			elif isinstance(depend, Src):
				if depend.scope & ScopeDef.Self:
					newProject.srcDepends.append(depend)
				if depend.scope & ScopeDef.Intermediate:
					newProject.srcDependsIntermediate.append(depend)
				if depend.scope & ScopeDef.Final:
					newProject.srcDependsFinal.append(depend)

		newProject.func = projectFunction

		newProject.priority = priority
		newProject.ignoreDependencyOrdering = ignoreDependencyOrdering

		_shared_globals.tempprojects.update( { name: newProject } )
		projectSettings.currentGroup.tempprojects.update( { name: newProject } )
		newProject.parentGroup = projectSettings.currentGroup

		projectSettings.currentProject = previousProject
		return projectFunction


	return wrap


def projectGroup( name ):
	"""
	Specifies a grouping of projects. This will add scope to the global project settings, and will additionally be used
	in solution generation to group the projects.

	:type name: str
	:param name: The name to identify this project group
	"""
	def wrap( groupFunction ):
		if name in projectSettings.currentGroup.subgroups:
			projectSettings.currentGroup = projectSettings.currentGroup.subgroups[name]
		else:
			newGroup = projectSettings.ProjectGroup( name, projectSettings.currentGroup )
			projectSettings.currentGroup.subgroups.update( { name: newGroup } )
			projectSettings.currentGroup = newGroup

		previousProject = projectSettings.currentProject.copy( )
		groupFunction( )
		projectSettings.currentProject = previousProject

		projectSettings.currentGroup = projectSettings.currentGroup.parentGroup


	return wrap


def target( name, override = False ):
	"""
	Specifies settings for a target. If the target doesn't exist it will be implicitly created. If a target does exist
	with this name, this function will be appended to a list of functions to be run for that target name, unless
	override is True.

	:type name: str
	:param name: The name for the target; i.e., "debug", "release"
	:type override: bool
	:param override: If this is true, existing functionality for this target will be discarded for this project.
	"""
	def wrap( targetFunction ):
		if override is True or name not in projectSettings.currentProject.targets:
			projectSettings.currentProject.targets.update( { name: [targetFunction] } )
		else:
			projectSettings.currentProject.targets[name].append( targetFunction )

		return targetFunction


	_shared_globals.alltargets.add( name )
	return wrap


def fileSettings( files, override = False ):
	"""
	Specifies settings that affect a single specific file

	:type files: str or list[str]
	:param files: The file or files to apply these settings to
	:type override: bool
	:param override: If this is true, existing functionality for this target will be discarded for this project.
	"""
	def wrap( fileFunction ):
		fileList = files
		if not isinstance(fileList, list):
			fileList = [fileList]

		for file in fileList:
			file = os.path.normcase(os.path.abspath(file))
			if override is True or file not in projectSettings.currentProject.fileOverrides:
				projectSettings.currentProject.fileOverrides.update( { file: [fileFunction] } )
			else:
				projectSettings.currentProject.fileOverrides[file].append( fileFunction )

			return fileFunction


	return wrap


def architecture( archs, override = False ):
	"""
	Specifies settings for a specific list of architectures.
	"""
	def wrap( archFunction ):
		archList = archs
		if not isinstance(archList, list):
			archList = [archList]

		for arch in archList:
			if override is True or arch not in projectSettings.currentProject.archFuncs:
				projectSettings.currentProject.archFuncs.update( { arch: [archFunction] } )
			else:
				projectSettings.currentProject.archFuncs[arch].append( archFunction )

		return archFunction

	return wrap


def prePrepareBuildStep( func ):
	"""
	Decorator that creates a pre-build step for the containing project. Pre-PrepareBuild steps run just before the project
	begins preparing its build tasks.

	:param func: (Implicit) The function wrapped by this decorator
	:type func: (Implicit) function

	.. note:: The function this wraps should take a single argument, which will be of type
		:class:`csbuild.projectSettings.projectSettings`.
	"""

	projectSettings.currentProject.SetValue("prePrepareBuildStep", func)
	return func


def postPrepareBuildStep( func ):
	"""
	Decorator that creates a post-compile step for the containing project. Post-PrepareBuild steps run just after the
	project completes its build preparation. This is the only place where running project.RediscoverFiles() has any
	appreciable effect.

	:param func: (Implicit) The function wrapped by this decorator
	:type func: (Implicit) function

	.. note:: The function this wraps should take a single argument, which will be of type
		:class:`csbuild.projectSettings.projectSettings`.
	"""

	projectSettings.currentProject.SetValue("postPrepareBuildStep", func)
	return func


def preMakeStep( func ):
	"""
	Decorator that creates a pre-make step for the containing project. Pre-make steps run after all projects' preparation
	steps have completed and their final chunk sets have been collected, but before any compiling starts.

	:param func: (Implicit) The function wrapped by this decorator
	:type func: (Implicit) function

	.. note:: The function this wraps should take a single argument, which will be of type
		:class:`csbuild.projectSettings.projectSettings`.
	"""

	projectSettings.currentProject.SetValue("preMakeStep", func)
	return func


def postMakeStep( func ):
	"""
	Decorator that creates a post-make step for the containing project. Post-make steps run after all projects have
	finished building and linking. This step will only run if the entire build process was successful.

	:param func: (Implicit) The function wrapped by this decorator
	:type func: (Implicit) function

	.. note:: The function this wraps should take a single argument, which will be of type
		:class:`csbuild.projectSettings.projectSettings`.
	"""

	projectSettings.currentProject.SetValue("postMakeStep", func)
	return func


def preBuildStep( func ):
	"""
	Decorator that creates a pre-build step for the containing project. Pre-build steps run just before the project
	begins compiling.

	:param func: (Implicit) The function wrapped by this decorator
	:type func: (Implicit) function

	.. note:: The function this wraps should take a single argument, which will be of type
		:class:`csbuild.projectSettings.projectSettings`.
	"""

	projectSettings.currentProject.SetValue("preBuildStep", func)
	return func


def postBuildStep( func ):
	"""
	Decorator that creates a post-build step for the containing project. Post-build steps run after the project has
	**successfully** compiled **and** linked.

	:param func: (Implicit) The function wrapped by this decorator
	:type func: (Implicit) function

	.. note:: The function this wraps should take a single argument, which will be of type
		:class:`csbuild.projectSettings.projectSettings`.
	"""

	projectSettings.currentProject.SetValue("postBuildStep", func)
	return func


def preLinkStep( func ):
	"""
	Decorator that creates a pre-link step for the containing project. Pre-link steps run after a successful compile of
	the project, but before the project links.

	:param func: (Implicit) The function wrapped by this decorator
	:type func: (Implicit) function

	.. note:: The function this wraps should take a single argument, which will be of type
		:class:`csbuild.projectSettings.projectSettings`.
	"""

	projectSettings.currentProject.SetValue("preLinkStep", func)
	return func


#</editor-fold>

_shared_globals.starttime = time.time( )

sys.stdout = log.stdoutWriter(sys.stdout)

_building = False

class _LinkStatus(object):
	"""
	Defines the current link status of a project.
	"""
	Fail = 0
	Success = 1
	UpToDate = 2

def _build( ):
	"""
	Build the project.
	This step handles:
	Checking library dependencies.
	Checking which files need to be built.
	And spawning a build thread for each one that does.
	"""

	if _guiModule:
		_guiModule.run()

	built = False
	global _building
	_building = True

	linker_threads_blocked = _shared_globals.max_linker_threads - 1
	for i in range( linker_threads_blocked ):
		_shared_globals.link_semaphore.acquire(True)

	for project in _shared_globals.sortedProjects:
		_shared_globals.total_compiles += len( project._finalChunkSet )

	_shared_globals.total_compiles += _shared_globals.total_precompiles
	_shared_globals.current_compile = 1

	projects_in_flight = []
	projects_done = set()
	pending_links = set()
	pending_builds = _shared_globals.sortedProjects
	#projects_needing_links = set()

	for project in pending_builds:
		project.activeToolchain.preMakeStep(project)
		if project.preMakeStep:
			log.LOG_BUILD( "Running pre-make step for {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )
			project.preMakeStep(project)

	for project in _shared_globals.sortedProjects:
		log.LOG_BUILD( "Verifying libraries for {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )
		if not project.check_libraries( ):
			return False
			#if _utils.needs_link(project):
			#    projects_needing_links.add(project.key)

	_shared_globals.starttime = time.time( )

	_linkThread.start()

	def ReconcilePostBuild():
		LinkedSomething = True
		while LinkedSomething:
			LinkedSomething = False
			for otherProj in list( projects_in_flight ):
				with otherProj.mutex:
					complete = otherProj.compilationCompleted

				if complete >= len( otherProj._finalChunkSet ) + int(
						otherProj.needsPrecompileC ) + int(
						otherProj.needsPrecompileCpp ):
					totaltime = (time.time( ) - otherProj.starttime)
					minutes = math.floor( totaltime / 60 )
					seconds = math.floor( totaltime % 60 )

					log.LOG_BUILD(
						"Compile of {0} ({3} {4}) took {1}:{2:02}".format( otherProj.outputName, int( minutes ),
							int( seconds ), otherProj.targetName, otherProj.outputArchitecture ) )
					otherProj.buildEnd = time.time()
					projects_in_flight.remove( otherProj )
					if otherProj.compilationFailed:
						log.LOG_ERROR( "Build of {} ({} {}/{}) failed! Finishing up non-dependent build tasks...".format(
							otherProj.outputName, otherProj.targetName, otherProj.outputArchitecture, otherProj.activeToolchainName ) )
						otherProj.state = _shared_globals.ProjectState.FAILED
						otherProj.linkQueueStart = time.time()
						otherProj.linkStart = otherProj.linkQueueStart
						otherProj.endTime = otherProj.linkQueueStart
						continue

					okToLink = True
					if otherProj.reconciledLinkDepends:
						for depend in otherProj.reconciledLinkDepends:
							if depend not in projects_done:
								okToLink = False
								break
					if okToLink:
						_link( otherProj )
						LinkedSomething = True
						projects_done.add( otherProj.key )
					else:
						log.LOG_LINKER(
							"Linking for {} ({} {}/{}) deferred until all dependencies have finished building...".format(
								otherProj.outputName, otherProj.targetName, otherProj.outputArchitecture, otherProj.activeToolchainName ) )
						otherProj.state = _shared_globals.ProjectState.WAITING_FOR_LINK
						pending_links.add( otherProj )

			for otherProj in list( pending_links ):
				okToLink = True
				for depend in otherProj.reconciledLinkDepends:
					if depend not in projects_done:
						okToLink = False
						break
				if okToLink:
					_link( otherProj )
					LinkedSomething = True
					projects_done.add( otherProj.key )
					pending_links.remove( otherProj )

	while pending_builds:
		theseBuilds = pending_builds
		pending_builds = []
		for project in theseBuilds:
			for depend in project.srcDepends:
				if depend not in projects_done:
					pending_builds.append( project )
					continue
			projects_in_flight.append( project )

			projectSettings.currentProject = project

			project.starttime = time.time( )

			project.activeToolchain.preBuildStep(project)
			if project.preBuildStep:
				log.LOG_BUILD( "Running pre-build step for {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )
				project.preBuildStep( project )

			log.LOG_BUILD( "Building {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )
			project.state = _shared_globals.ProjectState.BUILDING
			project.startTime = time.time()

			if project.precompile_headers( ):
				for chunk in projectSettings.currentProject._finalChunkSet:
					#not set until here because _finalChunkSet may be empty.
					project._builtSomething = True

					chunkFileStr = ""
					if chunk in project.chunksByFile:
						chunkFileStr = " {}".format( [ os.path.basename(piece) for piece in project.chunksByFile[chunk] ] )
					elif chunk in project.splitChunks:
						chunkFileStr = " [Split from {}_{}{}]".format(
							project.splitChunks[chunk],
							project.targetName,
							project.activeToolchain.Compiler().GetObjExt()
						)

					built = True
					obj = _utils.GetSourceObjPath(projectSettings.currentProject, chunk, sourceIsChunkPath=projectSettings.currentProject.ContainsChunk(chunk))
					if not _shared_globals.semaphore.acquire( False ):
						if _shared_globals.max_threads != 1:
							log.LOG_INFO( "Waiting for a build thread to become available..." )
						_shared_globals.semaphore.acquire( True )

					ReconcilePostBuild()

					if _shared_globals.interrupted:
						Exit( 2 )
					if not _shared_globals.build_success and _shared_globals.stopOnError:
						log.LOG_ERROR("Errors encountered during build, finishing current tasks and exiting...")
						_shared_globals.semaphore.release()
						break
					if _shared_globals.times:
						totaltime = (time.time( ) - _shared_globals.starttime)
						_shared_globals.lastupdate = totaltime
						minutes = math.floor( totaltime / 60 )
						seconds = math.floor( totaltime % 60 )
						avgtime = sum( _shared_globals.times ) / (len( _shared_globals.times ))
						esttime = totaltime + ((avgtime * (
							_shared_globals.total_compiles - len(
								_shared_globals.times ))) / _shared_globals.max_threads)
						if esttime < totaltime:
							esttime = totaltime
							_shared_globals.esttime = esttime
						estmin = math.floor( esttime / 60 )
						estsec = math.floor( esttime % 60 )
						log.LOG_BUILD(
							"Compiling {0}{7}... ({1}/{2}) - {3}:{4:02}/{5}:{6:02}".format( os.path.basename( obj ),
								_shared_globals.current_compile, _shared_globals.total_compiles, int( minutes ),
								int( seconds ), int( estmin ),
								int( estsec ), chunkFileStr ) )
					else:
						totaltime = (time.time( ) - _shared_globals.starttime)
						minutes = math.floor( totaltime / 60 )
						seconds = math.floor( totaltime % 60 )
						log.LOG_BUILD(
							"Compiling {0}{5}... ({1}/{2}) - {3}:{4:02}".format( os.path.basename( obj ),
								_shared_globals.current_compile,
								_shared_globals.total_compiles, int( minutes ), int( seconds ), chunkFileStr ) )
					_utils.ThreadedBuild( chunk, obj, project ).start( )
					_shared_globals.current_compile += 1
			else:
				projects_in_flight.remove( project )
				log.LOG_ERROR( "Build of {} ({} {}/{}) failed! Finishing up non-dependent build tasks...".format(
					project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName  ) )

				with project.mutex:
					for chunk in project._finalChunkSet:
						project.fileStatus[os.path.normcase(chunk)] = _shared_globals.ProjectState.ABORTED

				_shared_globals.total_compiles -= len(project._finalChunkSet)

				project.linkQueueStart = time.time()
				project.linkStart = project.linkQueueStart
				project.endTime = project.linkQueueStart
				project.state = _shared_globals.ProjectState.FAILED

			if not _shared_globals.build_success and _shared_globals.stopOnError:
				break

		#Wait until all threads are finished. Simple way to do this is acquire the semaphore until it's out of
		# resources.
		for j in range( _shared_globals.max_threads ):
			if not _shared_globals.semaphore.acquire( False ):
				if _shared_globals.max_threads != 1:
					if _shared_globals.times:
						totaltime = (time.time( ) - _shared_globals.starttime)
						_shared_globals.lastupdate = totaltime
						minutes = math.floor( totaltime / 60 )
						seconds = math.floor( totaltime % 60 )
						avgtime = sum( _shared_globals.times ) / (len( _shared_globals.times ))
						esttime = totaltime + ((avgtime * (_shared_globals.total_compiles - len(
							_shared_globals.times ))) / _shared_globals.max_threads)
						if esttime < totaltime:
							esttime = totaltime
						estmin = math.floor( esttime / 60 )
						estsec = math.floor( esttime % 60 )
						_shared_globals.esttime = esttime
						log.LOG_THREAD(
							"Waiting on {0} more build thread{1} to finish... ({2}:{3:02}/{4}:{5:02})".format(
								_shared_globals.max_threads - j,
								"s" if _shared_globals.max_threads - j != 1 else "", int( minutes ),
								int( seconds ), int( estmin ), int( estsec ) ) )
					else:
						log.LOG_THREAD(
							"Waiting on {0} more build thread{1} to finish...".format(
								_shared_globals.max_threads - j,
								"s" if _shared_globals.max_threads - j != 1 else "" ) )

				ReconcilePostBuild()
				_shared_globals.semaphore.acquire( True )

				if linker_threads_blocked > 0:
					_shared_globals.link_semaphore.release()
					linker_threads_blocked -= 1

				if _shared_globals.interrupted:
					Exit( 2 )

		#Then immediately release all the semaphores once we've reclaimed them.
		#We're not using any more threads so we don't need them now.
		for j in range( _shared_globals.max_threads ):
			if _shared_globals.stopOnError:
				projects_in_flight = set()
			_shared_globals.semaphore.release( )

		ReconcilePostBuild()

	if projects_in_flight:
		log.LOG_ERROR( "Could not complete all projects. This is probably very bad and should never happen."
					   " Remaining projects: {0}".format( [p.key for p in projects_in_flight] ) )
	if pending_links:
		log.LOG_ERROR( "Could not link all projects. Do you have unmet dependencies in your makefile?"
					   " Remaining projects: {0}".format( [p.key for p in pending_links] ) )
		for p in pending_links:
			p.state = _shared_globals.ProjectState.ABORTED
		_shared_globals.build_success = False
	for proj in _shared_globals.sortedProjects:
		proj.save_md5s( proj.allsources, proj.allheaders )

	if not built:
		log.LOG_BUILD( "Nothing to build." )
	_building = False
	global _linkCond
	global _linkMutex
	with _linkMutex:
		_linkCond.notify()
	log.LOG_THREAD("Waiting for linker tasks to finish.")
	_linkThread.join()

	if not projects_in_flight and not pending_links:
		for project in _shared_globals.sortedProjects:
			project.activeToolchain.postMakeStep(project)
			if project.postMakeStep:
				log.LOG_BUILD( "Running post-make step for {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )
				project.postMakeStep(project)

	compiletime = time.time( ) - _shared_globals.starttime
	totalmin = math.floor( compiletime / 60 )
	totalsec = math.floor( compiletime % 60 )
	log.LOG_BUILD( "Compilation took {0}:{1:02}".format( int( totalmin ), int( totalsec ) ) )

	_shared_globals.buildFinished = True

	return _shared_globals.build_success

_linkMutex = threading.Lock()
_linkCond = threading.Condition(_linkMutex)
_linkQueue = []
_currentLinkThreads = set()
_linkThreadMutex = threading.Lock()
_recheckDeferredLinkTasks = False

def _link( project, *objs ):
	"""
	Linker:
	Links all the built files.
	Accepts an optional list of object files to link; if this list is not provided it will use the auto-generated
	list created by build()
	This function also checks (if nothing was built) the modified times of all the required libraries, to see if we need
	to relink anyway, even though nothing was compiled.
	"""
	global _linkQueue
	global _linkMutex
	global _linkCond

	project.state = _shared_globals.ProjectState.LINK_QUEUED
	project.linkQueueStart = time.time()
	with _linkMutex:
		_linkQueue.append( (project, list(objs)) )
		_linkCond.notify()


def _performLink(project, objs):
	project.linkStart = time.time()

	project.activeToolchain.preLinkStep(project)
	if project.preLinkStep:
		log.LOG_BUILD( "Running pre-link step for {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName  ) )
		project.preLinkStep(project)

	project.activeToolchain.SetActiveTool("linker")

	starttime = time.time( )

	output = os.path.join( project.outputDir, project.outputName )

	log.LOG_LINKER( "Linking {0}...".format( os.path.abspath( output ) ) )

	if not objs:
		for chunk in project.chunks:
			if not project.unity:
				obj = _utils.GetChunkedObjPath(project, chunk)
			else:
				obj = _utils.GetUnityChunkObjPath(project)
			if project.useChunks and not _shared_globals.disable_chunks and os.access(obj , os.F_OK):
				objs.append( obj )
			else:
				if type( chunk ) == list:
					for source in chunk:
						obj = _utils.GetSourceObjPath(project, source)
						if os.access(obj , os.F_OK):
							objs.append( obj )
						else:
							log.LOG_ERROR( "Could not find {} for linking. Something went wrong here.".format(obj) )
							return _LinkStatus.Fail
				else:
					obj = _utils.GetSourceObjPath(project, chunk)
					if os.access(obj , os.F_OK):
						objs.append( obj )
					else:
						log.LOG_ERROR( "Could not find {} for linking. Something went wrong here.".format(obj) )
						return _LinkStatus.Fail

	if not objs:
		return _LinkStatus.UpToDate

	for obj in project.extraObjs:
		if not os.access(obj, os.F_OK):
			log.LOG_ERROR("Could not find extra object {}".format(obj))

	objs += project.extraObjs

	if not project._builtSomething:
		if os.access(output , os.F_OK):
			mtime = os.path.getmtime( output )
			for obj in objs:
				if os.path.getmtime( obj ) > mtime:
					#If the obj time is later, something got built in another run but never got linked...
					#Maybe the linker failed last time.
					#We should count that as having built something, because we do need to link.
					#Otherwise, if the object time is earlier, there's a good chance that the existing
					#output file was linked using a different target, so let's link it again to be safe.
					project._builtSomething = True
					break

			#Even though we didn't build anything, we should verify all our libraries are up to date too.
			#If they're not, we need to relink.
			for i in range( len( project.libraryLocations ) ):
				if os.path.getmtime(project.libraryLocations[i]) > mtime:
					log.LOG_LINKER(
						"Library {0} has been modified since the last successful build. Relinking to new library."
						.format(
							project.libraryLocations[i] ) )
					project._builtSomething = True
			for dep in project.reconciledLinkDepends:
				depProj = _shared_globals.projects[dep]
				if depProj.state != _shared_globals.ProjectState.UP_TO_DATE:
					log.LOG_LINKER(
						"Dependent project {0} has been modified since the last successful build. Relinking to new library."
						.format( depProj.name ) )
					project._builtSomething = True

			#Barring the two above cases, there's no point linking if the compiler did nothing.
			if not project._builtSomething:
				if not _shared_globals.called_something:
					log.LOG_LINKER( "Nothing to link." )
				return _LinkStatus.UpToDate

	if not os.access(project.outputDir , os.F_OK):
		os.makedirs( project.outputDir )

	#On unix-based OSes, we need to remove the output file so we're not just clobbering it
	#If it gets clobbered while running it could cause BAD THINGS (tm)
	#On windows, however, we want to leave it there so that incremental link can work.
	if platform.system() != "Windows":
		if os.access(output , os.F_OK):
			os.remove( output )

	for dep in project.reconciledLinkDepends:
		proj = _shared_globals.projects[dep]
		if proj.type == ProjectType.StaticLibrary and project.linkMode == StaticLinkMode.LinkIntermediateObjects:
			for chunk in proj.chunks:
				if not proj.unity:
					obj = _utils.GetChunkedObjPath(proj, chunk)
				else:
					obj = _utils.GetUnityChunkObjPath(proj)
				if proj.useChunks and not _shared_globals.disable_chunks and os.access(obj , os.F_OK):
					objs.append( obj )
				else:
					if type( chunk ) == list:
						for source in chunk:
							obj = _utils.GetSourceObjPath(proj, source)
							if os.access(obj , os.F_OK):
								objs.append( obj )
							else:
								log.LOG_ERROR( "Could not find {} for linking. Something went wrong here.".format(obj) )
								return _LinkStatus.Fail
					else:
						obj = _utils.GetSourceObjPath(proj, chunk)
						if os.access(obj , os.F_OK):
							objs.append( obj )
						else:
							log.LOG_ERROR( "Could not find {} for linking. Something went wrong here.".format(obj) )
							return _LinkStatus.Fail
			objs += proj.extraObjs

	cmd = project.activeToolchain.Linker().GetLinkCommand( project, output, objs )
	if _shared_globals.show_commands:
		print(cmd)
	project.linkCommand = cmd
	if platform.system() != "Windows":
		cmd = shlex.split(cmd)

	fd = subprocess.Popen( cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE, cwd = project.objDir )

	(output, errors) = fd.communicate( )

	ret = fd.returncode
	sys.stdout.flush( )
	sys.stderr.flush( )

	if sys.version_info >= (3, 0):
		output = output.decode("utf-8")
		errors = errors.decode("utf-8")
	sys.stdout.write( output )
	sys.stderr.write( errors )

	with project.mutex:
		ansi_escape = re.compile(r'\x1b[^m]*m')
		stripped_errors = re.sub(ansi_escape, '', errors)
		project.linkOutput = output
		project.linkErrors = stripped_errors
		errorlist = project.activeToolchain.Compiler()._parseOutput(output)
		errorlist2 = project.activeToolchain.Compiler()._parseOutput(stripped_errors)
		if errorlist is None:
			errorlist = errorlist2
		elif errorlist2 is not None:
			errorlist += errorlist2
		errorcount = 0
		warningcount = 0
		if errorlist:
			for error in errorlist:
				if error.level == _shared_globals.OutputLevel.ERROR:
					errorcount += 1
				if error.level == _shared_globals.OutputLevel.WARNING:
					warningcount += 1

			project.errors += errorcount
			project.warnings += warningcount
			project.parsedLinkErrors = errorlist

	if ret != 0:
		log.LOG_ERROR( "Linking failed." )
		return _LinkStatus.Fail

	totaltime = time.time( ) - starttime
	totalmin = math.floor( totaltime / 60 )
	totalsec = math.floor( totaltime % 60 )
	log.LOG_LINKER( "Link time: {0}:{1:02}".format( int( totalmin ), int( totalsec ) ) )

	return _LinkStatus.Success

class _LinkThread(threading.Thread):
	def __init__(self, project, objs):
		threading.Thread.__init__( self )
		self._project = project
		self._objs = objs
		#Prevent certain versions of python from choking on dummy threads.
		if not hasattr( threading.Thread, "_Thread__block" ):
			threading.Thread._Thread__block = _shared_globals.dummy_block( )


	def run( self ):
		global _linkThreadMutex
		global _currentLinkThreads
		global _linkCond
		global _recheckDeferredLinkTasks
		try:
			project = self._project
			project.state = _shared_globals.ProjectState.LINKING
			ret = _performLink(project, self._objs)

			if ret == _LinkStatus.Fail:
				_shared_globals.build_success = False
				project.state = _shared_globals.ProjectState.LINK_FAILED
			elif ret == _LinkStatus.Success:

				try:
					project.activeToolchain.postBuildStep(project)
				except Exception:
					traceback.print_exc()

				if project.postBuildStep:
					log.LOG_BUILD( "Running post-build step for {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )
					try:
						project.postBuildStep( project )
					except Exception:
						traceback.print_exc()
				project.state = _shared_globals.ProjectState.FINISHED
			elif ret == _LinkStatus.UpToDate:
				project.state = _shared_globals.ProjectState.UP_TO_DATE
			project.endTime = time.time()
			log.LOG_BUILD( "Finished {} ({} {}/{})".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )

			_shared_globals.link_semaphore.release()

			with _linkThreadMutex:
				_currentLinkThreads.remove(project.key)
			with _linkMutex:
				_recheckDeferredLinkTasks = True
				_linkCond.notify()
		except Exception:
			traceback.print_exc()


def _linkThreadLoop():
	global _linkQueue
	global _linkMutex
	global _linkCond
	global _currentLinkThreads
	global _linkThreadMutex
	global _recheckDeferredLinkTasks

	try:
		global _building
		deferredLinks = []
		while True:
			projectsToLink = []
			with _linkMutex:
				if _recheckDeferredLinkTasks:
					if _linkQueue:
						_linkQueue += deferredLinks
					else:
						_linkQueue = deferredLinks
					deferredLinks = []
					_recheckDeferredLinkTasks = False
				if not _linkQueue:
					if not _building and not deferredLinks and not _currentLinkThreads:
						return
					_linkQueue = deferredLinks
					deferredLinks = []
					_linkCond.wait()
				projectsToLink = _linkQueue
				_linkQueue = []


			for ( project, objs ) in projectsToLink:
				okToLink = True
				with _linkThreadMutex:
					for depend in project.reconciledLinkDepends:
						if depend in _currentLinkThreads:
							okToLink = False
							break

						for ( otherProj, otherObjs ) in projectsToLink:
							if otherProj.key == depend:
								okToLink = False
								break
						if not okToLink:
							break

				if okToLink:
					with _linkThreadMutex:
						_currentLinkThreads.add(project.key)
					_shared_globals.link_semaphore.acquire(True)
					_LinkThread(project, objs).start()
				else:
					deferredLinks.append( ( project, objs ) )
	except Exception:
		traceback.print_exc()

_linkThread = threading.Thread(target=_linkThreadLoop)

def _clean( silent = False ):
	"""
	Cleans the project.
	Invoked with --clean or --rebuild.
	Deletes all of the object files to make sure they're rebuilt cleanly next run.
	"""
	for project in _shared_globals.sortedProjects:

		if not silent:
			log.LOG_BUILD( "Cleaning {} ({} {}/{})...".format( project.outputName, project.targetName, project.outputArchitecture, project.activeToolchainName ) )

		# Delete any chunks in the current project.
		for chunk in project.chunks:
			if not project.unity:
				obj = _utils.GetChunkedObjPath(project, chunk)
			else:
				obj = _utils.GetUnityChunkObjPath(project)
			if os.access(obj , os.F_OK):
				if not silent:
					log.LOG_INFO( "Deleting {0}".format( obj ) )
				os.remove( obj )

		# Individual source files may not be in the chunks list, so we're gonna play it safe and delete any single source file objects that may exist.
		for source in project.sources:
			obj = _utils.GetSourceObjPath(project, source)
			if os.access(obj , os.F_OK):
				if not silent:
					log.LOG_INFO( "Deleting {0}".format( obj ) )
				os.remove( obj )

		# Delete the project's C++ precompiled header.
		headerfile = os.path.join(project.csbuildDir, "{}_cpp_precompiled_headers_{}.hpp".format(
			project.outputName.split( '.' )[0],
			project.targetName ) )
		obj = project.activeToolchain.Compiler().GetPchFile( headerfile )
		if os.access(obj , os.F_OK):
			if not silent:
				log.LOG_INFO( "Deleting {0}".format( obj ) )
			os.remove( obj )

		# Delete the project's C precompiled header.
		headerfile = os.path.join(project.csbuildDir, "{}_c_precompiled_headers_{}.h".format(
			project.outputName.split( '.' )[0],
			project.targetName ))
		obj = project.activeToolchain.Compiler().GetPchFile( headerfile )
		if os.access(obj , os.F_OK):
			if not silent:
				log.LOG_INFO( "Deleting {0}".format( obj ) )
			os.remove( obj )

		# Delete the project's output directory.
		outpath = os.path.join( project.outputDir, project.outputName )
		if os.access(outpath , os.F_OK):
			if not silent:
				log.LOG_INFO( "Deleting {}".format( outpath ) )
			os.remove( outpath )


def _installHeaders( ):
	log.LOG_INSTALL("Installing headers...")

	for project in _shared_globals.sortedProjects:
		os.chdir( project.workingDirectory )
		#install headers
		subdir = project.headerInstallSubdir
		if not subdir:
			subdir = _utils.GetBaseName( project.outputName )
		if project.installHeaders:
			install_dir = os.path.join( _shared_globals.install_incdir, subdir )
			if not os.access(install_dir , os.F_OK):
				os.makedirs( install_dir )
			headers = []
			cHeaders = []
			project.get_files( headers = headers, cHeaders = cHeaders )
			for header in headers:
				this_header_dir = os.path.dirname( os.path.join( install_dir, os.path.relpath( header, project.workingDirectory ) ) )
				if not os.access(this_header_dir , os.F_OK):
					os.makedirs( this_header_dir )
				log.LOG_INSTALL( "Installing {0} to {1}...".format( header, this_header_dir ) )
				shutil.copy( header, this_header_dir )
			for header in cHeaders:
				log.LOG_INSTALL( "Installing {0} to {1}...".format( header, install_dir ) )
				shutil.copy( header, install_dir )
			install_something = True

def _installOutput( ):
	log.LOG_INSTALL("Installing output...")

	for project in _shared_globals.sortedProjects:
		os.chdir( project.workingDirectory )
		output = os.path.join( project.outputDir, project.outputName )
		install_something = False

		if project.installOutput:
			#install output file
			if os.access(output , os.F_OK):
				outputDir = _shared_globals.install_libdir
				if not os.access(outputDir , os.F_OK):
					os.makedirs( outputDir )
				log.LOG_INSTALL( "Installing {0} to {1}...".format( output, outputDir ) )
				shutil.copy( output, outputDir )
				pdb = output.rsplit(".", 1)[0] + ".pdb"
				if os.access(pdb , os.F_OK):
					log.LOG_INSTALL( "Installing {0} to {1}...".format( pdb, outputDir ) )
					shutil.copy( pdb, outputDir )
				install_something = True
			else:
				log.LOG_ERROR( "Output file {0} does not exist! You must build without --install first.".format( output ) )

def _install( ):
	"""
	Installer.
	Invoked with --install.
	Installs the generated output file and/or header files to the specified directory.
	Does nothing if neither InstallHeaders() nor InstallOutput() has been called in the make script.
	"""
	_installHeaders()
	_installOutput()


def _make( ):
	"""
	Performs both the build and link steps of the process.
	Aborts if the build fails.
	"""
	if not _build( ):
		_shared_globals.build_success = False
		log.LOG_ERROR( "Build failed." )
	else:
		log.LOG_BUILD( "Build complete." )


def AddScript( incFile ):
	"""
	Include the given makefile script as part of this build process.

	.. attention:: The included file will be loaded in the **current** file's namespace, not a new namespace.
	This doesn't work the same way as importing a module. Any functions or variables defined in the current module
	will be available to the called script, and anything defined in the called script will be available to the
	calling module after it's been called. As a result, this can be used much like #include in C++ to pull in
	utility scripts in addition to calling makefiles. The result is essentially as if the called script were
	copied and pasted directly into this one in the location of the AddScript() call.

	:type incFile: str
	:param incFile: path to an additional makefile script to call as part of this build
	"""
	path = os.path.dirname( incFile )
	incFile = os.path.abspath( incFile )
	wd = os.getcwd( )
	os.chdir( path )
	scriptFiles.append(incFile)
	_execfile( incFile, _shared_globals.makefile_dict, _shared_globals.makefile_dict )
	del scriptFiles[-1]
	os.chdir( wd )


def SetupDebugTarget( ):
	"""Default debug target."""
	if not projectSettings.currentProject._optLevel_set:
		SetOptimizationLevel( OptimizationLevel.Disabled )
	if not projectSettings.currentProject._debugLevel_set:
		SetDebugLevel( DebugLevel.EmbeddedSymbols )
		Toolchain("msvc").SetDebugLevel( DebugLevel.ExternalSymbols )

	if not projectSettings.currentProject.linkModeSet:
		Toolchain("msvc").SetStaticLinkMode( StaticLinkMode.LinkIntermediateObjects )

	AddDefines("_DEBUG")

	if not projectSettings.currentProject._outputDir_set:
		projectSettings.currentProject.outputDir = "{project.activeToolchainName}-{project.outputArchitecture}-{project.targetName}"
	if not projectSettings.currentProject._objDir_set:
		projectSettings.currentProject.objDir = os.path.join(projectSettings.currentProject.outputDir, "obj")
	if not projectSettings.currentProject.toolchains["msvc"].Compiler().debug_runtime_set:
		projectSettings.currentProject.toolchains["msvc"].Compiler().debug_runtime = True
	if not projectSettings.currentProject.toolchains["msvc"].Linker().debug_runtime_set:
		projectSettings.currentProject.toolchains["msvc"].Linker().debug_runtime = True


def SetupReleaseTarget( ):
	"""Default release target."""
	if not projectSettings.currentProject._optLevel_set:
		SetOptimizationLevel( OptimizationLevel.Max )
	if not projectSettings.currentProject._debugLevel_set:
		SetDebugLevel( DebugLevel.Disabled )
		Toolchain("msvc").SetDebugLevel( DebugLevel.ExternalSymbols )

	AddDefines("NDEBUG")

	if not projectSettings.currentProject._outputDir_set:
		projectSettings.currentProject.outputDir = "{project.activeToolchainName}-{project.outputArchitecture}-{project.targetName}"
	if not projectSettings.currentProject._objDir_set:
		projectSettings.currentProject.objDir = os.path.join(projectSettings.currentProject.outputDir, "obj")
	if not projectSettings.currentProject.toolchains["msvc"].Compiler().debug_runtime_set:
		projectSettings.currentProject.toolchains["msvc"].Compiler().debug_runtime = False
	if not projectSettings.currentProject.toolchains["msvc"].Linker().debug_runtime_set:
		projectSettings.currentProject.toolchains["msvc"].Linker().debug_runtime = False


def _setupdefaults( ):
	RegisterToolchain( "gcc", toolchain_gcc.compiler_gcc, toolchain_gcc.linker_gcc )
	RegisterToolchain( "msvc", toolchain_msvc.compiler_msvc, toolchain_msvc.linker_msvc )
	RegisterToolchain( "android", toolchain_android.AndroidCompiler, toolchain_android.AndroidLinker )
	RegisterToolchain( "ios", toolchain_ios.iOSCompiler, toolchain_ios.iOSLinker )

	RegisterProjectGenerator( "qtcreator", project_generator_qtcreator.project_generator_qtcreator )
	RegisterProjectGenerator( "slickedit", project_generator_slickedit.project_generator_slickedit )
	RegisterProjectGenerator( "visualstudio", project_generator_visual_studio.project_generator_visual_studio )

	if platform.system( ) == "Windows":
		SetActiveToolchain( "msvc" )
	else:
		SetActiveToolchain( "gcc" )

	target( "debug" )( SetupDebugTarget )
	target( "release" )( SetupReleaseTarget )

_guiModule = None

sysExit = sys.exit

def Done( code = 0 ):
	"""
	Exit the build process early

	:param code: Exit code to exit with
	:type code: int
	"""
	Exit( code )


def Exit( code = 0 ):
	"""
	Exit the build process early

	:param code: Exit code to exit with
	:type code: int
	"""
	#global _guiModule
	#if _guiModule:
	#	_guiModule.stop()

	if not imp.lock_held():
		imp.acquire_lock()

	sysExit( code )


ARG_NOT_SET = type( "ArgNotSetType", (), { } )( )

_options = []

helpMode = False


def GetOption( option ):
	"""
	Retrieve the given option from the parsed command line arguments.

	:type option: str
	:param option: The name of the option, without any preceding dashes.
	ArgParse replaces dashes with underscores, but csbuild will accept dashes and automatically handle the conversion
	internally.

	:return: The given argument, if it exists. If the argument has never been specified, returns csbuild.ARG_NOT_SET.
	If --help has been specified, this will ALWAYS return csbuild.ARG_NOT_SET for user-specified arguments.
	Handle csbuild.ARG_NOT_SET to prevent code from being unintentionally run with --help.
	"""
	global args
	if not helpMode:
		newparser = argparse.ArgumentParser( )
		global _options
		for opt in _options:
			newparser.add_argument( *opt[0], **opt[1] )
		_options = []
		newargs, remainder = newparser.parse_known_args( args.remainder )
		args.__dict__.update( newargs.__dict__ )
		args.remainder = remainder

	option = option.replace( "-", "_" )
	if hasattr( args, option ):
		return getattr( args, option )
	else:
		return ARG_NOT_SET


def AddOption( *args, **kwargs ):
	"""
	Adds an option to the argument parser.
	The syntax for this is identical to the ArgParse add_argument syntax; see
	the :argparse: documentation
	"""
	_options.append( [args, kwargs] )


def GetArgs( ):
	"""
	Gets all of the arguments parsed by the argument parser.

	:return: an argparse.Namespace object
	:rtype: argparse.Namespace
	"""
	global args
	if not helpMode:
		newparser = argparse.ArgumentParser( )
		global _options
		for opt in _options:
			newparser.add_argument( *opt[0], **opt[1] )
		_options = []
		newargs, remainder = newparser.parse_known_args( args.remainder )
		args.__dict__.update( newargs.__dict__ )
		args.remainder = remainder
	return vars( args )


def GetArgDefault( argname ):
	"""
	Gets the default argument for the requested option

	:type argname: str
	:param argname: the name of the option
	"""
	global parser
	return parser.get_default( argname )


def GetTargetList():
	"""
	Get the list of targets currently being built.

	If no target has been specified (the default is being used), this list is empty.

	:return: The list of targets
	:rtype: list[str]
	"""
	return _shared_globals.target_list


class _dummy( object ):
	def __setattr__( self, key, value ):
		pass
	def __getattribute__( self, item ):
		return ""


def _execfile( file, glob, loc ):
	if sys.version_info >= (3, 0):
		with open( file, "r" ) as f:
			exec (f.read( ), glob, loc)
	else:
		execfile( file, glob, loc )


mainFile = ""
mainFileDir = ""

def _run( ):

	_setupdefaults( )

	global args
	args = _dummy( )

	global mainFile
	global mainFileDir
	mainFile = sys.modules['__main__'].__file__
	if mainFile is not None:
		mainFileDir = os.path.abspath( os.path.dirname( mainFile ) )
		if mainFileDir:
			os.chdir( mainFileDir )
			mainFile = os.path.basename( os.path.abspath( mainFile ) )
		else:
			mainFileDir = os.path.abspath( os.getcwd( ) )
		scriptFiles.append(os.path.join(mainFileDir, mainFile))
		if "-h" in sys.argv or "--help" in sys.argv:
			global helpMode
			helpMode = True
			_execfile( mainFile, _shared_globals.makefile_dict, _shared_globals.makefile_dict )
			_shared_globals.sortedProjects = _utils.SortProjects( _shared_globals.tempprojects )

	else:
		log.LOG_ERROR( "CSB cannot be run from the interactive console." )
		Exit( 1 )

	csbDir = os.path.join(mainFileDir, ".csbuild")
	if not os.path.exists(csbDir):
		os.makedirs(csbDir)

	_shared_globals.cacheDirectory = os.path.join(csbDir, "cache")
	if not os.path.exists(_shared_globals.cacheDirectory):
		os.makedirs(_shared_globals.cacheDirectory)

	logDirectory = os.path.join(csbDir, "log")
	if not os.path.exists(logDirectory):
		os.makedirs(logDirectory)

	logFile = os.path.join(logDirectory, "build.log")

	logBackup = "{}.4".format(logFile)
	if os.path.exists(logBackup):
		os.remove(logBackup)

	for i in range(3,0,-1):
		logBackup = "{}.{}".format(logFile, i)
		if os.path.exists(logBackup):
			newBackup = "{}.{}".format(logFile, i+1)
			os.rename(logBackup, newBackup)

	if os.path.exists(logFile):
		logBackup = "{}.1".format(logFile)
		os.rename(logFile, logBackup)

	_shared_globals.logFile = open(logFile, "w")

	epilog = "    ------------------------------------------------------------    \n\nProjects available in this makefile (listed in build order):\n\n"

	projtable = [[]]
	i = 1
	j = 0

	maxcols = min( math.floor( len( _shared_globals.sortedProjects ) / 4 ), 4 )

	for proj in _shared_globals.sortedProjects:
		projtable[j].append( proj.name )
		if i < maxcols:
			i += 1
		else:
			projtable.append( [] )
			i = 1
			j += 1

	if projtable:
		maxlens = [15] * len( projtable[0] )
		for index in range( len( projtable ) ):
			col = projtable[index]
			for subindex in range( len( col ) ):
				maxlens[subindex] = max( maxlens[subindex], len( col[subindex] ) )

		for index in range( len( projtable ) ):
			col = projtable[index]
			for subindex in range( len( col ) ):
				item = col[subindex]
				epilog += "  "
				epilog += item
				for space in range( maxlens[subindex] - len( item ) ):
					epilog += " "
				epilog += "  "
			epilog += "\n"

	epilog += "\nTargets available in this makefile:\n\n"

	targtable = [[]]
	i = 1
	j = 0

	maxcols = min( math.floor( len( _shared_globals.alltargets ) / 4 ), 4 )

	for targ in _shared_globals.alltargets:
		targtable[j].append( targ )
		if i < maxcols:
			i += 1
		else:
			targtable.append( [] )
			i = 1
			j += 1

	if targtable:
		maxlens = [15] * len( targtable[0] )
		for index in range( len( targtable ) ):
			col = targtable[index]
			for subindex in range( len( col ) ):
				maxlens[subindex] = max( maxlens[subindex], len( col[subindex] ) )

		for index in range( len( targtable ) ):
			col = targtable[index]
			for subindex in range( len( col ) ):
				item = col[subindex]
				epilog += "  "
				epilog += item
				for space in range( maxlens[subindex] - len( item ) ):
					epilog += " "
				epilog += "  "
			epilog += "\n"

	global parser
	parser = argparse.ArgumentParser(
		prog = mainFile, epilog = epilog, formatter_class = argparse.RawDescriptionHelpFormatter )

	group = parser.add_mutually_exclusive_group( )
	group.add_argument( '-t', '--target', action='append', help = 'Target(s) for build', default=[])
	group.add_argument( '--at', "--all-targets", action = "store_true", help = "Build all targets" )

	parser.add_argument(
		"-p",
		"--project",
		action = "append",
		help = "Build only the specified project. May be specified multiple times."
	)

	group = parser.add_mutually_exclusive_group( )
	group.add_argument( '-c', '--clean', action = "store_true", help = 'Clean the target build' )
	group.add_argument( '--install', action = "store_true", help = 'Install the target build' )
	group.add_argument( '--install-headers', action = "store_true", help = 'Install only headers for the target build' )
	group.add_argument( '--install-output', action = "store_true", help = 'Install only the output for the target build' )
	group.add_argument( '--version', action = "store_true", help = "Print version information and exit" )
	group.add_argument( '-r', '--rebuild', action = "store_true", help = 'Clean the target build and then build it' )
	group2 = parser.add_mutually_exclusive_group( )
	group2.add_argument( '-v', '--verbose', action = "store_const", const = 0, dest = "quiet",
		help = "Verbose. Enables additional INFO-level logging.", default = 1 )
	group2.add_argument( '-q', '--quiet', action = "store_const", const = 2, dest = "quiet",
		help = "Quiet. Disables all logging except for WARN and ERROR.", default = 1 )
	group2.add_argument( '-qq', '--very-quiet', action = "store_const", const = 3, dest = "quiet",
		help = "Very quiet. Disables all csb-specific logging.", default = 1 )
	parser.add_argument( "-j", "--jobs", action = "store", dest = "jobs", type = int, help = "Number of simultaneous build processes" )

	parser.add_argument(
		"-l",
		"--linker-jobs",
		action = "store",
		dest = "linker_jobs",
		type = int,
		help = "Max number of simultaneous link processes. (If not specified, same value as -j.)"
		"Note that this pool is shared with build threads, and linker will only get one thread from the pool until compile threads start becoming free."
		"This value only specifies a maximum."
	)
	parser.add_argument( "-g", "--gui", action = "store_true", dest = "gui", help = "Show GUI while building (experimental)")
	parser.add_argument( "--auto-close-gui", action = "store_true", help = "Automatically close the gui on build success (will stay open on failure)")
	parser.add_argument("--profile", action="store_true", help="Collect detailed line-by-line profiling information on compile time. --gui option required to see this information.")
	parser.add_argument( '--show-commands', help = "Show all commands sent to the system.", action = "store_true" )
	parser.add_argument( '--force-color', help = "Force color on or off.",
		action = "store", choices = ["on", "off"], default = None, const = "on", nargs = "?" )
	parser.add_argument( '--force-progress-bar', help = "Force progress bar on or off.",
		action = "store", choices = ["on", "off"], default = None, const = "on", nargs = "?" )
	parser.add_argument( '--prefix', help = "install prefix (default /usr/local)", action = "store" )
	parser.add_argument( '--libdir', help = "install location for libraries (default {prefix}/lib)", action = "store" )
	parser.add_argument( '--incdir', help = "install prefix (default {prefix}/include)", action = "store" )

	group = parser.add_mutually_exclusive_group( )
	group.add_argument( '-o', '--toolchain', help = "Toolchain to use for compiling.",
		choices = _shared_globals.alltoolchains, default=[], action = "append" )
	group.add_argument( "--ao", '--all-toolchains', help="Build with all toolchains", action = "store_true" )

	group = parser.add_mutually_exclusive_group( )

	for toolchainName, toolchainArchStrings in _shared_globals.allToolchainArchStrings.items():
		archStringLong = "--" + toolchainArchStrings[0]
		archStringShort = "--" + toolchainArchStrings[1]
		parser.add_argument(archStringLong, archStringShort, help = "Architecture to compile for the {} toolchain.".format(toolchainName), action = "append")

	group.add_argument("-a", "--architecture", "--arch", help = 'Architecture to compile for each toolchain.', action = "append")
	group.add_argument("--aa", "--all-architectures", "--all-arch", action = "store_true", help = "Build all architectures supported by this toolchain" )

	parser.add_argument(
		"--stop-on-error",
		help = "Stop compilation after the first error is encountered.",
		action = "store_true"
	)
	parser.add_argument( '--no-precompile', help = "Disable precompiling globally, affects all projects",
		action = "store_true" )
	parser.add_argument( '--no-chunks', help = "Disable chunking globally, affects all projects",
		action = "store_true" )
	parser.add_argument( '--dg', '--dependency-graph', help="Generate dependency graph", action="store_true")
	parser.add_argument( '--with-libs', help="Include linked libraries in dependency graph", action="store_true" )

	group = parser.add_argument_group( "Solution generation", "Commands to generate a solution" )
	group.add_argument( '--generate-solution', help = "Generate a solution file for use with the given IDE.",
		choices = _shared_globals.allgenerators.keys( ), action = "store" )
	group.add_argument( '--solution-path',
		help = "Path to output the solution file (default is ./Solutions/<solutiontype>)", action = "store",
		default = "" )
	group.add_argument( '--solution-name', help = "Name of solution output file (default is csbuild)", action = "store",
		default = "csbuild" )
	group.add_argument( '--solution-args', help = 'Arguments passed to the build script executed by the solution',
		action = "store", default = "")

	#TODO: Additional args here
	for chain in _shared_globals.alltoolchains.items( ):
		chainInst = chain[1]()
		argfuncs = set()
		for tool in chainInst.tools.values():
			if(
				hasattr(tool.__class__, "AdditionalArgs")
				and tool.__class__.AdditionalArgs != toolchain.compilerBase.AdditionalArgs
				and tool.__class__.AdditionalArgs != toolchain.linkerBase.AdditionalArgs
			):
				argfuncs.add(tool.__class__.AdditionalArgs)

		if argfuncs:
			group = parser.add_argument_group( "Options for toolchain {}".format( chain[0] ) )
			for func in argfuncs:
				func( group )

	for gen in _shared_globals.allgenerators.items( ):
		if gen[1].AdditionalArgs != project_generator.project_generator.AdditionalArgs:
			group = parser.add_argument_group( "Options for solution generator {}".format( gen[0] ) )
			gen[1].AdditionalArgs( group )

	if _options:
		group = parser.add_argument_group( "Local makefile options" )
		for option in _options:
			group.add_argument( *option[0], **option[1] )

	args, remainder = parser.parse_known_args( )
	args.remainder = remainder

	# Note:
	# The reason for this line of code is that the import lock, in the way that CSBuild operates, prevents
	# us from being able to call subprocess.Popen() or any other process execution function other than os.popen().
	# This exists to prevent multiple threads from importing at the same time, so... Within csbuild, never import
	# within any thread but the main thread. Any import statements used by threads should be in the module those
	# thread objects are defined in so they're completed in full on the main thread before that thread starts.
	#
	# After this point, the LOCK IS RELEASED. Importing is NO LONGER THREAD-SAFE. DON'T DO IT.
	if imp.lock_held():
		imp.release_lock()

	if args.version:
		print("CSBuild version {}".format( __version__ ))
		print(__copyright__)
		print("Code by {}".format( __author__ ))
		print("Additional credits: {}".format( ", ".join( __credits__ ) ))
		print("\nMaintainer: {} - {}".format( __maintainer__, __email__ ))
		return

	_shared_globals.CleanBuild = args.clean
	_shared_globals.do_install = args.install or args.install_headers or args.install_output
	_shared_globals.quiet = args.quiet
	_shared_globals.show_commands = args.show_commands
	_shared_globals.rebuild = args.rebuild or args.profile
	if args.gui and _shared_globals.CleanBuild:
		log.LOG_INFO("The GUI is currently disabled when performing a clean.");
		args.gui = False
	if args.profile and not args.gui:
		log.LOG_WARN("Profile mode has no effect without --gui. Disabling --profile.")
		args.profile = False
	if args.profile and not args.rebuild:
		log.LOG_WARN("A full build is required to collect profiling information. Forcing --rebuild flag.")
	project_build_list = None
	if args.project:
		project_build_list = set( args.project )

	if args.force_color == "on":
		_shared_globals.color_supported = True
	elif args.force_color == "off":
		_shared_globals.color_supported = False

	_shared_globals.forceProgressBar = args.force_progress_bar

	if args.prefix:
		_shared_globals.install_prefix = os.path.abspath(args.prefix)
	if args.libdir:
		_shared_globals.install_libdir = args.libdir
	if args.incdir:
		_shared_globals.install_incdir = args.incdir

	_shared_globals.install_libdir = os.path.abspath(_shared_globals.install_libdir.format(prefix=_shared_globals.install_prefix))
	_shared_globals.install_incdir = os.path.abspath(_shared_globals.install_incdir.format(prefix=_shared_globals.install_prefix))

	if args.jobs:
		_shared_globals.max_threads = args.jobs
		_shared_globals.semaphore = threading.BoundedSemaphore( value = _shared_globals.max_threads )

	if args.linker_jobs:
		_shared_globals.max_linker_threads = max(args.linker_jobs, _shared_globals.max_threads)
		_shared_globals.link_semaphore = threading.BoundedSemaphore( value = _shared_globals.max_linker_threads )

	_shared_globals.profile = args.profile
	_shared_globals.disable_chunks = args.no_chunks
	_shared_globals.disable_precompile = args.no_precompile or args.profile

	_shared_globals.stopOnError = args.stop_on_error

	if args.generate_solution is not None:
		args.at = True
		args.aa = True
		#args.ao = True

	if args.at:
		_shared_globals.target_list = list(_shared_globals.alltargets)
	elif args.target:
		_shared_globals.target_list = args.target

	#there's an execfile on this up above, but if we got this far we didn't pass --help or -h, so we need to do this here instead
	_execfile( mainFile, _shared_globals.makefile_dict, _shared_globals.makefile_dict )

	parser.parse_args(args.remainder)

	def BuildWithToolchain( chain ):

		def BuildWithTarget( target ):
			if target is not None:
				_shared_globals.target = target.lower( )

			def BuildWithArchitecture( project, architecture ):

				_shared_globals.allarchitectures.add(architecture)
				os.chdir( project.scriptPath )

				newproject = project.copy()

				if _shared_globals.target:
					newproject.targetName = _shared_globals.target
				else:
					newproject.targetName = projectSettings.currentProject.defaultTarget

				if newproject.targetName not in newproject.targets:
					log.LOG_INFO( "Project {} has no rules specified for target {}. Skipping.".format( newproject.name,
						newproject.targetName ) )
					return

				projectSettings.currentProject = newproject

				SetOutputArchitecture(architecture)

				for targetFunc in newproject.targets[newproject.targetName]:
					targetFunc( )

				if newproject.outputArchitecture in newproject.archFuncs:
					for archFunc in newproject.archFuncs[newproject.outputArchitecture]:
						archFunc()

				for file in newproject.fileOverrides:
					projCopy = newproject.copy()
					projectSettings.currentProject = projCopy

					for func in newproject.fileOverrides[file]:
						func()

					newproject.fileOverrideSettings[file] = projCopy

				if newproject.targetName not in newproject.targets:
					log.LOG_INFO( "Project {} has no rules specified for target {}. Skipping.".format( newproject.name,
						newproject.targetName ) )
					return

				projectSettings.currentProject = newproject

				SetOutputArchitecture(architecture)

				for targetFunc in newproject.targets[newproject.targetName]:
					targetFunc( )

				if newproject.outputArchitecture in newproject.archFuncs:
					for archFunc in newproject.archFuncs[newproject.outputArchitecture]:
						archFunc()

				for file in newproject.fileOverrides:
					projCopy = newproject.copy()
					projectSettings.currentProject = projCopy

					for func in newproject.fileOverrides[file]:
						func()

					newproject.fileOverrideSettings[file] = projCopy

				projectSettings.currentProject = newproject

				alteredLinkDepends = []
				alteredLinkDependsIntermediate = []
				alteredLinkDependsFinal = []
				alteredSrcDepends = []
				alteredSrcDependsIntermediate = []
				alteredSrcDependsFinal = []

				for depend in newproject.linkDepends:
					if depend.includeToolchains and newproject.activeToolchainName not in depend.includeToolchains:
						continue
					if depend.includeArchitectures and newproject.outputArchitecture not in depend.includeArchitectures:
						continue
					if depend.excludeToolchains and newproject.activeToolchainName in depend.excludeToolchains:
						continue
					if depend.excludeArchitectures and newproject.outputArchitecture in depend.excludeArchitectures:
						continue
					alteredLinkDepends.append( "{}@{}#{}${}".format( depend.libName, projectSettings.currentProject.targetName, projectSettings.currentProject.outputArchitecture, projectSettings.currentProject.activeToolchainName ) )

				for depend in newproject.linkDependsIntermediate:
					if depend.includeToolchains and newproject.activeToolchainName not in depend.includeToolchains:
						continue
					if depend.includeArchitectures and newproject.outputArchitecture not in depend.includeArchitectures:
						continue
					if depend.excludeToolchains and newproject.activeToolchainName in depend.excludeToolchains:
						continue
					if depend.excludeArchitectures and newproject.outputArchitecture in depend.excludeArchitectures:
						continue
					alteredLinkDependsIntermediate.append( "{}@{}#{}${}".format( depend.libName, projectSettings.currentProject.targetName, projectSettings.currentProject.outputArchitecture, projectSettings.currentProject.activeToolchainName ) )

				for depend in newproject.linkDependsFinal:
					if depend.includeToolchains and newproject.activeToolchainName not in depend.includeToolchains:
						continue
					if depend.includeArchitectures and newproject.outputArchitecture not in depend.includeArchitectures:
						continue
					if depend.excludeToolchains and newproject.activeToolchainName in depend.excludeToolchains:
						continue
					if depend.excludeArchitectures and newproject.outputArchitecture in depend.excludeArchitectures:
						continue
					alteredLinkDependsFinal.append( "{}@{}#{}${}".format( depend.libName, projectSettings.currentProject.targetName, projectSettings.currentProject.outputArchitecture, projectSettings.currentProject.activeToolchainName ) )


				for depend in newproject.srcDepends:
					if depend.includeToolchains and newproject.activeToolchainName not in depend.includeToolchains:
						continue
					if depend.includeArchitectures and newproject.outputArchitecture not in depend.includeArchitectures:
						continue
					if depend.excludeToolchains and newproject.activeToolchainName in depend.excludeToolchains:
						continue
					if depend.excludeArchitectures and newproject.outputArchitecture in depend.excludeArchitectures:
						continue
					alteredSrcDepends.append( "{}@{}#{}${}".format( depend.libName, projectSettings.currentProject.targetName, projectSettings.currentProject.outputArchitecture, projectSettings.currentProject.activeToolchainName ) )

				for depend in newproject.srcDependsIntermediate:
					if depend.includeToolchains and newproject.activeToolchainName not in depend.includeToolchains:
						continue
					if depend.includeArchitectures and newproject.outputArchitecture not in depend.includeArchitectures:
						continue
					if depend.excludeToolchains and newproject.activeToolchainName in depend.excludeToolchains:
						continue
					if depend.excludeArchitectures and newproject.outputArchitecture in depend.excludeArchitectures:
						continue
					alteredSrcDependsIntermediate.append( "{}@{}#{}${}".format( depend.libName, projectSettings.currentProject.targetName, projectSettings.currentProject.outputArchitecture, projectSettings.currentProject.activeToolchainName ) )

				for depend in newproject.srcDependsFinal:
					if depend.includeToolchains and newproject.activeToolchainName not in depend.includeToolchains:
						continue
					if depend.includeArchitectures and newproject.outputArchitecture not in depend.includeArchitectures:
						continue
					if depend.excludeToolchains and newproject.activeToolchainName in depend.excludeToolchains:
						continue
					if depend.excludeArchitectures and newproject.outputArchitecture in depend.excludeArchitectures:
						continue
					alteredSrcDependsFinal.append( "{}@{}#{}${}".format( depend.libName, projectSettings.currentProject.targetName, projectSettings.currentProject.outputArchitecture, projectSettings.currentProject.activeToolchainName ) )

				newproject.linkDepends = alteredLinkDepends
				newproject.linkDependsIntermediate = alteredLinkDependsIntermediate
				newproject.linkDependsFinal = alteredLinkDependsFinal
				newproject.srcDepends = alteredSrcDepends
				newproject.srcDependsIntermediate = alteredSrcDependsIntermediate
				newproject.srcDependsFinal = alteredSrcDependsFinal

				newproject.key = "{}@{}#{}${}".format( newproject.name, newproject.targetName, newproject.outputArchitecture, newproject.activeToolchainName )
				_shared_globals.projects.update( { newproject.key: newproject } )

			for project in _shared_globals.tempprojects.values( ):

				if chain is not None:
					_shared_globals.selectedToolchains.add(chain)
					project.activeToolchainName = chain

				if project.supportedToolchains and project.activeToolchainName not in project.supportedToolchains:
					continue

				project.activeToolchain = project.toolchains[project.activeToolchainName]

				validArchList = set(project.activeToolchain.GetValidArchitectures())
				cmdLineGlobalArchList = args.architecture
				cmdLineToolchainArchList = args.__dict__[_shared_globals.allToolchainArchStrings[project.activeToolchainName][0].replace("-", "_")]
				cmdLineArchList = set()
				if cmdLineGlobalArchList:
					cmdLineArchList.update(cmdLineGlobalArchList)
				if cmdLineToolchainArchList:
					cmdLineArchList.update(cmdLineToolchainArchList)
				if project.supportedArchitectures:
					validArchList &= project.supportedArchitectures
				if not validArchList:
					log.LOG_ERROR("Project {} does not support any architectures supported by toolchain {}".format(project.name, project.activeToolchainName))
				if cmdLineArchList:
					for arch in cmdLineArchList:
						if arch not in validArchList:
							log.LOG_ERROR("Toolchain {} does not support architecture {}".format(project.activeToolchainName, arch))
							Exit(1)
						BuildWithArchitecture(project, arch)
				elif args.aa:
					for arch in validArchList:
						BuildWithArchitecture(project, arch)
				else:
					BuildWithArchitecture(project, project.activeToolchain.Compiler().GetDefaultArchitecture())

		if args.at:
			for target in _shared_globals.alltargets:
				BuildWithTarget( target )
		elif args.target:
			for target in args.target:
				BuildWithTarget( target )
			for target in args.target:
				if target.lower( ) not in _shared_globals.alltargets:
					log.LOG_ERROR( "Unknown target: {}".format( target ) )
					return False
		else:
			BuildWithTarget( None )

		return True

	if args.ao:
		_shared_globals.selectedToolchains = set( ) # Reset the selected toolchains.
		for chain in _shared_globals.alltoolchains:
			if not BuildWithToolchain( chain ):
				return
	elif args.toolchain:
		_shared_globals.selectedToolchains = set( ) # Reset the selected toolchains.
		for chain in args.toolchain:
			if chain.lower() not in _shared_globals.alltoolchains:
				log.LOG_ERROR( "Unknown toolchain: {}".format( chain ) )
				return
			if not BuildWithToolchain( chain ):
				return
	else:
		BuildWithToolchain( None )

	os.chdir( mainFileDir )

	if project_build_list:
		for proj in _shared_globals.projects.keys( ):
			if proj.rsplit( "@", 1 )[0] in project_build_list:
				_shared_globals.project_build_list.add( proj )
	else:
		_shared_globals.project_build_list = set(_shared_globals.projects.keys())

	for projName in _shared_globals.projects:
		project = _shared_globals.projects[projName]

		flats_added = {projName}

		def add_flats(deps):
			for dep in deps:
				if dep in flats_added:
					continue
				flats_added.add(dep)
				project.flattenedDepends.add(dep)
				proj = _shared_globals.projects[dep]
				add_flats(proj.linkDepends)
				add_flats(proj.linkDependsIntermediate)
				add_flats(proj.linkDependsFinal)


		depends = project.linkDepends + project.linkDependsIntermediate + project.linkDependsFinal
		for dep in depends:
			if dep not in _shared_globals.projects:
				log.LOG_ERROR("Project {} references unknown dependency {}".format(project.name, dep.rsplit("@")[0]))
				return
			proj = _shared_globals.projects[dep]
			project.flattenedDepends.add(dep)
			add_flats(proj.linkDepends)
			add_flats(proj.linkDependsFinal)
			add_flats(proj.linkDependsIntermediate)

		project.finalizeSettings()

		if project.type == ProjectType.Application:
			project.linkDepends += project.linkDependsFinal
			project.linkDependsFinal = []

	for projName in _shared_globals.projects:
		project = _shared_globals.projects[projName]

		intermediates_added = {projName}
		finals_added = {projName}

		def add_intermediates(deps):
			for dep in deps:
				if dep in intermediates_added:
					continue
				intermediates_added.add(dep)
				project.reconciledLinkDepends.add(dep)
				proj = _shared_globals.projects[dep]
				add_finals(proj.linkDependsIntermediate)

		def add_finals(deps):
			for dep in deps:
				if dep in finals_added:
					continue
				finals_added.add(dep)
				project.reconciledLinkDepends.add(dep)
				proj = _shared_globals.projects[dep]
				add_finals(proj.linkDependsFinal)


		depends = project.linkDepends
		if args.dg:
			depends = project.linkDepends + project.linkDependsIntermediate + project.linkDependsFinal

		for dep in depends:
			if dep not in _shared_globals.projects:
				log.LOG_ERROR("Project {} references unknown dependency {}".format(project.name, dep.rsplit("@")[0]))
				return
			proj = _shared_globals.projects[dep]
			project.reconciledLinkDepends.add(dep)
			if args.dg:
				add_finals(proj.linkDependsFinal)
				add_intermediates(proj.linkDependsIntermediate)
			elif project.type == ProjectType.Application:
				add_finals(proj.linkDependsFinal)
			else:
				add_intermediates(proj.linkDependsIntermediate)

		project.finalizeSettings2()

	already_errored_link = { }
	already_errored_source = { }

	def insert_depends( proj, projList, already_inserted = set( ) ):
		already_inserted.add( proj.key )
		if proj not in already_errored_link:
			already_errored_link[proj] = set( )
			already_errored_source[proj] = set( )
		for depend in proj.reconciledLinkDepends:
			if depend in already_inserted:
				log.LOG_WARN(
					"Circular dependencies detected: {0} and {1} in linkDepends".format( depend.rsplit( "@", 1 )[0],
						proj.name ) )
				continue

			if depend not in _shared_globals.projects:
				if depend not in already_errored_link[proj]:
					log.LOG_ERROR(
						"Project {} references non-existent link dependency {}".format( proj.name,
							depend.rsplit( "@", 1 )[0] ) )
					already_errored_link[proj].add( depend )
					proj.reconciledLinkDepends.remove(depend)
				continue

			projData = _shared_globals.projects[depend]
			projList[depend] = projData

			insert_depends( projData, projList )

		for index in range( len( proj.srcDepends ) ):
			depend = proj.srcDepends[index]

			if depend in already_inserted:
				log.LOG_WARN(
					"Circular dependencies detected: {0} and {1} in srcDepends".format( depend.rsplit( "@", 1 )[0],
						proj.name ) )
				continue

			if depend not in _shared_globals.projects:
				if depend not in already_errored_link[proj]:
					log.LOG_ERROR(
						"Project {} references non-existent link dependency {}".format( proj.name,
							depend.rsplit( "@", 1 )[0] ) )
					already_errored_link[proj].add( depend )
					del proj.srcDepends[index]
				continue

			projData = _shared_globals.projects[depend]
			projList[depend] = projData

			insert_depends( projData, projList )
		already_inserted.remove( proj.key )

	if _shared_globals.project_build_list:
		newProjList = { }
		for proj in _shared_globals.project_build_list:
			projData = _shared_globals.projects[proj]
			newProjList[proj] = projData
			insert_depends( projData, newProjList )
		_shared_globals.projects = newProjList

	_shared_globals.sortedProjects = _utils.SortProjects( _shared_globals.projects )

	if args.dg:
		builder = 'digraph G {\n\tlayout="neato";\n\toverlap="false";\n\tsplines="spline"\n'
		colors = [
			"#ff0000", "#cc5200", "#b2742d", "#858c23", "#20802d",
			"#00ffcc", "#39c3e6", "#205380", "#003380", "#38008c",
			"#ff40d9", "#e53967", "#f20000", "#7f4620", "#cca300",
			"#66ff00", "#00cc6d", "#36d9ce", "#007a99", "#0061f2",
			"#0000f2", "#cc00ff", "#d9368d", "#7f202d", "#991400",
			"#f28100", "#dae639", "#69bf30", "#269973", "#208079",
			"#00a2f2", "#397ee6", "#0000e6", "#8d29a6", "#990052"
		]
		idx = 0
		libs_drawn = set()
		for project in _shared_globals.sortedProjects:
			color = colors[idx]
			idx += 1
			if idx == len(colors):
				idx = 0
			builder += '\t{0} [shape="{1}" color="{2}" style="filled" fillcolor="{2}30"];\n'.format(project.name, "box3d" if project.type == ProjectType.Application else "oval", color)
			for dep in project.linkDepends:
				otherProj = _shared_globals.projects[dep]
				builder += '\t{} -> {} [color="{}"];\n'.format(project.name, otherProj.name, color)
			for dep in project.linkDependsIntermediate:
				otherProj = _shared_globals.projects[dep]
				builder += '\t{} -> {} [color="{}B0" style="dashed" arrowhead="onormal"];\n'.format(project.name, otherProj.name, color)
			for dep in project.linkDependsFinal:
				otherProj = _shared_globals.projects[dep]
				builder += '\t{} -> {} [color="{}B0" style="dashed" arrowhead="onormal"];\n'.format(project.name, otherProj.name, color)

			if args.with_libs:
				project.activeToolchain = project.toolchains[project.activeToolchainName]
				project.activeToolchain.SetActiveTool("linker")
				for lib in project.libraries:
					lib = lib.replace("-", "_")
					if lib not in libs_drawn:
						builder += '\t{} [shape="diamond" color="#303030" style="filled" fillcolor="#D0D0D080"];\n'.format(lib)
						libs_drawn.add(lib)
					builder += '\t{} -> {} [color="{}" style="dotted" arrowhead="onormal"];\n'.format(project.name, lib, color)
		builder += "}\n"
		with open("depends.gv", "w") as f:
			f.write(builder)
		log.LOG_BUILD("Wrote depends.gv")
		try:
			from graphviz import Digraph
		except:
			log.LOG_WARN("graphviz library not found. You can open depends.gv with graphviz or a similar dot viewer to view the graph, or install graphviz with pip install graphviz.")
		else:
			graph = Digraph(comment="CSBuild Dependency Graph", format="png", engine="dot", filename="depends")
			Digraph.source=property(lambda self: builder)
			graph.render("depends.gv", view=True)
			log.LOG_BUILD("Wrote depends.png")
		return

	#headerCacheFile = os.path.join(_shared_globals.cacheDirectory, "header_info.csbc")
	#if os.path.exists(headerCacheFile):
	#	log.LOG_BUILD("Loading cache data...")
	#	with open(headerCacheFile, "rb") as f:
	#		_shared_globals.allheaders = pickle.load(f)
	#	mtime = os.path.getmtime(headerCacheFile)
	#	for header in _shared_globals.allheaders.keys():
	#		if not header:
	#			continue
	#		try:
	#			htime = os.path.getmtime(header)
	#			if htime > mtime:
	#				del _shared_globals.allheaders[header]
	#		except:
	#			del _shared_globals.allheaders[header]

	for proj in _shared_globals.sortedProjects:
		proj.prepareBuild( )

	#with open(headerCacheFile, "wb") as f:
	#	pickle.dump(_shared_globals.allheaders, f, 2)

	_utils.CheckVersion( )

	totaltime = time.time( ) - _shared_globals.starttime
	totalmin = math.floor( totaltime / 60 )
	totalsec = math.floor( totaltime % 60 )
	_utils.ChunkedBuild( )
	_utils.PreparePrecompiles( )
	log.LOG_BUILD( "Task preparation took {0}:{1:02}".format( int( totalmin ), int( totalsec ) ) )


	if args.gui:
		_shared_globals.autoCloseGui = args.auto_close_gui
		from . import _gui
		global _guiModule
		_guiModule = _gui

	if args.generate_solution is not None:
		if not args.solution_path:
			args.solution_path = os.path.join( ".", "Solutions", args.generate_solution )
		if args.generate_solution not in _shared_globals.project_generators:
			log.LOG_ERROR( "No solution generator present for solution of type {}".format( args.generate_solution ) )
			Exit( 0 )
		generator = _shared_globals.project_generators[args.generate_solution]( args.solution_path, args.solution_name, args.solution_args )

		generator.WriteProjectFiles( )
		log.LOG_BUILD( "Done" )

	elif _shared_globals.CleanBuild:
		_clean( )
	elif args.install:
		_install( )
	elif args.install_headers:
		_installHeaders()
	elif args.install_output:
		_installOutput()
	elif _shared_globals.rebuild:
		_clean( )
		_make( )
	else:
		_make( )

	#Print out any errors or warnings incurred so the user doesn't have to scroll to see what went wrong
	if _shared_globals.warnings:
		print("\n")
		log.LOG_WARN( "Warnings encountered during build:" )
		for warn in _shared_globals.warnings[0:-1]:
			log.LOG_WARN( warn )
	if _shared_globals.errors:
		print("\n")
		log.LOG_ERROR( "Errors encountered during build:" )
		for error in _shared_globals.errors[0:-1]:
			log.LOG_ERROR( error )

	if not _shared_globals.build_success:
		Exit( 1 )
	else:
		Exit( 0 )

#Regular sys.exit can't be called because we HAVE to reacquore the import lock at exit.
#We stored sys.exit earlier, now we overwrite it to call our wrapper.
sys.exit = Exit

try:
	if not hasattr(sys, "runningSphinx"):
		_run( )
		Exit( 0 )
except Exception as e:
	if not imp.lock_held():
		imp.acquire_lock()
	raise
