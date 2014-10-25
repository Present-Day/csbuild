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
**Toolchain Module**

Defines the base class for creating custom toolchains
"""

from abc import abstractmethod, ABCMeta
import glob
import os
import platform
from . import log
from . import _shared_globals
import csbuild


class ClassCombiner( object ):
	"""
	Represents the combined return value of a multi-object accessor.

	:ivar objs: The objects contained within the combined class
	@itype objs: list[object]
	"""
	def __init__( self, objs ):
		self.objs = objs


	def __getattr__( self, name ):
		funcs = []
		for obj in self.objs:
			funcs.append( getattr( obj, name ) )


		def combined_func( *args, **kwargs ):
			rets = []
			for func in funcs:
				rets.append(func( *args, **kwargs ))
			if rets:
				if len(rets) == 1:
					return rets[0]
				else:
					return ClassCombiner(rets)


		return combined_func

class SettingsOverrider( object ):
	def __init__(self):
		self._settingsOverrides = {}

	def copy(self):
		ret = self.__class__()

		for kvp in self._settingsOverrides.items( ):
			if isinstance( kvp[1], list ):
				ret._settingsOverrides[kvp[0]] = list( kvp[1] )
			elif isinstance( kvp[1], dict ):
				ret._settingsOverrides[kvp[0]] = dict( kvp[1] )
			elif isinstance( kvp[1], set ):
				ret._settingsOverrides[kvp[0]] = set( kvp[1] )
			elif isinstance( kvp[1], csbuild.projectSettings.projectSettings.UserData ):
				ret._settingsOverrides[kvp[0]] = kvp[1].copy()
			else:
				ret._settingsOverrides[kvp[0]] = kvp[1]

		return ret

	def EnableOutputInstall( self ):
		"""
		Enables installation of the compiled output file.
		Default target is /usr/local/lib, unless the --prefix option is specified.
		If --prefix is specified, the target will be *{prefix*}/lib

		:type s: str
		:param s: Override directory - i.e., if you specify this as "libraries", the libraries will be installed
		to *{prefix*}/libraries.
		"""
		self._settingsOverrides["installOutput"] = True


	def EnableHeaderInstall( self ):
		"""
		Enables installation of the project's headers
		Default target is /usr/local/include, unless the --prefix option is specified.
		If --prefix is specified, the target will be *{prefix*}/include

		:type s: str
		:param s: Override directory - i.e., if you specify this as "headers", the headers will be installed
		to *{prefix*}/headers.
		"""
		self._settingsOverrides["installHeaders"] = True


	def SetHeaderInstallSubdirectory( self, s ):
		"""
		Specifies a subdirectory of *{prefix*}/include in which to install the headers.

		:type s: str
		:param s: The desired subdirectory; i.e., if you specify this as "myLib", the headers will be
		installed under *{prefix*}/include/myLib.
		"""
		self._settingsOverrides["headerInstallSubdir"] = s


	def AddExcludeDirectories( self, *args ):
		"""
		Exclude the given directories from the project. This may be called multiple times to add additional excludes.
		Directories are relative to the location of the script itself, not the specified project working directory.

		:type args: an arbitrary number of strings
		:param args: The list of directories to be excluded.
		"""
		if "excludeDirs" not in self._settingsOverrides:
			self._settingsOverrides["excludeDirs"] = []
		args = list( args )
		newargs = []
		for arg in args:
			if arg[0] != '/' and not arg.startswith( "./" ):
				arg = "./" + arg
			newargs.append( os.path.abspath( arg ) )
		self._settingsOverrides["excludeDirs"] += newargs


	def AddExcludeFiles( self, *args ):
		"""
		Exclude the given files from the project. This may be called multiple times to add additional excludes.
		Files are relative to the location of the script itself, not the specified project working directory.

		:type args: an arbitrary number of strings
		:param args: The list of files to be excluded.
		"""
		if "excludeFiles" not in self._settingsOverrides:
			self._settingsOverrides["excludeFiles"] = []

		args = list( args )
		newargs = []
		for arg in args:
			if arg[0] != '/' and not arg.startswith( "./" ):
				arg = "./" + arg
			newargs.append( os.path.abspath( arg ) )
		self._settingsOverrides["excludeFiles"] += newargs


	def AddLibraries( self, *args ):
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
		if "libraries" not in self._settingsOverrides:
			self._settingsOverrides["libraries"] = set()

		self._settingsOverrides["libraries"] |= set( args )


	def AddStaticLibraries( self, *args ):
		"""
		Similar to csbuild.toolchain.Libraries, but forces these libraries to be linked statically.

		:type args: an arbitrary number of strings
		:param args: The list of libraries to link in.
		"""
		if "staticLibraries" not in self._settingsOverrides:
			self._settingsOverrides["staticLibraries"] = set()

		self._settingsOverrides["staticLibraries"] |= set( args )


	def AddSharedLibraries( self, *args ):
		"""
		Similar to csbuild.toolchain.Libraries, but forces these libraries to be linked dynamically.

		:type args: an arbitrary number of strings
		:param args: The list of libraries to link in.
		"""
		if "sharedLibraries" not in self._settingsOverrides:
			self._settingsOverrides["sharedLibraries"] = set()

		self._settingsOverrides["sharedLibraries"] |= set( args )


	def AddFrameworks( self, *args ):
		"""
		When linking the project, link against the given frameworks. This may be called multiple times to add additional frameworks.

		These will have no effect on toolchains that do not support frameworks.

		:type args: an arbitrary number of strings
		:param args: The list of frameworks to link in.
		"""
		if "frameworks" not in self._settingsOverrides:
			self._settingsOverrides["frameworks"] = set()

		self._settingsOverrides["frameworks"] |= set( args )


	def AddIncludeDirectories( self, *args ):
		"""
		Search the given directories for include headers. This may be called multiple times to add additional directories.
		Directories are relative to the location of the script itself, not the specified project working directory.

		In the gcc toolchain, /usr/include and /usr/local/include (or the platform appropriate equivalents) will always
		be appended to the end of this list.

		:type args: an arbitrary number of strings
		:param args: The list of directories to be searched.
		"""
		if "includeDirs" not in self._settingsOverrides:
			self._settingsOverrides["includeDirs"] = []

		for arg in args:
			arg = os.path.abspath( arg )
			self._settingsOverrides["includeDirs"].append( arg )


	def AddLibraryDirectories( self, *args ):
		"""
		Search the given directories for libraries to link. This may be called multiple times to add additional directories.
		Directories are relative to the location of the script itself, not the specified project working directory.

		In the gcc toolchain, /usr/lib and /usr/local/lib (or the platform appropriate equivalents) will always
		be appended to the end of this list.

		:type args: an arbitrary number of strings
		:param args: The list of directories to be searched.
		"""
		if "libraryDirs" not in self._settingsOverrides:
			self._settingsOverrides["libraryDirs"] = []

		for arg in args:
			arg = os.path.abspath( arg )
			self._settingsOverrides["libraryDirs"].append( arg )


	def AddFrameworkDirectories( self, *args ):
		"""
		Search the given directories for frameworks. This may be called multiple times to add additional directories.
		Directories are relative to the location of the script itself, not the specified project working directory.

		:type args: an arbitrary number of strings
		:param args: The list of directories to be searched.
		"""
		if "frameworkDirs" not in self._settingsOverrides:
			self._settingsOverrides["frameworkDirs"] = []

		for arg in args:
			arg = os.path.abspath( arg )
			self._settingsOverrides["frameworkDirs"].append( arg )


	def ClearLibraries( self ):
		"""Clears the list of libraries"""
		self._settingsOverrides["libraries"] = set()


	def ClearStaticLibraries( self ):
		"""Clears the list of libraries"""
		self._settingsOverrides["staticLibraries"] = set()


	def ClearSharedLibraries( self ):
		"""Clears the list of libraries"""
		self._settingsOverrides["sharedLibraries"] = set()


	def ClearFrameworks( self ):
		"""Clears the list of framworks"""
		self._settingsOverrides["frameworks"] = set()


	def ClearIncludeDirectories( self ):
		"""Clears the include directories, including the defaults."""
		self._settingsOverrides["includeDirs"] = []


	def ClearLibDirectories( self ):
		"""Clears the library directories, including the defaults"""
		self._settingsOverrides["libraryDirs"] = []


	def ClearFrameworkDirectories( self ):
		"""Clears the framework directories, including the defaults."""
		self._settingsOverrides["frameworkDirs"] = []


	def SetOptimizationLevel( self, i ):
		"""
		Sets the optimization level. Due to toolchain differences, this should be called per-toolchain, usually.

		:type i: either str or int
		:param i: A toolchain-appropriate optimization level.
		"""
		self._settingsOverrides["optLevel"] = i
		self._settingsOverrides["_optLevel_set"] = True


	def SetDebugLevel( self, i ):
		"""
		Sets the debug level. Due to toolchain differences, this should be called per-toolchain, usually.

		:type i: either str or int
		:param i: A toolchain-appropriate debug level.
		"""
		self._settingsOverrides["debugLevel"] = i
		self._settingsOverrides["_debugLevel_set"] = True


	def AddDefines( self, *args ):
		"""
		Add additionally defined preprocessor directives, as if each file had a #define directive at the very top.

		:type args: an arbitrary number of strings
		:param args: The list of preprocessor directives to define
		"""
		if "defines" not in self._settingsOverrides:
			self._settingsOverrides["defines"] = []

		self._settingsOverrides["defines"] += list( args )


	def ClearDefines( self ):
		"""clears the list of defines"""
		self._settingsOverrides["defines"] = []


	def AddUndefines( self, *args ):
		"""
		Add explicitly undefined preprocessor directives, as if each file had a #undef directive at the very top.

		:type args: an arbitrary number of strings
		:param args: The list of preprocessor directives to undefine
		"""
		if "undefines" not in self._settingsOverrides:
			self._settingsOverrides["undefines"] = []

		self._settingsOverrides["undefines"] += list( args )


	def ClearUndefines( self ):
		"""clears the list of undefines"""
		self._settingsOverrides["undefines"] = []


	def SetCxxCommand( self, s ):
		"""
		Specify the compiler executable to be used for compiling C++ files. Ignored by the msvc toolchain.

		:type s: str
		:param s: Path to the executable to use for compilation
		"""
		self._settingsOverrides["cxx"] = s


	def SetCcCommand( self, s ):
		"""
		Specify the compiler executable to be used for compiling C files. Ignored by the msvc toolchain.

		:type s: str
		:param s: Path to the executable to use for compilation
		"""
		self._settingsOverrides["cc"] = s


	def SetOutput( self, name, projectType = csbuild.ProjectType.Application ):
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
		self._settingsOverrides["outputName"] = name
		self._settingsOverrides["type"] = projectType


	def SetOutputExtension( self, name ):
		"""
		This allows you to override the extension used for the output file.

		:type name: str
		:param name: The desired extension, including the .; i.e., csbuild.Extension( ".exe" )
		"""
		self._settingsOverrides["ext"] = name


	def SetOutputDirectory( self, s ):
		"""
		Specifies the directory in which to place the output file.

		:type s: str
		:param s: The output directory, relative to the current script location, NOT to the project working directory.
		"""
		self._settingsOverrides["outputDir"] = os.path.abspath( s )
		self._settingsOverrides["_outputDir_set"] = True


	def SetIntermediateDirectory( self, s ):
		"""
		Specifies the directory in which to place the intermediate .o or .obj files.

		:type s: str
		:param s: The object directory, relative to the current script location, NOT to the project working directory.
		"""
		self._settingsOverrides["objDir"] = os.path.abspath( s )
		self._settingsOverrides["_objDir_set"] = True


	def EnableProfiling( self ):
		"""
		Optimize output for profiling
		"""
		self._settingsOverrides["profile"] = True


	def DisableProfiling( self ):
		"""
		Turns profiling optimizations back off
		"""
		self._settingsOverrides["profile"] = False


	def AddCxxCompilerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the C++ compiler. As this is toolchain-specific, it should be
		called on a per-toolchain basis.

		:type args: an arbitrary number of strings
		:param args: The list of flags to be passed
		"""
		if "cxxCompilerFlags" not in self._settingsOverrides:
			self._settingsOverrides["cxxCompilerFlags"] = []

		self._settingsOverrides["cxxCompilerFlags"] += list( args )


	def ClearCxxCompilerFlags( self ):
		"""
		Clears the list of literal C++ compiler flags.
		"""
		self._settingsOverrides["cxxCompilerFlags"] = []


	def AddCcCompilerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the C compiler. As this is toolchain-specific, it should be
		called on a per-toolchain basis.

		:type args: an arbitrary number of strings
		:param args: The list of flags to be passed
		"""
		if "ccCompilerFlags" not in self._settingsOverrides:
			self._settingsOverrides["ccCompilerFlags"] = []

		self._settingsOverrides["ccCompilerFlags"] += list( args )


	def ClearCcCompilerFlags( self ):
		"""
		Clears the list of literal C compiler flags.
		"""
		self._settingsOverrides["ccCompilerFlags"] = []


	def AddCompilerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the both the C compiler and the C++ compiler.
		As this is toolchain-specific, it should be called on a per-toolchain basis.

		:type args: an arbitrary number of strings
		:param args: The list of flags to be passed
		"""
		self.AddCcCompilerFlags( *args )
		self.AddCxxCompilerFlags( *args )


	def ClearCompilerFlags( self ):
		"""
		Clears the list of literal compiler flags.
		"""
		self.ClearCcCompilerFlags( )
		self.ClearCxxCompilerFlags( )


	def AddLinkerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the linker. As this is toolchain-specific, it should be
		called on a per-toolchain basis.

		:type args: an arbitrary number of strings
		:param args: The list of flags to be passed
		"""
		if "linkerFlags" not in self._settingsOverrides:
			self._settingsOverrides["linkerFlags"] = []

		self._settingsOverrides["linkerFlags"] += list( args )


	def ClearLinkerFlags( self ):
		"""
		Clears the list of literal linker flags.
		"""
		self._settingsOverrides["linkerFlags"] = []


	def DisableChunkedBuild( self ):
		"""Turn off the chunked/unity build system and build using individual files."""
		self._settingsOverrides["useChunks"] = False


	def EnableChunkedBuild( self ):
		"""Turn chunked/unity build on and build using larger compilation units. This is the default."""
		self._settingsOverrides["useChunks"] = True


	def SetNumFilesPerChunk( self, i ):
		"""
		Set the size of the chunks used in the chunked build. This indicates the number of files per compilation unit.
		The default is 10.

		This value is ignored if SetChunks is called.

		Mutually exclusive with ChunkFilesize().

		:type i: int
		:param i: Number of files per chunk
		"""
		self._settingsOverrides["chunkSize"] = i
		self._settingsOverrides["chunkFilesize"] = 0


	def SetMaxChunkFileSize( self, i ):
		"""
		Sets the maximum combined filesize for a chunk. The default is 500000, and this is the default behavior.

		This value is ignored if SetChunks is called.

		Mutually exclusive with ChunkNumFiles()

		:type i: int
		:param i: Maximum size per chunk in bytes.
		"""
		self._settingsOverrides["chunkFilesize"] = i
		self._settingsOverrides["chunkSize"] = i


	def SetChunkTolerance( self, i ):
		"""
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
		if "chunkFilesize" in self._settingsOverrides and self._settingsOverrides["chunkFilesize"] > 0:
			self._settingsOverrides["chunkSizeTolerance"] = i
		elif "chunkSize" in self._settingsOverrides and self._settingsOverrides["chunkSize"] > 0:
			self._settingsOverrides["chunkTolerance"] = i
		else:
			log.LOG_WARN( "Chunk size and chunk filesize are both zero or negative, cannot set a tolerance." )


	def SetChunks( self, *chunks ):
		"""
		Explicitly set the chunks used as compilation units.

		NOTE that setting this will disable the automatic file gathering, so any files in the project directory that
		are not specified here will not be built.

		:type chunks: an arbitrary number of lists of strings
		:param chunks: Lists containing filenames of files to be built,
		relativel to the script's location, NOT the project working directory. Each list will be built as one chunk.
		"""
		chunks = list( chunks )
		self._settingsOverrides["forceChunks"] = chunks


	def ClearChunks( self ):
		"""Clears the explicitly set list of chunks and returns the behavior to the default."""
		self._settingsOverrides["forceChunks"] = []


	def SetHeaderRecursionDepth( self, i ):
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
		self._settingsOverrides["headerRecursionDepth"] = i


	def IgnoreExternalHeaders( self ):
		"""
		If this option is set, external headers will not be checked or followed when building. Only headers within the
		base project's directory and its subdirectories will be checked. This will speed up header checking, but if you
		modify any external headers, you will need to manually --clean or --rebuild the project.
		"""
		self._settingsOverrides["ignoreExternalHeaders"] = True


	def DisableWarnings( self ):
		"""
		Disables all warnings.
		"""
		self._settingsOverrides["noWarnings"] = True


	def SetDefaultTarget( self, s ):
		"""
		Sets the default target if none is specified. The default value for this is release.

		:type s: str
		:param s: Name of the target to build for this project if none is specified.
		"""
		self._settingsOverrides["defaultTarget"] = s.lower( )


	def Precompile( self, *args ):
		"""
		Explicit list of header files to precompile. Disables chunk precompile when called.

		:type args: an arbitrary number of strings
		:param args: The files to precompile.
		"""
		self._settingsOverrides["precompile"] = []
		for arg in list( args ):
			self._settingsOverrides["precompile"].append( os.path.abspath( arg ) )
		self._settingsOverrides["chunkedPrecompile"] = False


	def PrecompileAsC( self, *args ):
		"""
		Specifies header files that should be compiled as C headers instead of C++ headers.

		:type args: an arbitrary number of strings
		:param args: The files to specify as C files.
		"""
		self._settingsOverrides["precompileAsC"] = []
		for arg in list( args ):
			self._settingsOverrides["precompileAsC"].append( os.path.abspath( arg ) )


	def EnableChunkedPrecompile( self ):
		"""
		When this is enabled, all header files will be precompiled into a single "superheader" and included in all files.
		"""
		self._settingsOverrides["chunkedPrecompile"] = True


	def DisablePrecompile( self, *args ):
		"""
		Disables precompilation and handles headers as usual.

		:type args: an arbitrary number of strings
		:param args: A list of files to disable precompilation for.
		If this list is empty, it will disable precompilation entirely.
		"""
		if "precompileExcludeFiles" not in self._settingsOverrides:
			self._settingsOverrides["precompileExcludeFiles"] = []

		args = list( args )
		if args:
			newargs = []
			for arg in args:
				if arg[0] != '/' and not arg.startswith( "./" ):
					arg = "./" + arg
				newargs.append( os.path.abspath( arg ) )
				self._settingsOverrides["precompileExcludeFiles"] += newargs
		else:
			self._settingsOverrides["chunkedPrecompile"] = False
			self._settingsOverrides["precompile"] = []
			self._settingsOverrides["precompileAsC"] = []


	def EnableUnityBuild( self ):
		"""
		Turns on true unity builds, combining all files into only one compilation unit.
		"""
		self._settingsOverrides["unity"] = True


	def LinkStaticRuntime( self ):
		"""
		Link against a static C/C++ runtime library.
		"""
		self._settingsOverrides["useStaticRuntime"] = True


	def LinkSharedRuntime( self ):
		"""
		Link against a dynamic C/C++ runtime library.
		"""
		self._settingsOverrides["useStaticRuntime"] = False


	def SetOutputArchitecture( self, arch ):
		"""
		Set the output architecture.

		:type arch: ArchitectureType
		:param arch: The desired architecture.
		"""
		self._settingsOverrides["outputArchitecture"] = arch

	def AddExtraFiles( self, *args ):
		"""
		Adds additional files to be compiled that are not in the project directory.

		:type args: an arbitrary number of strings
		:param args: A list of files to add.
		"""
		if "extraFiles" not in self._settingsOverrides:
			self._settingsOverrides["extraFiles"] = []
		for arg in list( args ):
			for file in glob.glob( arg ):
				self._settingsOverrides["extraFiles"].append( os.path.abspath( file ) )


	def ClearExtraFiles(self):
		"""
		Clear the list of external files to compile.
		"""
		self._settingsOverrides["extraFiles"] = []


	def AddExtraDirectories( self, *args ):
		"""
		Adds additional directories to search for files in.

		:type args: an arbitrary number of strings
		:param args: A list of directories to search.
		"""
		if "extraDirs" not in self._settingsOverrides:
			self._settingsOverrides["extraDirs"] = []
		for arg in list( args ):
			self._settingsOverrides["extraDirs"].append( os.path.abspath( arg ) )


	def AddExtraObjects( self, *args ):
		"""
		Adds additional objects to be passed to the linker that are not in the project directory.

		:type args: an arbitrary number of strings
		:param args: A list of objects to add.
		"""
		# Make sure the set exists before adding anything to it.
		if not "extraObjs" in self._settingsOverrides:
			self._settingsOverrides["extraObjs"] = set()

		for arg in list( args ):
			for file in glob.glob( arg ):
				self._settingsOverrides["extraObjs"].add( os.path.abspath( file ) )


	def ClearExtraObjects( self ):
		"""
		Clear the list of external objects to link.
		"""
		if "extraObjs" in self._settingsOverrides:
			self._settingsOverrides["extraObjs"] = set()


	def ClearExtraDirectories(self):
		"""
		Clear the list of external directories to search.
		"""
		self._settingsOverrides["extraDirs"] = []

	def EnableWarningsAsErrors( self ):
		"""
		Promote all warnings to errors.
		"""
		self._settingsOverrides["warningsAsErrors"] = True


	def DisableWarningsAsErrors(self):
		"""
		Disable the promotion of warnings to errors.
		"""
		self._settingsOverrides["warningsAsErrors"] = False

	def DoNotChunkTogether(self, pattern, *additionalPatterns):
		"""
		Makes files matching the given patterns mutually exclusive for chunking.
		I.e., if you call this with DoNotChunkTogether("File1.cpp", "File2.cpp"), it guarantees
		File1 and File2 will never appear together in the same chunk. If you specify more than two files,
		or a pattern that matches more than two files, no two files in the list will ever appear together.

		:type pattern: string
		:param pattern: Pattern to search for files with (i.e., Source/*_Unchunkable.cpp)
		:type additionalPatterns: arbitrary number of optional strings
		:param additionalPatterns: Additional patterns to compile the list of mutually exclusive files with
		"""
		if "chunkMutexes" not in self._settingsOverrides:
			self._settingsOverrides["chunkMutexes"] = {}
		patterns = [pattern] + list(additionalPatterns)
		mutexFiles = set()
		for patternToMatch in patterns:
			for filename in glob.glob(patternToMatch):
				mutexFiles.add(os.path.abspath(filename))

		for file1 in mutexFiles:
			for file2 in mutexFiles:
				if file1 == file2:
					continue
				if file1 not in self._settingsOverrides["chunkMutexes"]:
					self._settingsOverrides["chunkMutexes"][file1] = set( [file2] )
				else:
					self._settingsOverrides["chunkMutexes"][file1].add(file2)

	def DoNotChunk(self, *files):
		"""
		Prevents the listed files (or files matching the listed patterns) from ever being placed
		in a chunk, ever.

		:type files: arbitrary number of strings
		:param files: filenames or patterns to exclude from chunking
		"""

		if "chunkExcludes" not in self._settingsOverrides:
			self._settingsOverrides["chunkExcludes"] = set()

		for pattern in list(files):
			for filename in glob.glob(pattern):
				self._settingsOverrides["chunkExcludes"].add(os.path.abspath(filename))


	def SetStaticLinkMode(self, mode):
		"""
		Determines how static links are handled. With the msvc toolchain, iterative link times of a project with many libraries
		can be significantly improved by setting this to :StaticLinkMode.LinkIntermediateObjects:. This will cause the linker to link
		the .obj files used to make a library directly into the dependent project. Link times for full builds may be slightly slower,
		but this will allow incremental linking to function when libraries are being changed. (Usually, changing a .lib results
		in a full link.)

		On most toolchains, this defaults to :StaticLinkMode.LinkLibs:. In debug mode only for the msvc toolchain, this defaults
		to :StaticLinkMode.LinkIntermediateObjects:.

		:type mode: :StaticLinkMode:
		:param mode: The link mode to set
		"""
		self._settingsOverrides["linkMode"] = mode
		self._settingsOverrides["linkModeSet"] = True


	def SetUserData(self, key, value):
		"""
		Adds miscellaneous data to a project. This can be used later in a build event or in a format string.

		This becomes an attribute on the project's userData member variable. As an example, to set a value:

		csbuild.SetUserData("someData", "someValue")

		Then to access it later:

		project.userData.someData

		:type key: str
		:param key: name of the variable to set
		:type value: any
		:param value: value to set to that variable
		"""
		if "userData" not in self._settingsOverrides:
			self._settingsOverrides["userData"] = csbuild.projectSettings.projectSettings.UserData()

		self._settingsOverrides["userData"].dataDict[key] = value


	def SetSupportedArchitectures(self, *architectures):
		"""
		Specifies the architectures that this project supports. This can be used to limit
		--all-architectures from building everything supported by the toolchain, if the project
		is not set up to support all of the toolchain's architectures.
		"""
		self._settingsOverrides["supportedArchitectures"] = set(architectures)


