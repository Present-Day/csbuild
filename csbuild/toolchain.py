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
B{Toolchain Module}

Defines the base class for creating custom toolchains

@undocumented: ClassCombiner
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

	@ivar objs: The objects contained within the combined class
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
		self.settingsOverrides = {}

	def copy(self):
		ret = self.__class__()

		for kvp in self.settingsOverrides.items( ):
			if isinstance( kvp[1], list ):
				ret.settingsOverrides[kvp[0]] = list( kvp[1] )
			elif isinstance( kvp[1], dict ):
				ret.settingsOverrides[kvp[0]] = dict( kvp[1] )
			elif isinstance( kvp[1], set ):
				ret.settingsOverrides[kvp[0]] = set( kvp[1] )
			else:
				ret.settingsOverrides[kvp[0]] = kvp[1]

		return ret

	def InstallOutput( self ):
		"""
		Enables installation of the compiled output file.
		Default target is /usr/local/lib, unless the --prefix option is specified.
		If --prefix is specified, the target will be I{{prefix}}/lib

		@type s: str
		@param s: Override directory - i.e., if you specify this as "libraries", the libraries will be installed
		to I{{prefix}}/libraries.
		"""
		self.settingsOverrides["install_output"] = True


	def InstallHeaders( self ):
		"""
		Enables installation of the project's headers
		Default target is /usr/local/include, unless the --prefix option is specified.
		If --prefix is specified, the target will be I{{prefix}}/include

		@type s: str
		@param s: Override directory - i.e., if you specify this as "headers", the headers will be installed
		to I{{prefix}}/headers.
		"""
		self.settingsOverrides["install_headers"] = True


	def InstallSubdir( self, s ):
		"""
		Specifies a subdirectory of I{{prefix}}/include in which to install the headers.

		@type s: str
		@param s: The desired subdirectory; i.e., if you specify this as "myLib", the headers will be
		installed under I{{prefix}}/include/myLib.
		"""
		self.settingsOverrides["header_subdir"] = s


	def ExcludeDirs( self, *args ):
		"""
		Exclude the given directories from the project. This may be called multiple times to add additional excludes.
		Directories are relative to the location of the script itself, not the specified project working directory.

		@type args: an arbitrary number of strings
		@param args: The list of directories to be excluded.
		"""
		if "exclude_dirs" not in self.settingsOverrides:
			self.settingsOverrides["exclude_dirs"] = []
		args = list( args )
		newargs = []
		for arg in args:
			if arg[0] != '/' and not arg.startswith( "./" ):
				arg = "./" + arg
			newargs.append( os.path.abspath( arg ) )
		self.settingsOverrides["exclude_dirs"] += newargs


	def ExcludeFiles( self, *args ):
		"""
		Exclude the given files from the project. This may be called multiple times to add additional excludes.
		Files are relative to the location of the script itself, not the specified project working directory.

		@type args: an arbitrary number of strings
		@param args: The list of files to be excluded.
		"""
		if "exclude_files" not in self.settingsOverrides:
			self.settingsOverrides["exclude_files"] = []

		args = list( args )
		newargs = []
		for arg in args:
			if arg[0] != '/' and not arg.startswith( "./" ):
				arg = "./" + arg
			newargs.append( os.path.abspath( arg ) )
		self.settingsOverrides["exclude_files"] += newargs


	def Libraries( self, *args ):
		"""
		When linking the project, link in the given libraries. This may be called multiple times to add additional libraries.

		In the gcc toolchain, these will all be prefixed with "lib" when looking for the file to link. I.e.,
		csbuild.Libraries("MyLib") will link libMyLib.so or libMyLib.a.

		For compatibility, the msvc toolchain will search for the library exactly as specified, and if it can't find it,
		will then search for it with the lib prefix. I.e., csbuild.Libraries("MyLib") will first search for MyLib.lib,
		and if that isn't found, will then search for libMyLib.lib.

		@type args: an arbitrary number of strings
		@param args: The list of libraries to link in.
		"""
		if "libraries" not in self.settingsOverrides:
			self.settingsOverrides["libraries"] = set()

		self.settingsOverrides["libraries"] |= set( args )


	def StaticLibraries( self, *args ):
		"""
		Similar to csbuild.toolchain.Libraries, but forces these libraries to be linked statically.

		@type args: an arbitrary number of strings
		@param args: The list of libraries to link in.
		"""
		if "static_libraries" not in self.settingsOverrides:
			self.settingsOverrides["static_libraries"] = set()

		self.settingsOverrides["static_libraries"] |= set( args )


	def SharedLibraries( self, *args ):
		"""
		Similar to csbuild.toolchain.Libraries, but forces these libraries to be linked dynamically.

		@type args: an arbitrary number of strings
		@param args: The list of libraries to link in.
		"""
		if "shared_libraries" not in self.settingsOverrides:
			self.settingsOverrides["shared_libraries"] = set()

		self.settingsOverrides["shared_libraries"] |= set( args )


	def IncludeDirs( self, *args ):
		"""
		Search the given directories for include headers. This may be called multiple times to add additional directories.
		Directories are relative to the location of the script itself, not the specified project working directory.

		In the gcc toolchain, /usr/include and /usr/local/include (or the platform appropriate equivalents) will always
		be appended to the end of this list.

		@type args: an arbitrary number of strings
		@param args: The list of directories to be searched.
		"""
		if "include_dirs" not in self.settingsOverrides:
			self.settingsOverrides["include_dirs"] = []

		for arg in args:
			arg = os.path.abspath( arg )
			self.settingsOverrides["include_dirs"].append( arg )


	def LibDirs( self, *args ):
		"""
		Search the given directories for libraries to link. This may be called multiple times to add additional directories.
		Directories are relative to the location of the script itself, not the specified project working directory.

		In the gcc toolchain, /usr/lib and /usr/local/lib (or the platform appropriate equivalents) will always
		be appended to the end of this list.

		@type args: an arbitrary number of strings
		@param args: The list of directories to be searched.
		"""
		if "library_dirs" not in self.settingsOverrides:
			self.settingsOverrides["library_dirs"] = []

		for arg in args:
			arg = os.path.abspath( arg )
			self.settingsOverrides["library_dirs"].append( arg )


	def ClearLibraries( self ):
		"""Clears the list of libraries"""
		self.settingsOverrides["libraries"] = set()


	def ClearStaticLibraries( self ):
		"""Clears the list of libraries"""
		self.settingsOverrides["static_libraries"] = set()


	def ClearSharedLibraries( self ):
		"""Clears the list of libraries"""
		self.settingsOverrides["shared_libraries"] = set()


	def ClearIncludeDirs( self ):
		"""Clears the include directories, including the defaults."""
		self.settingsOverrides["include_dirs"] = []


	def ClearLibDirs( self ):
		"""Clears the library directories, including the defaults"""
		self.settingsOverrides["library_dirs"] = []


	def Opt( self, i ):
		"""
		Sets the optimization level. Due to toolchain differences, this should be called per-toolchain, usually.

		@type i: either str or int
		@param i: A toolchain-appropriate optimization level.
		"""
		self.settingsOverrides["opt_level"] = i
		self.settingsOverrides["opt_set"] = True


	def Debug( self, i ):
		"""
		Sets the debug level. Due to toolchain differences, this should be called per-toolchain, usually.

		@type i: either str or int
		@param i: A toolchain-appropriate debug level.
		"""
		self.settingsOverrides["debug_level"] = i
		self.settingsOverrides["debug_set"] = True


	def Define( self, *args ):
		"""
		Add additionally defined preprocessor directives, as if each file had a #define directive at the very top.

		@type args: an arbitrary number of strings
		@param args: The list of preprocessor directives to define
		"""
		if "defines" not in self.settingsOverrides:
			self.settingsOverrides["defines"] = []

		self.settingsOverrides["defines"] += list( args )


	def ClearDefines( self ):
		"""clears the list of defines"""
		self.settingsOverrides["defines"] = []


	def Undefine( self, *args ):
		"""
		Add explicitly undefined preprocessor directives, as if each file had a #undef directive at the very top.

		@type args: an arbitrary number of strings
		@param args: The list of preprocessor directives to undefine
		"""
		if "undefines" not in self.settingsOverrides:
			self.settingsOverrides["undefines"] = []

		self.settingsOverrides["undefines"] += list( args )


	def ClearUndefines( self ):
		"""clears the list of undefines"""
		self.settingsOverrides["undefines"] = []


	def CppCompiler( self, s ):
		"""
		Specify the compiler executable to be used for compiling C++ files. Ignored by the msvc toolchain.

		@type s: str
		@param s: Path to the executable to use for compilation
		"""
		self.settingsOverrides["cxx"] = s


	def CCompiler( self, s ):
		"""
		Specify the compiler executable to be used for compiling C files. Ignored by the msvc toolchain.

		@type s: str
		@param s: Path to the executable to use for compilation
		"""
		self.settingsOverrides["cc"] = s


	def Output( self, name, projectType = csbuild.ProjectType.Application ):
		"""
		Sets the output options for this project.

		@type name: str
		@param name: The output name. Do not include an extension, and do not include the "lib" prefix for libraries on
		Linux. These are added automatically.

		@type projectType: csbuild.ProjectType
		@param projectType: The type of project to compile. The options are:
			- ProjectType.Application - on Windows, this will be built with a .exe extension. On Linux, there is no extension.
			- ProjectType.SharedLibrary - on Windows, this will generate a .lib and a .dll.
			On Linux, this will generate a .so and prefix "lib" to the output name.
			- ProjectType.StaticLibrary - on Windows, this will generate a .lib. On Linux, this will generate a .a and prefix
			"lib" ot the output name.
		"""
		self.settingsOverrides["output_name"] = name
		self.settingsOverrides["type"] = projectType


	def Extension( self, name ):
		"""
		This allows you to override the extension used for the output file.

		@type name: str
		@param name: The desired extension, including the .; i.e., csbuild.Extension( ".exe" )
		"""
		self.settingsOverrides["ext"] = name


	def OutDir( self, s ):
		"""
		Specifies the directory in which to place the output file.

		@type s: str
		@param s: The output directory, relative to the current script location, NOT to the project working directory.
		"""
		self.settingsOverrides["output_dir"] = os.path.abspath( s )
		self.settingsOverrides["output_dir_set"] = True


	def ObjDir( self, s ):
		"""
		Specifies the directory in which to place the intermediate .o or .obj files.

		@type s: str
		@param s: The object directory, relative to the current script location, NOT to the project working directory.
		"""
		self.settingsOverrides["obj_dir"] = os.path.abspath( s )
		self.settingsOverrides["obj_dir_set"] = True


	def EnableProfile( self ):
		"""
		Optimize output for profiling
		"""
		self.settingsOverrides["profile"] = True


	def DisableProfile( self ):
		"""
		Turns profiling optimizations back off
		"""
		self.settingsOverrides["profile"] = False


	def CppCompilerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the C++ compiler. As this is toolchain-specific, it should be
		called on a per-toolchain basis.

		@type args: an arbitrary number of strings
		@param args: The list of flags to be passed
		"""
		if "cpp_compiler_flags" not in self.settingsOverrides:
			self.settingsOverrides["cpp_compiler_flags"] = []

		self.settingsOverrides["cpp_compiler_flags"] += list( args )


	def ClearCppCompilerFlags( self ):
		"""
		Clears the list of literal C++ compiler flags.
		"""
		self.settingsOverrides["cpp_compiler_flags"] = []


	def CCompilerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the C compiler. As this is toolchain-specific, it should be
		called on a per-toolchain basis.

		@type args: an arbitrary number of strings
		@param args: The list of flags to be passed
		"""
		if "c_compiler_flags" not in self.settingsOverrides:
			self.settingsOverrides["c_compiler_flags"] = []

		self.settingsOverrides["c_compiler_flags"] += list( args )


	def ClearCCompilerFlags( self ):
		"""
		Clears the list of literal C compiler flags.
		"""
		self.settingsOverrides["c_compiler_flags"] = []


	def CompilerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the both the C compiler and the C++ compiler.
		As this is toolchain-specific, it should be called on a per-toolchain basis.

		@type args: an arbitrary number of strings
		@param args: The list of flags to be passed
		"""
		self.CCompilerFlags( *args )
		self.CppCompilerFlags( *args )


	def ClearCompilerFlags( self ):
		"""
		Clears the list of literal compiler flags.
		"""
		self.ClearCCompilerFlags( )
		self.ClearCppCompilerFlags( )


	def LinkerFlags( self, *args ):
		"""
		Specifies a list of literal strings to be passed to the linker. As this is toolchain-specific, it should be
		called on a per-toolchain basis.

		@type args: an arbitrary number of strings
		@param args: The list of flags to be passed
		"""
		if "linker_flags" not in self.settingsOverrides:
			self.settingsOverrides["linker_flags"] = []

		self.settingsOverrides["linker_flags"] += list( args )


	def ClearLinkerFlags( self ):
		"""
		Clears the list of literal linker flags.
		"""
		self.settingsOverrides["linker_flags"] = []


	def DisableChunkedBuild( self ):
		"""Turn off the chunked/unity build system and build using individual files."""
		self.settingsOverrides["use_chunks"] = False


	def EnableChunkedBuild( self ):
		"""Turn chunked/unity build on and build using larger compilation units. This is the default."""
		self.settingsOverrides["use_chunks"] = True


	def ChunkNumFiles( self, i ):
		"""
		Set the size of the chunks used in the chunked build. This indicates the number of files per compilation unit.
		The default is 10.

		This value is ignored if SetChunks is called.

		Mutually exclusive with ChunkFilesize().

		@type i: int
		@param i: Number of files per chunk
		"""
		self.settingsOverrides["chunk_size"] = i
		self.settingsOverrides["chunk_filesize"] = 0


	def ChunkFilesize( self, i ):
		"""
		Sets the maximum combined filesize for a chunk. The default is 500000, and this is the default behavior.

		This value is ignored if SetChunks is called.

		Mutually exclusive with ChunkNumFiles()

		@type i: int
		@param i: Maximum size per chunk in bytes.
		"""
		self.settingsOverrides["chunk_filesize"] = i
		self.settingsOverrides["chunk_size"] = i


	def ChunkTolerance( self, i ):
		"""
		B{If building using ChunkSize():}

		Set the number of modified files below which a chunk will be split into individual files.

		For example, if you set this to 3 (the default), then a chunk will be built as a chunk
		if more than three of its files need to be built; if three or less need to be built, they will
		be built individually to save build time.

		B{If building using ChunkFilesize():}

		Sets the total combined filesize of modified files within a chunk below which the chunk will be split into
		individual files.

		For example, if you set this to 150000 (the default), then a chunk will be built as a chunk if the total
		filesize of the files needing to be built exceeds 150kb. If less than 150kb worth of data needs to be built,
		they will be built individually to save time.

		@type i: int
		@param i: Number of files required to trigger chunk building.
		"""
		if "chunk_filesize" in self.settingsOverrides and self.settingsOverrides["chunk_filesize"] > 0:
			self.settingsOverrides["chunk_size_tolerance"] = i
		elif "chunk_size" in self.settingsOverrides and self.settingsOverrides["chunk_size"] > 0:
			self.settingsOverrides["chunk_tolerance"] = i
		else:
			log.LOG_WARN( "Chunk size and chunk filesize are both zero or negative, cannot set a tolerance." )


	def SetChunks( self, *chunks ):
		"""
		Explicitly set the chunks used as compilation units.

		NOTE that setting this will disable the automatic file gathering, so any files in the project directory that
		are not specified here will not be built.

		@type chunks: an arbitrary number of lists of strings
		@param chunks: Lists containing filenames of files to be built,
		relativel to the script's location, NOT the project working directory. Each list will be built as one chunk.
		"""
		chunks = list( chunks )
		self.settingsOverrides["forceChunks"] = chunks


	def ClearChunks( self ):
		"""Clears the explicitly set list of chunks and returns the behavior to the default."""
		self.settingsOverrides["forceChunks"] = []


	def HeaderRecursionLevel( self, i ):
		"""
		Sets the depth to search for header files. If set to 0, it will search with unlimited recursion to find included
		headers. Otherwise, it will travel to a depth of i to check headers. If set to 1, this will only check first-level
		headers and not check headers included in other headers; if set to 2, this will check headers included in headers,
		but not headers included by *those* headers; etc.

		This is very useful if you're using a large library (such as boost) or a very large project and are experiencing
		long waits prior to compilation.

		@type i: int
		@param i: Recursion depth for header examination
		"""
		self.settingsOverrides["header_recursion"] = i


	def IgnoreExternalHeaders( self ):
		"""
		If this option is set, external headers will not be checked or followed when building. Only headers within the
		base project's directory and its subdirectories will be checked. This will speed up header checking, but if you
		modify any external headers, you will need to manually --clean or --rebuild the project.
		"""
		self.settingsOverrides["ignore_external_headers"] = True


	def DisableWarnings( self ):
		"""
		Disables all warnings.
		"""
		self.settingsOverrides["no_warnings"] = True


	def DefaultTarget( self, s ):
		"""
		Sets the default target if none is specified. The default value for this is release.

		@type s: str
		@param s: Name of the target to build for this project if none is specified.
		"""
		self.settingsOverrides["default_target"] = s.lower( )


	def Precompile( self, *args ):
		"""
		Explicit list of header files to precompile. Disables chunk precompile when called.

		@type args: an arbitrary number of strings
		@param args: The files to precompile.
		"""
		self.settingsOverrides["precompile"] = []
		for arg in list( args ):
			self.settingsOverrides["precompile"].append( os.path.abspath( arg ) )
		self.settingsOverrides["chunk_precompile"] = False


	def PrecompileAsC( self, *args ):
		"""
		Specifies header files that should be compiled as C headers instead of C++ headers.

		@type args: an arbitrary number of strings
		@param args: The files to specify as C files.
		"""
		self.settingsOverrides["precompileAsC"] = []
		for arg in list( args ):
			self.settingsOverrides["precompileAsC"].append( os.path.abspath( arg ) )


	def ChunkPrecompile( self ):
		"""
		When this is enabled, all header files will be precompiled into a single "superheader" and included in all files.
		"""
		self.settingsOverrides["chunk_precompile"] = True


	def NoPrecompile( self, *args ):
		"""
		Disables precompilation and handles headers as usual.

		@type args: an arbitrary number of strings
		@param args: A list of files to disable precompilation for.
		If this list is empty, it will disable precompilation entirely.
		"""
		if "precompile_exclude" not in self.settingsOverrides:
			self.settingsOverrides["precompile_exclude"] = []

		args = list( args )
		if args:
			newargs = []
			for arg in args:
				if arg[0] != '/' and not arg.startswith( "./" ):
					arg = "./" + arg
				newargs.append( os.path.abspath( arg ) )
				self.settingsOverrides["precompile_exclude"] += newargs
		else:
			self.settingsOverrides["chunk_precompile"] = False
			self.settingsOverrides["precompile"] = []
			self.settingsOverrides["precompileAsC"] = []


	def EnableUnity( self ):
		"""
		Turns on true unity builds, combining all files into only one compilation unit.
		"""
		self.settingsOverrides["unity"] = True


	def StaticRuntime( self ):
		"""
		Link against a static C/C++ runtime library.
		"""
		self.settingsOverrides["static_runtime"] = True


	def SharedRuntime( self ):
		"""
		Link against a dynamic C/C++ runtime library.
		"""
		self.settingsOverrides["static_runtime"] = False


	def OutputArchitecture( self, arch ):
		"""
		Set the output architecture.

		@type arch: ArchitectureType
		@param arch: The desired architecture.
		"""
		self.settingsOverrides["outputArchitecture"] = arch

	def ExtraFiles( self, *args ):
		"""
		Adds additional files to be compiled that are not in the project directory.

		@type args: an arbitrary number of strings
		@param args: A list of files to add.
		"""
		if "extraFiles" not in self.settingsOverrides:
			self.settingsOverrides["extraFiles"] = []
		for arg in list( args ):
			for file in glob.glob( arg ):
				self.settingsOverrides["extraFiles"].append( os.path.abspath( file ) )


	def ClearExtraFiles(self):
		"""
		Clear the list of external files to compile.
		"""
		self.settingsOverrides["extraFiles"] = []


	def ExtraDirs( self, *args ):
		"""
		Adds additional directories to search for files in.

		@type args: an arbitrary number of strings
		@param args: A list of directories to search.
		"""
		if "extraDirs" not in self.settingsOverrides:
			self.settingsOverrides["extraDirs"] = []
		for arg in list( args ):
			self.settingsOverrides["extraDirs"].append( os.path.abspath( arg ) )


	def ClearExtraDirs(self):
		"""
		Clear the list of external directories to search.
		"""
		self.settingsOverrides["extraDirs"] = []

	def EnableWarningsAsErrors( self ):
		"""
		Promote all warnings to errors.
		"""
		self.settingsOverrides["warnings_as_errors"] = True


	def DisableWarningsAsErrors(self):
		"""
		Disable the promotion of warnings to errors.
		"""
		self.settingsOverrides["warnings_as_errors"] = False

	def DoNotChunkTogether(self, pattern, *additionalPatterns):
		"""
		Makes files matching the given patterns mutually exclusive for chunking.
		I.e., if you call this with DoNotChunkTogether("File1.cpp", "File2.cpp"), it guarantees
		File1 and File2 will never appear together in the same chunk. If you specify more than two files,
		or a pattern that matches more than two files, no two files in the list will ever appear together.

		@type pattern: string
		@param pattern: Pattern to search for files with (i.e., Source/*_Unchunkable.cpp)
		@type additionalPatterns: arbitrary number of optional strings
		@param additionalPatterns: Additional patterns to compile the list of mutually exclusive files with
		"""
		if "chunkMutexes" not in self.settingsOverrides:
			self.settingsOverrides["chunkMutexes"] = {}
		patterns = [pattern] + list(additionalPatterns)
		mutexFiles = set()
		for patternToMatch in patterns:
			for filename in glob.glob(patternToMatch):
				mutexFiles.add(os.path.abspath(filename))

		for file1 in mutexFiles:
			for file2 in mutexFiles:
				if file1 == file2:
					continue
				if file1 not in self.settingsOverrides["chunkMutexes"]:
					self.settingsOverrides["chunkMutexes"][file1] = set( [file2] )
				else:
					self.settingsOverrides["chunkMutexes"][file1].add(file2)

	def DoNotChunk(self, *files):
		"""
		Prevents the listed files (or files matching the listed patterns) from ever being placed
		in a chunk, ever.

		@type files: arbitrary number of strings
		@param files: filenames or patterns to exclude from chunking
		"""

		if "chunkExcludes" not in self.settingsOverrides:
			self.settingsOverrides["chunkExcludes"] = set()

		for pattern in list(files):
			for filename in glob.glob(pattern):
				self.settingsOverrides["chunkExcludes"].add(os.path.abspath(filename))

	def SupportedArchitectures(self, *architectures):
		"""
		Specifies the architectures that this project supports. This can be used to limit
		--all-architectures from building everything supported by the toolchain, if the project
		is not set up to support all of the toolchain's architectures.
		"""
		self.settingsOverrides["supportedArchitectures"] = set(architectures)


	def SetStaticLinkMode(self, mode):
		"""
		Determines how static links are handled. With the msvc toolchain, iterative link times of a project with many libraries
		can be significantly improved by setting this to L{StaticLinkMode.LinkIntermediateObjects}. This will cause the linker to link
		the .obj files used to make a library directly into the dependent project. Link times for full builds may be slightly slower,
		but this will allow incremental linking to function when libraries are being changed. (Usually, changing a .lib results
		in a full link.)

		On most toolchains, this defaults to L{StaticLinkMode.LinkLibs}. In debug mode only for the msvc toolchain, this defaults
		to L{StaticLinkMode.LinkIntermediateObjects}.

		@type mode: L{StaticLinkMode}
		@param mode: The link mode to set
		"""
		self.settingsOverrides["linkMode"] = mode
		self.settingsOverrides["linkModeSet"] = True

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
	def additional_args( parser ):
		"""
		Asks for additional command-line arguments to be added by the toolchain.

		@param parser: A parser for these arguments to be added to
		@type parser: argparse.argument_parser
		"""
		pass


	@abstractmethod
	def interrupt_exit_code( self ):
		"""
		Get the exit code that the compiler returns if the compile process is interrupted.

		@return: The linker's interrupt exit code
		@rtype: int
		"""
		pass

	@abstractmethod
	def GetValidArchitectures( self ):
		"""
		Get the list of architectures supported by this linker.

		@return: List of architectures
		@rtype: list[str]
		"""
		pass

	@abstractmethod
	def get_link_command( self, project, outputFile, objList ):
		"""
		Retrieves the command to be used for linking for this toolchain.

		@param project: The project currently being linked, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@param outputFile: The file that will be the result of the link operation.
		@type outputFile: str

		@param objList: List of objects being linked
		@type objList: list[str]

		@return: The fully formatted link command
		@rtype: str
		"""
		pass


	@abstractmethod
	def find_library( self, project, library, library_dirs, force_static, force_shared ):
		"""
		Search for a library and verify that it is installed.

		@param project: The project currently being checked, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@param library: The library being searched for
		@type library: str

		@param library_dirs: The directories to search for the library in
		@type library_dirs: list[str]

		@param force_static: Whether or not this library should be forced to link statically
		@type force_static: bool

		@param force_shared: Whether or not this library should be forced to link dynamically
		@type force_shared: bool

		@return: The location to the library if found, or None
		@rtype: str or None
		"""
		pass

	@abstractmethod
	def get_default_extension( self, projectType ):
		"""
		Get the default extension for a given L{csbuild.ProjectType} value.

		@param projectType: The requested output type
		@type projectType: L{csbuild.ProjectType}

		@return: The extension, including the . (i.e., .so, .a, .lib, .exe)
		@rtype: str
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
	def additional_args( parser ):
		"""
		Asks for additional command-line arguments to be added by the toolchain.

		@param parser: A parser for these arguments to be added to
		@type parser: argparse.argument_parser
		"""
		pass


	@abstractmethod
	def interrupt_exit_code( self ):
		"""
		Get the exit code that the compiler returns if the compile process is interrupted.

		@return: The compiler's interrupt exit code
		@rtype: int
		"""
		pass

	@abstractmethod
	def GetValidArchitectures( self ):
		"""
		Get the list of architectures supported by this compiler.

		@return: List of architectures
		@rtype: list[str]
		"""
		pass


	@abstractmethod
	def get_base_cxx_command( self, project ):
		"""
		Retrieves the BASE C++ compiler command for this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		@param project: The project currently being compiled, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@return: The base command string
		@rtype: str
		"""
		pass


	@abstractmethod
	def get_base_cc_command( self, project ):
		"""
		Retrieves the BASE C compiler command for this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		@param project: The project currently being compiled, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@return: The base command string
		@rtype: str
		"""
		pass


	@abstractmethod
	def get_extended_command( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		"""
		Retrieves the EXTENDED C/C++ compiler command for compiling a specific file

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		@param baseCmd: The project's base command as returned from L{get_base_cxx_command} or L{get_base_cc_command},
		as is appropriate for the file being compiled.
		@type baseCmd: str

		@param project: The project currently being compiled, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@param forceIncludeFile: A precompiled header that's being forcefully included.
		@type forceIncludeFile: str

		@param outObj: The object file to be generated by this command
		@type outObj: str

		@param inFile: The file being compiled
		@type inFile: str

		@return: The extended command string, including the base command string
		@rtype: str
		"""
		pass


	@abstractmethod
	def get_base_cxx_precompile_command( self, project ):
		"""
		Retrieves the BASE C++ compiler command for precompiling headers in this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		@param project: The project currently being compiled, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@return: The base command string
		@rtype: str
		"""
		pass


	@abstractmethod
	def get_base_cc_precompile_command( self, project ):
		"""
		Retrieves the BASE C compiler command for precompiling headers in this project.

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		@param project: The project currently being compiled, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@return: The base command string
		@rtype: str
		"""
		pass


	@abstractmethod
	def get_extended_precompile_command( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		"""
		Retrieves the EXTENDED C/C++ compiler command for compiling a specific precompiled header

		The difference between the base command and the extended command is as follows:
			1. The base command does not include any specific files in it
			2. The base command should be seen as the full list of compiler settings that will force a full recompile
			if ANY of them are changed. For example, optimization settings should be included here because a change to
			that setting should cause all object files to be regenerated.

		Thus, anything that can be changed without forcing a clean rebuild should be in the extended command, not the base.

		@param baseCmd: The project's base command as returned from L{get_base_cxx_command} or L{get_base_cc_command},
		as is appropriate for the file being compiled.
		@type baseCmd: str

		@param project: The project currently being compiled, which can be used to retrieve any needed information.
		@type project: L{csbuild.projectSettings.projectSettings}

		@param forceIncludeFile: Currently unused for precompiled headers.
		@type forceIncludeFile: str

		@param outObj: The object file to be generated by this command
		@type outObj: str

		@param inFile: The file being compiled
		@type inFile: str

		@return: The extended command string, including the base command string
		@rtype: str
		"""
		pass


	@abstractmethod
	def get_pch_file( self, fileName ):
		"""
		Get the properly formatted precompiled header output file for a given header input.

		@param fileName: The input header
		@type fileName: str

		@return: The formatted output file (i.e., "header.pch" or "header.gch")
		@rtype: str
		"""
		pass


	@abstractmethod
	def get_preprocess_command(self, baseCmd, project, inFile ):
		return ""


	@abstractmethod
	def pragma_message(self, message):
		return ""


	def get_extra_post_preprocess_flags(self):
		return ""


	def get_post_preprocess_sanitation_lines(self):
		return []

	@abstractmethod
	def get_obj_ext(self):
		"""
		Get the extension for intermediate object files, including the .
		"""
		pass


class toolchain( SettingsOverrider ):
	"""
	Base class used for custom toolchains
	To create a new toolchain, inherit from this class, and then use
	L{csbuild.RegisterToolchain()<csbuild.RegisterToolchain>}
	"""
	def __init__( self ):
		"""
		Default constructor
		"""

		self.settingsOverrides = { }
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

		@type args: arbitrary number of strings
		@param args: The list of tools to act on

		@return: A proxy object that enables functions to be applied to one or more specific tools.
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

		@return: a copy of this toolchain
		@rtype: toolchain
		"""
		ret = SettingsOverrider.copy(self)

		for kvp in self.tools.items():
			ret.tools[kvp[0]] = kvp[1].copy()

		if self.activeToolName:
			ret.activeToolName = self.activeToolName
			if ret.activeToolName:
				ret.activeTool = ret.tools[ret.activeToolName]

		return ret