@_shared_globals.MetaClass(ABCMeta)
class linkerBase( SettingsOverrider ):
	def __init__(self):
		SettingsOverrider.__init__(self)

	def prePrepareBuildStep(self, project):
		pass

	def postPrepareBuildStep(self, project):
		pass

	def preMakeStep(self, project):
		pass

	def postMakeStep(self, project):
		pass

	def preBuildStep(self, project):
		pass

	def preLinkStep(self, project):
		pass

	def postBuildStep(self, project):
		pass

	def parseOutput(self, outputStr):
		return None

	@abstractmethod
	def copy(self):
		return SettingsOverrider.copy(self)

	@staticmethod
	def AdditionalArgs( parser ):
		"""
		Asks for additional command-line arguments to be added by the toolchain.

		:param parser: A parser for these arguments to be added to
		:type parser: argparse.argument_parser
		"""
		pass


	@abstractmethod
	def InterruptExitCode( self ):
		"""
		Get the exit code that the compiler returns if the compile process is interrupted.

		:return: The linker's interrupt exit code
		:rtype: int
		"""
		pass

	@abstractmethod
	def GetValidArchitectures( self ):
		"""
		Get the list of architectures supported by this linker.

		:return: List of architectures
		:rtype: list[str]
		"""
		pass

	@abstractmethod
	def GetLinkCommand( self, project, outputFile, objList ):
		"""
		Retrieves the command to be used for linking for this toolchain.

		:param project: The project currently being linked, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:param outputFile: The file that will be the result of the link operation.
		:type outputFile: str

		:param objList: List of objects being linked
		:type objList: list[str]

		:return: The fully formatted link command
		:rtype: str
		"""
		pass


	@abstractmethod
	def FindLibrary( self, project, library, libraryDirs, force_static, force_shared ):
		"""
		Search for a library and verify that it is installed.

		:param project: The project currently being checked, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:param library: The library being searched for
		:type library: str

		:param libraryDirs: The directories to search for the library in
		:type libraryDirs: list[str]

		:param force_static: Whether or not this library should be forced to link statically
		:type force_static: bool

		:param force_shared: Whether or not this library should be forced to link dynamically
		:type force_shared: bool

		:return: The location to the library if found, or None
		:rtype: str or None
		"""
		pass

	@abstractmethod
	def GetDefaultOutputExtension( self, projectType ):
		"""
		Get the default extension for a given :class:`csbuild.ProjectType` value.

		:param projectType: The requested output type
		:type projectType: :class:`csbuild.ProjectType`

		:return: The extension, including the . (i.e., .so, .a, .lib, .exe)
		:rtype: str
		"""
		pass


@_shared_globals.MetaClass(ABCMeta)
class compilerBase( SettingsOverrider ):
	def __init__(self):
		SettingsOverrider.__init__(self)

	def prePrepareBuildStep(self, project):
		pass

	def postPrepareBuildStep(self, project):
		pass

	def preMakeStep(self, project):
		pass

	def postMakeStep(self, project):
		pass

	def preBuildStep(self, project):
		pass

	def preLinkStep(self, project):
		pass

	def postBuildStep(self, project):
		pass

	def parseOutput(self, outputStr):
		return None

	def GetDefaultArchitecture(self):
		if platform.machine().endswith('64'):
			return "x64"
		else:
			return "x86"


	@abstractmethod
	def copy(self):
		return SettingsOverrider.copy(self)

	@staticmethod
	def AdditionalArgs( parser ):
		"""
		Asks for additional command-line arguments to be added by the toolchain.

		:param parser: A parser for these arguments to be added to
		:type parser: argparse.argument_parser
		"""
		pass


	@abstractmethod
	def InterruptExitCode( self ):
		"""
		Get the exit code that the compiler returns if the compile process is interrupted.

		:return: The compiler's interrupt exit code
		:rtype: int
		"""
		pass

	@abstractmethod
	def GetValidArchitectures( self ):
		"""
		Get the list of architectures supported by this compiler.

		:return: List of architectures
		:rtype: list[str]
		"""
		pass


	@abstractmethod
	def GetBaseCxxCommand( self, project ):
		"""
		Retrieves the BASE C++ compiler command for this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		:param project: The project currently being compiled, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:return: The base command string
		:rtype: str
		"""
		pass


	@abstractmethod
	def GetBaseCcCommand( self, project ):
		"""
		Retrieves the BASE C compiler command for this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		:param project: The project currently being compiled, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:return: The base command string
		:rtype: str
		"""
		pass


	@abstractmethod
	def GetExtendedCommand( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		"""
		Retrieves the EXTENDED C/C++ compiler command for compiling a specific file

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		:param baseCmd: The project's base command as returned from :get_base_cxx_command: or :get_base_cc_command:,
		as is appropriate for the file being compiled.
		:type baseCmd: str

		:param project: The project currently being compiled, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:param forceIncludeFile: A precompiled header that's being forcefully included.
		:type forceIncludeFile: str

		:param outObj: The object file to be generated by this command
		:type outObj: str

		:param inFile: The file being compiled
		:type inFile: str

		:return: The extended command string, including the base command string
		:rtype: str
		"""
		pass


	@abstractmethod
	def GetBaseCxxPrecompileCommand( self, project ):
		"""
		Retrieves the BASE C++ compiler command for precompiling headers in this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		:param project: The project currently being compiled, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:return: The base command string
		:rtype: str
		"""
		pass


	@abstractmethod
	def GetBaseCcPrecompileCommand( self, project ):
		"""
		Retrieves the BASE C compiler command for precompiling headers in this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		:param project: The project currently being compiled, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:return: The base command string
		:rtype: str
		"""
		pass


	@abstractmethod
	def GetExtendedPrecompileCommand( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		"""
		Retrieves the EXTENDED C/C++ compiler command for compiling a specific precompiled header

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		:param baseCmd: The project's base command as returned from :get_base_cxx_command: or :get_base_cc_command:,
		as is appropriate for the file being compiled.
		:type baseCmd: str

		:param project: The project currently being compiled, which can be used to retrieve any needed information.
		:type project: :class:`csbuild.projectSettings.projectSettings`

		:param forceIncludeFile: Currently unused for precompiled headers.
		:type forceIncludeFile: str

		:param outObj: The object file to be generated by this command
		:type outObj: str

		:param inFile: The file being compiled
		:type inFile: str

		:return: The extended command string, including the base command string
		:rtype: str
		"""
		pass


	@abstractmethod
	def GetPchFile( self, fileName ):
		"""
		Get the properly formatted precompiled header output file for a given header input.

		:param fileName: The input header
		:type fileName: str

		:return: The formatted output file (i.e., "header.pch" or "header.gch")
		:rtype: str
		"""
		pass


	@abstractmethod
	def GetPreprocessCommand(self, baseCmd, project, inFile ):
		return ""


	@abstractmethod
	def PragmaMessage(self, message):
		return ""


	def GetExtraPostPreprocessorFlags(self):
		return ""


	def GetPostPreprocessorSanitationLines(self):
		return []

	@abstractmethod
	def GetObjExt(self):
		"""
		Get the extension for intermediate object files, including the .
		"""
		pass


class toolchain( object ):
	"""
	Base class used for custom toolchains
	To create a new toolchain, inherit from this class, and then use
	:func:`csbuild.RegisterToolchain`
	"""
	def __init__( self ):
		"""
		Default constructor
		"""

		self._settingsOverrides = { }
		self.tools = {}
		self.activeTool = None
		self.activeToolName = ""


	def Compiler(self):
		return self.tools["compiler"]


	def Linker(self):
		return self.tools["linker"]


	def Assembler(self):
		return self.tools["assembler"]


	def Tool( self, *args ):
		"""
		Perform actions on the listed tools. Examples:

		csbuild.Toolchain("msvc").Tool("compiler", "linker").SetMsvcVersion(110)

		:type args: arbitrary number of strings
		:param args: The list of tools to act on

		:return: A proxy object that enables functions to be applied to one or more specific tools.
		"""
		tools = []
		for arg in list( args ):
			tools.append( self.tools[arg] )
		return ClassCombiner( tools )


	def GetValidArchitectures( self ):
		validArchs = set()
		first = True
		for tool in self.tools.values():
			if hasattr(tool, "GetValidArchitectures"):
				archsThisTool = tool.GetValidArchitectures()
				if first:
					validArchs = set(archsThisTool)
					first = False
				else:
					validArchs &= set(archsThisTool)
		return list(validArchs)


	def AddCustomTool(self, name, tool):
		self.tools[name] = tool()


	def SetActiveTool(self, name):
		self.activeToolName = name
		if name:
			self.activeTool = self.tools[name]
		else:
			self.activeTool = None

	def _runStep(self, name, project):
		for tool in self.tools.values():
			if hasattr(tool, name):
				getattr(tool, name)(project)

	def prePrepareBuildStep(self, project):
		self._runStep("prePrepareBuildStep", project)

	def postPrepareBuildStep(self, project):
		self._runStep("postPrepareBuildStep", project)

	def preMakeStep(self, project):
		self._runStep("preMakeStep", project)

	def postMakeStep(self, project):
		self._runStep("postMakeStep", project)

	def preBuildStep(self, project):
		self._runStep("preBuildStep", project)

	def preLinkStep(self, project):
		self._runStep("preLinkStep", project)

	def postBuildStep(self, project):
		self._runStep("postBuildStep", project)


	def __getattr__( self, name ):
		funcs = []
		for obj in self.tools.values():
			funcs.append( getattr( obj, name ) )

		def combined_func( *args, **kwargs ):
			for func in funcs:
				func( *args, **kwargs )

		return combined_func


	def copy( self ):
		"""
		Create a deep copy of this toolchain.

		:return: a copy of this toolchain
		:rtype: toolchain
		"""
		ret = toolchain()

		for kvp in self.tools.items():
			ret.tools[kvp[0]] = kvp[1].copy()

		if self.activeToolName:
			ret.activeToolName = self.activeToolName
			if ret.activeToolName:
				ret.activeTool = ret.tools[ret.activeToolName]

		return ret
