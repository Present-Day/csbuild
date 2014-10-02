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
B{ProjectSettings module}

Defines the projectSettings class.

@var currentProject: The current project being built. Note that if this is accessed outside of an @project
block, the project returned will only be a temporary variable that will not be valid for compilation
@type currentProject: projectSettings

@var rootGroup: This is the top-level project group that all projects and project groups fall under.
It has no name and is NOT itself a valid or "real" group.
@type rootGroup: ProjectGroup

@var currentGroup: The current group that's being populated
@type currentGroup: ProjectGroup
"""

import csbuild

import fnmatch
import os
import re
import hashlib
import time
import sys
import math
import platform
import glob
import itertools
import threading

from . import log
from . import _shared_globals
from . import _utils

class projectSettings( object ):
	"""
	Contains settings for the project

	@ivar name: The project's name
	@type name: str

	@ivar key: A unique key made by combining project name and target
	@type key: str

	@ivar workingDirectory: The directory containing all of the project's files
	@type workingDirectory: str

	@ivar linkDepends: The projects that this one depends on for linking
	@type linkDepends: list[str]

	@ivar srcDepends: The projects that this one depends on for compiling
	@type srcDepends: str

	@ivar func: The project's settings function - the function wrapped in the @project decorator
	@type func: function

	@ivar libraries: The libraries the project will link against
	@type libraries: list[str]

	@ivar static_libraries: The libraries the project will forcibly statically link against
	@type static_libraries: list[str]

	@ivar shared_libraries: The libraries the project will forcibly statically link against
	@type shared_libraries: list[str]

	@ivar include_dirs: Directories to search for included headers in
	@type include_dirs: list[str]

	@ivar library_dirs: Directories to search for libraries in
	@type library_dirs: list[str]

	@ivar opt_level: Optimization level for this project
	@type opt_level: csbuild.OptimizationLevel

	@ivar debug_level: Debug level for this project
	@type debug_level: csbuild.DebugLevel

	@ivar defines: #define declarations for this project
	@type defines: list[str]

	@ivar undefines: #undef declarations for this project
	@type undefines: list[str]

	@ivar cxx: C++ compiler executable for this project
	@type cxx: str

	@ivar cc: C compiler executable for this project
	@type cc: str

	@ivar hasCppFiles: Whether or not the project includes C++ files
	@type hasCppFiles: bool

	@ivar obj_dir: Output directory for intermediate object files
	@type obj_dir: str

	@ivar output_dir: Output directory for the final output file
	@type output_dir: str

	@ivar csbuild_dir: Output directory for csbuild internal data, subdir of obj_dir
	@type csbuild_dir: str

	@ivar output_name: Final filename to be generated for this project
	@type output_name: str

	@ivar header_subdir: Subdirectory that headers live in for this project
	@type header_subdir: str

	@ivar sources: Source files within this project that are being compiled during this run
	@type sources: list[str]

	@ivar allsources: All source files within this project
	@type allsources: list[str]

	@ivar allheaders: Headers within this project
	@type allheaders: list[str]

	@ivar type: Project type
	@type type: L{csbuild.ProjectType}

	@ivar ext: Extension override for output
	@type ext: str or None

	@ivar profile: Whether or not to optimize for profiling
	@type profile: bool

	@ivar cpp_compiler_flags: Literal flags to pass to the C++ compiler
	@type cpp_compiler_flags: list[str]

	@ivar c_compiler_flags: Literal flags to pass to the C compiler
	@type c_compiler_flags: list[str]

	@ivar linker_flags: Literal flags to pass to the linker
	@type linker_flags: list[str]

	@ivar exclude_dirs: Directories excluded from source file discovery
	@type exclude_dirs: list[str]

	@ivar exclude_files: Files excluded from source file discovery
	@type exclude_files: list[str]

	@ivar output_dir_set: Whether or not the output directory has been set
	@type output_dir_set: bool

	@ivar obj_dir_set: Whether or not the object directory has been set
	@type obj_dir_set: bool

	@ivar debug_set: Whether or not debug settings have been set
	@type debug_set: bool

	@ivar opt_set: Whether or not optimization settings have been set
	@type opt_set: bool

	@ivar allpaths: All the paths used to contain all headers included by this project
	@type allpaths: list[str]

	@ivar chunks: Compiled list of chunks to be compiled in this project
	@type chunks: list[str]

	@ivar chunksByFile: Dictionary to get the list of files in a chunk from its filename
	@type chunksByFile: dict[str, list[str]]

	@ivar use_chunks: Whether or not to use chunks
	@type use_chunks: bool

	@ivar chunk_tolerance: minimum number of modified files needed to build a chunk as a chunk
	@type chunk_tolerance: int

	@ivar chunk_size: number of files per chunk
	@type chunk_size: int

	@ivar chunk_filesize: maximum file size of a built chunk, in bytes
	@type chunk_filesize: int

	@ivar chunk_size_tolerance: minimum total filesize of modified files needed to build a chunk as a chunk
	@type chunk_size_tolerance: int

	@ivar header_recursion: Depth to recurse when building header information
	@type header_recursion: int

	@ivar ignore_external_headers: Whether or not to ignore external headers when building header information
	@type ignore_external_headers: bool

	@ivar default_target: The target to be built when none is specified
	@type default_target: str

	@ivar chunk_precompile: Whether or not to precompile all headers in the project
	@type chunk_precompile: bool

	@ivar precompile: List of files to precompile
	@type precompile: list[str]

	@ivar precompile_exclude: List of files NOT to precompile
	@type precompile_exclude: list[str]

	@ivar cppheaderfile: The C++ precompiled header that's been built (if any)
	@type cppheaderfile: str

	@ivar cheaderfile: The C precompiled header that's been built (if any)
	@type cheaderfile: str

	@ivar needs_cpp_precompile: Whether or not the C++ precompiled header needs to be rebuilt during this compile
	@type needs_cpp_precompile: bool

	@ivar needs_c_precompile: Whether or not the C++ precompiled header needs to be rebuilt during this compile
	@type needs_c_precompile: bool

	@ivar unity: Whether or not to build in full unity mode (all files included in one translation unit)
	@type unity: bool

	@ivar precompile_done: Whether or not the project's precompile step has been completed
	@type precompile_done: bool

	@ivar no_warnings: Whether or not to disable all warnings for this project
	@type no_warnings: bool

	@ivar toolchains: All toolchains enabled for this project
	@type toolchains: dict[str, csbuild.toolchain.toolchain]

	@ivar cxxcmd: Base C++ compile command, returned from toolchain.get_base_cxx_command
	@type cxxcmd: str

	@ivar cccmd: Base C compile command, returned from toolchain.get_base_cc_command
	@type cccmd: str

	@ivar cxxpccmd: Base C++ precompile command, returned from toolchain.get_base_cxx_precompile_command
	@type cxxpccmd: str

	@ivar ccpccmd: Base C precompile command, returned from toolchain.get_base_cc_precompile_command
	@type ccpccmd: str

	@ivar recompile_all: Whether or not conditions have caused the entire project to need recompilation
	@type recompile_all: bool

	@ivar targets: List of targets in this project with their associated settings functions, decorated with @target
	@type targets: dict[str, list[function]]

	@ivar targetName: The target name for this project as it's currently being built
	@type targetName: str

	@ivar final_chunk_set: The list of chunks to be built after building all chunks, determining whether or not to build
	them as chunks, etc.
	@type final_chunk_set: list[str]

	@ivar compiles_completed: The number of files that have been compiled (successfully or not) at this point in the
	compile process. Note that this variable is modified in multiple threads and should be handled within project.mutex
	@type compiles_completed: int

	@ivar compile_failed: Whether or not ANY compilation unit has failed to successfully compile in this build
	@type compile_failed: bool

	@ivar static_runtime: Whether or not to link against a static runtime
	@type static_runtime: bool

	@ivar cppheaders: List of C++ headers
	@type cppheaders: list[str]

	@ivar cheaders: List of C headers
	@type cheaders: list[str]

	@ivar activeToolchainName: The name of the currently active toolchain
	@type activeToolchainName: str

	@ivar activeToolchain: The actual currently active toolchain
	@type activeToolchain: csbuild.toolchain.toolchain

	@ivar warnings_as_errors: Whether all warnings should be treated as errors
	@type warnings_as_errors: bool

	@ivar built_something: Whether or not ANY file has been compiled in this build
	@type built_something: bool

	@ivar outputArchitecture: The architecture to build against
	@type outputArchitecture: csbuild.ArchitectureType

	@ivar library_locs: evaluated locations of the project's libraries
	@type library_locs: list[str]

	@ivar scriptPath: The location of the script file this project is defined in
	@type scriptPath: str

	@ivar mutex: A mutex used to control modification of project data across multiple threads
	@type mutex: threading.Lock

	@ivar preBuildStep: A function that will be executed before compile of this project begins
	@type preBuildStep: function

	@ivar postBuildStep: A function that will be executed after compile of this project ends
	@type postBuildStep: function

	@ivar parentGroup: The group this project is contained within
	@type parentGroup: ProjectGroup

	@ivar state: Current state of the project
	@type state: L{_shared_globals.ProjectState}

	@ivar startTime: The time the project build started
	@type startTime: float

	@ivar endTime: The time the project build ended
	@type endTime: float

	@type extraFiles: list[str]
	@ivar extraFiles: Extra files being compiled, these will be rolled into project.sources, so use that instead

	@type extraDirs: list[str]
	@ivar extraDirs: Extra directories used to search for files

	@type extraObjs: list[str]
	@ivar extraObjs: Extra objects to pass to the linker

	@undocumented: prepareBuild
	@undocumented: __getattribute__
	@undocumented: __setattr__
	@undocumented: get_files
	@undocumented: get_full_path
	@undocumented: get_included_files
	@undocumented: follow_headers
	@undocumented: follow_headers2
	@undocumented: should_recompile
	@undocumented: check_libraries
	@undocumented: make_chunks
	@undocumented: get_chunk
	@undocumented: save_md5
	@undocumented: save_md5s
	@undocumented: precompile_headers
	@undocumented: copy
	@undocumented: CanJoinChunk

	@note: Toolchains can define additional variables that will show up on this class's
	instance variable list when that toolchain is active. See toolchain documentation for
	more details on what additional instance variables are available.
	"""
	def __init__( self ):
		"""
		Default projectSettings constructor
		"""
		self.name = ""
		self.priority = -1
		self.ignoreDependencyOrdering = False
		self.key = ""
		self.workingDirectory = "./"
		self.linkDepends = []
		self.linkDependsIntermediate = []
		self.linkDependsFinal = []
		self.reconciledLinkDepends = set()
		self.srcDepends = []
		self.srcDependsIntermediate = []
		self.srcDependsFinal = []
		self.func = None

		self.libraries = set()
		self.static_libraries = set()
		self.shared_libraries = set()
		self.include_dirs = []
		self.library_dirs = []

		self.opt_level = csbuild.OptimizationLevel.Disabled
		self.debug_level = csbuild.DebugLevel.Disabled
		self.defines = []
		self.undefines = []
		self.cxx = ""
		self.cc = ""
		self.hasCppFiles = False

		self.obj_dir = "."
		self.output_dir = "."
		self.csbuild_dir = ".csbuild"
		self.output_name = ""
		self.install_output = False
		self.install_headers = False
		self.header_subdir = ""

		self.sources = []
		self.allsources = []
		self.allheaders = []

		self.type = csbuild.ProjectType.Application
		self.ext = None
		self.profile = False

		self.cpp_compiler_flags = []
		self.c_compiler_flags = []
		self.linker_flags = []

		self.exclude_dirs = []
		self.exclude_files = []

		self.output_dir_set = False
		self.obj_dir_set = False
		self.debug_set = False
		self.opt_set = False

		self.allpaths = []
		self.chunks = []
		self.forceChunks = []
		self.chunksByFile = {}

		self.use_chunks = True
		self.chunk_tolerance = 3
		self.chunk_size = 0
		self.chunk_filesize = 512000
		self.chunk_size_tolerance = 128000

		self.header_recursion = 0
		self.ignore_external_headers = False

		self.default_target = "release"

		self.chunk_precompile = True
		self.precompile = []
		self.precompileAsC = []
		self.precompile_exclude = []
		self.cppheaderfile = ""
		self.cheaderfile = ""
		self.needs_cpp_precompile = False
		self.needs_c_precompile = False

		self.unity = False

		self.precompile_done = False
		self.precompile_started = True

		self.no_warnings = False

		self.toolchains = { }

		self.cxxcmd = ""  # return value of get_base_cxx_command
		self.cccmd = ""  # return value of get_base_cc_command
		self.cxxpccmd = ""  # return value of get_base_cxx_precompile_command
		self.ccpccmd = ""  # return value of get_base_cc_precompile_command

		self.recompile_all = False

		self.targets = {}
		self.archFuncs = {}

		self.targetName = ""

		self.final_chunk_set = []

		self.compiles_completed = 0

		self.compile_failed = False
		self.precompileFailed = False

		self.static_runtime = False

		self.cheaders = []
		self.cppheaders = []

		self.activeToolchainName = None
		self.activeToolchain = None

		self.warnings_as_errors = False

		self.built_something = False

		self.outputArchitecture = ""

		self.library_locs = []

		self.scriptPath = ""
		self.scriptFile = ""

		self.mutex = threading.Lock( )

		self.postBuildStep = None
		self.preBuildStep = None
		self.prePrepareBuildStep = None
		self.postPrepareBuildStep = None
		self.preLinkStep = None
		self.preMakeStep = None
		self.postMakeStep = None

		self.parentGroup = currentGroup

		self.extraFiles = []
		self.extraDirs = []
		self.extraObjs = []

		self.cExtensions = {".c"}
		self.cppExtensions = {".cpp", ".cxx", ".cc", ".cp", ".c++"}
		self.asmExtensions = {".s", ".asm"}
		self.cHeaderExtensions = set()
		self.cppHeaderExtensions = {".hpp", ".hxx", ".hh", ".hp", ".h++"}
		self.ambiguousHeaderExtensions = {".h", ".inl"}

		self.chunkMutexes = {}
		self.chunkExcludes = set()

		self.fileOverrides = {}
		self.fileOverrideSettings = {}
		self.ccOverrideCmds = {}
		self.cxxOverrideCmds = {}
		self.ccpcOverrideCmds = {}
		self.cxxpcOverrideCmds = {}

		self.supportedArchitectures = set()
		self.supportedToolchains = set()

		self.linkMode = csbuild.StaticLinkMode.LinkLibs
		self.linkModeSet = False

		self.splitChunks = {}

		#GUI support
		self.state = _shared_globals.ProjectState.PENDING
		self.startTime = 0
		self.buildEnd = 0
		self.linkQueueStart = 0
		self.linkStart = 0
		self.endTime = 0
		self.compileOutput = {}
		self.compileErrors = {}
		self.parsedErrors = {}
		self.fileStatus = {}
		self.fileStart = {}
		self.fileEnd = {}
		self.cpchcontents = []
		self.cpppchcontents = []
		self.updated = False
		self.warnings = 0
		self.errors = 0
		self.warningsByFile = {}
		self.errorsByFile = {}
		self.times = {}
		self.summedTimes = {}
		self.linkCommand = ""
		self.compileCommands = {}

		self.linkOutput = ""
		self.linkErrors = ""
		self.parsedLinkErrors = None

	def prepareBuild( self ):
		log.LOG_BUILD( "Preparing tasks for {} ({} {}/{})...".format( self.output_name, self.targetName, self.outputArchitecture, self.activeToolchainName ) )
		wd = os.getcwd( )
		os.chdir( self.workingDirectory )

		self.activeToolchain = self.toolchains[self.activeToolchainName]

		self.activeToolchain.SetActiveTool("linker")
		self.output_dir = os.path.abspath( self.output_dir ).format(project=self)
		if not os.access(self.output_dir, os.F_OK):
			os.makedirs(self.output_dir)

		alteredLibraryDirs = []
		for directory in self.library_dirs:
			directory = directory.format(project=self)
			if not os.access(directory, os.F_OK):
				log.LOG_WARN("Library path {} does not exist!".format(directory))
			alteredLibraryDirs.append(directory)
		self.library_dirs = alteredLibraryDirs

		#Kind of hacky. The libraries returned here are a temporary object that's been created by combining
		#base, toolchain, and architecture information. We need to bind it to something more permanent so we
		#can actually modify it. Assigning it to itself makes that temporary list permanent.
		self.libraries = self.libraries

		for dep in self.reconciledLinkDepends:
			proj = _shared_globals.projects[dep]
			if proj.type == csbuild.ProjectType.StaticLibrary and self.linkMode == csbuild.StaticLinkMode.LinkIntermediateObjects:
				continue
			self.libraries.add(proj.output_name.split(".")[0])

		self.activeToolchain.SetActiveTool("compiler")
		self.obj_dir = os.path.abspath( self.obj_dir ).format(project=self)
		self.csbuild_dir = os.path.join( self.obj_dir, ".csbuild" )

		alteredIncludeDirs = []
		for directory in self.include_dirs:
			directory = directory.format(project=self)
			if not os.access(directory, os.F_OK):
				log.LOG_WARN("Include path {} does not exist!".format(directory))
			alteredIncludeDirs.append(directory)
		self.include_dirs = alteredIncludeDirs

		def apply_macro(l):
			alteredList = []
			for s in l:
				s = os.path.abspath(s.format(project=self))
				alteredList.append(s)
			return alteredList

		self.exclude_dirs = apply_macro(self.exclude_dirs)

		self.extraFiles = apply_macro(self.extraFiles)
		self.extraDirs = apply_macro(self.extraDirs)
		self.extraObjs = apply_macro(self.extraObjs)
		self.exclude_files = apply_macro(self.exclude_files)
		self.precompile = apply_macro(self.precompile)
		self.precompileAsC = apply_macro(self.precompileAsC)
		self.precompile_exclude = apply_macro(self.precompile_exclude)

		self.header_subdir = self.header_subdir.format(project=self)

		self.exclude_dirs.append( self.csbuild_dir )

		global currentProject
		currentProject = self

		self.activeToolchain.prePrepareBuildStep(self)
		if self.prePrepareBuildStep:
			log.LOG_BUILD( "Running pre-PrepareBuild step for {} ({} {}/{})".format( self.output_name, self.targetName, self.outputArchitecture, self.activeToolchainName ) )
			self.prePrepareBuildStep(self)

		self.activeToolchain.SetActiveTool("linker")
		if self.ext is None:
			self.ext = self.activeToolchain.Linker().get_default_extension( self.type )

		self.output_name += self.ext
		self.activeToolchain.SetActiveTool("compiler")

		if not os.access(self.csbuild_dir , os.F_OK):
			os.makedirs( self.csbuild_dir )

		for item in self.fileOverrideSettings.items():
			item[1].activeToolchain = item[1].toolchains[self.activeToolchainName]
			self.ccOverrideCmds[item[0]] = self.activeToolchain.Compiler().get_base_cc_command( item[1] )
			self.cxxOverrideCmds[item[0]] = self.activeToolchain.Compiler().get_base_cxx_command( item[1] )
			self.ccpcOverrideCmds[item[0]] = self.activeToolchain.Compiler().get_base_cc_precompile_command( item[1] )
			self.cxxpcOverrideCmds[item[0]] = self.activeToolchain.Compiler().get_base_cxx_precompile_command( item[1] )

		self.cccmd = self.activeToolchain.Compiler().get_base_cc_command( self )
		self.cxxcmd = self.activeToolchain.Compiler().get_base_cxx_command( self )
		self.ccpccmd = self.activeToolchain.Compiler().get_base_cc_precompile_command( self )
		self.cxxpccmd = self.activeToolchain.Compiler().get_base_cxx_precompile_command( self )

		cmdfile = os.path.join( self.csbuild_dir, "{}.csbuild".format( self.targetName ) )
		cmd = ""
		if os.access(cmdfile , os.F_OK):
			with open( cmdfile, "r" ) as f:
				cmd = f.read( )

		if self.cxxcmd + self.cccmd != cmd or _shared_globals.rebuild:
			self.recompile_all = True
			with open( cmdfile, "w" ) as f:
				f.write( self.cxxcmd + self.cccmd )


		self.RediscoverFiles()

		if self.name not in self.parentGroup.projects:
			self.parentGroup.projects[self.name] = {}

		if self.activeToolchainName not in self.parentGroup.projects[self.name]:
			self.parentGroup.projects[self.name][self.activeToolchainName] = {}

		if self.targetName not in self.parentGroup.projects[self.name][self.activeToolchainName]:
			self.parentGroup.projects[self.name][self.activeToolchainName][self.targetName] = {}

		self.parentGroup.projects[self.name][self.activeToolchainName][self.targetName][self.outputArchitecture] = self

		self.activeToolchain.postPrepareBuildStep(self)
		if self.postPrepareBuildStep:
			log.LOG_BUILD( "Running post-PrepareBuild step for {} ({} {}/{})".format( self.output_name, self.targetName, self.outputArchitecture, self.activeToolchainName ) )
			self.postPrepareBuildStep(self)

		os.chdir( wd )

	def RediscoverFiles(self):
		"""
		Force a re-run of the file discovery process. Useful if a postPrepareBuild step adds additional files to the project.
		This will have no effect when called from any place other than a postPrepareBuild step.
		"""
		self.sources = []
		if not self.forceChunks:
			self.allsources = []
			self.allheaders = []
			self.cppheaders = []
			self.cheaders = []

			self.get_files( self.allsources, self.cppheaders, self.cheaders )
			if self.extraFiles:
				log.LOG_INFO("Appending extra files {}".format(self.extraFiles))
				self.allsources += self.extraFiles
			self.allheaders = self.cppheaders + self.cheaders

			if not self.allsources:
				return

			#We'll do this even if _use_chunks is false, because it simplifies the linker logic.
			self.chunks = self.make_chunks( self.allsources )
		else:
			self.allsources = list( itertools.chain( *self.forceChunks ) )

		if not _shared_globals.CleanBuild and not _shared_globals.do_install and csbuild.get_option(
				"generate_solution" ) is None:
			for source in self.allsources:
				if self.should_recompile( source ):
					self.sources.append( source )
		else:
			self.sources = list( self.allsources )

		_shared_globals.allfiles |= set(self.sources)

	def __getattribute__( self, name ):
		activeToolchain = object.__getattribute__( self, "activeToolchain" )
		if activeToolchain:
			if activeToolchain.activeTool and name in activeToolchain.activeTool.settingsOverrides:
				ret = activeToolchain.activeTool.settingsOverrides[name]

				if ret:
					if isinstance( ret, dict ):
						ret2 = object.__getattribute__( self, name )
						ret2.update( ret )
						return ret2
					elif isinstance( ret, list ):
						return ret + object.__getattribute__( self, name )
					elif isinstance( ret, set ):
						return ret | object.__getattribute__( self, name )

				return ret
			elif name in activeToolchain.settingsOverrides:
				ret = activeToolchain.settingsOverrides[name]

				if ret:
					if isinstance( ret, dict ):
						ret2 = object.__getattribute__( self, name )
						ret2.update( ret )
						return ret2
					elif isinstance( ret, list ):
						return ret + object.__getattribute__( self, name )
					elif isinstance( ret, set ):
						return ret | object.__getattribute__( self, name )

				return ret
		return object.__getattribute__( self, name )


	def __setattr__( self, name, value ):
		if name == "state":
			with self.mutex:
				self.updated = True

		if hasattr( self, "activeToolchain" ):
			activeToolchain = object.__getattribute__( self, "activeToolchain" )
			if activeToolchain:
				if activeToolchain.activeTool and name in activeToolchain.activeTool.settingsOverrides:
					del activeToolchain.activeTool.settingsOverrides[name]
				if name in activeToolchain.settingsOverrides:
					del activeToolchain.settingsOverrides[name]
		object.__setattr__( self, name, value )


	def copy( self ):
		ret = projectSettings( )
		toolchains = { }
		for kvp in self.toolchains.items( ):
			toolchains[kvp[0]] = kvp[1].copy( )

		ret.__dict__ = {
			"name": self.name,
			"priority" : self.priority,
			"ignoreDependencyOrdering" : self.ignoreDependencyOrdering,
			"key": self.key,
			"workingDirectory": self.workingDirectory,
			"linkDepends": list( self.linkDepends ),
			"linkDependsIntermediate": list( self.linkDependsIntermediate ),
			"linkDependsFinal": list( self.linkDependsFinal ),
			"reconciledLinkDepends" : set( self.reconciledLinkDepends ),
			"srcDepends": list( self.srcDepends ),
			"srcDependsIntermediate": list( self.srcDependsIntermediate ),
			"srcDependsFinal": list( self.srcDependsFinal ),
			"func": self.func,
			"libraries": set( self.libraries ),
			"static_libraries": set( self.static_libraries ),
			"shared_libraries": set( self.shared_libraries ),
			"include_dirs": list( self.include_dirs ),
			"library_dirs": list( self.library_dirs ),
			"opt_level": self.opt_level,
			"debug_level": self.debug_level,
			"defines": list( self.defines ),
			"undefines": list( self.undefines ),
			"cxx": self.cxx,
			"cc": self.cc,
			"hasCppFiles": self.hasCppFiles,
			"obj_dir": self.obj_dir,
			"output_dir": self.output_dir,
			"csbuild_dir": self.csbuild_dir,
			"output_name": self.output_name,
			"install_output": self.install_output,
			"install_headers": self.install_headers,
			"header_subdir": self.header_subdir,
			"sources": list( self.sources ),
			"allsources": list( self.allsources ),
			"allheaders": list( self.allheaders ),
			"type": self.type,
			"ext": self.ext,
			"profile": self.profile,
			"cpp_compiler_flags": list( self.cpp_compiler_flags ),
			"c_compiler_flags": list( self.c_compiler_flags ),
			"linker_flags": list( self.linker_flags ),
			"exclude_dirs": list( self.exclude_dirs ),
			"exclude_files": list( self.exclude_files ),
			"output_dir_set": self.output_dir_set,
			"obj_dir_set": self.obj_dir_set,
			"debug_set": self.debug_set,
			"opt_set": self.opt_set,
			"allpaths": list( self.allpaths ),
			"chunks": list( self.chunks ),
			"forceChunks": list( self.forceChunks ),
			"chunksByFile" : dict( self.chunksByFile ),
			"use_chunks": self.use_chunks,
			"chunk_tolerance": self.chunk_tolerance,
			"chunk_size": self.chunk_size,
			"chunk_filesize": self.chunk_filesize,
			"chunk_size_tolerance": self.chunk_size_tolerance,
			"header_recursion": self.header_recursion,
			"ignore_external_headers": self.ignore_external_headers,
			"default_target": self.default_target,
			"chunk_precompile": self.chunk_precompile,
			"precompile": list( self.precompile ),
			"precompileAsC": list( self.precompileAsC ),
			"precompile_exclude": list( self.precompile_exclude ),
			"cppheaderfile": self.cppheaderfile,
			"cheaderfile": self.cheaderfile,
			"unity": self.unity,
			"precompile_done": self.precompile_done,
			"precompile_started": self.precompile_started,
			"no_warnings": self.no_warnings,
			"toolchains": toolchains,
			"cxxcmd": self.cxxcmd,
			"cccmd": self.cccmd,
			"recompile_all": self.recompile_all,
			"targets": {},
			"archFuncs" : {},
			"fileOverrides" : {},
			"fileOverrideSettings" : {},
			"ccOverrideCmds" : dict(self.ccOverrideCmds),
			"cxxOverrideCmds" : dict(self.cxxOverrideCmds),
			"ccpcOverrideCmds" : dict(self.ccpcOverrideCmds),
			"cxxpcOverrideCmds" : dict(self.cxxpcOverrideCmds),
			"targetName": self.targetName,
			"final_chunk_set": list( self.final_chunk_set ),
			"needs_c_precompile": self.needs_c_precompile,
			"needs_cpp_precompile": self.needs_cpp_precompile,
			"compiles_completed": self.compiles_completed,
			"compile_failed": self.compile_failed,
			"precompileFailed": self.precompileFailed,
			"static_runtime": self.static_runtime,
			"cheaders": list( self.cheaders ),
			"cppheaders": list( self.cppheaders ),
			"activeToolchainName": self.activeToolchainName,
			"activeToolchain": None,
			"warnings_as_errors": self.warnings_as_errors,
			"built_something": self.built_something,
			"outputArchitecture": self.outputArchitecture,
			"library_locs": list( self.library_locs ),
			"scriptPath": self.scriptPath,
			"scriptFile": self.scriptFile,
			"mutex": threading.Lock( ),
			"preBuildStep" : self.preBuildStep,
			"postBuildStep" : self.postBuildStep,
			"prePrepareBuildStep" : self.prePrepareBuildStep,
			"postPrepareBuildStep" : self.postPrepareBuildStep,
			"preLinkStep" : self.preLinkStep,
			"preMakeStep" : self.preMakeStep,
			"postMakeStep" : self.postMakeStep,
			"parentGroup" : self.parentGroup,
			"extraFiles": list(self.extraFiles),
			"extraDirs": list(self.extraDirs),
			"extraObjs": list(self.extraObjs),
			"linkMode" : self.linkMode,
			"linkModeSet" : self.linkModeSet,
			"splitChunks" : dict(self.splitChunks),
			"state" : self.state,
			"startTime" : self.startTime,
			"buildEnd" : self.buildEnd,
			"linkQueueStart" : self.linkQueueStart,
			"linkStart" : self.linkStart,
			"endTime" : self.endTime,
			"compileOutput" : dict(self.compileOutput),
			"compileErrors" : dict(self.compileErrors),
			"parsedErrors" : dict(self.parsedErrors),
			"fileStatus" : dict(self.fileStatus),
			"fileStart" : dict(self.fileStart),
			"fileEnd" : dict(self.fileEnd),
			"cpchcontents" : list(self.cpchcontents),
			"cpppchcontents" : list(self.cpppchcontents),
			"updated" : self.updated,
			"warnings" : self.warnings,
			"errors" : self.errors,
			"warningsByFile" : self.warningsByFile,
			"errorsByFile" : self.errorsByFile,
			"linkOutput" : self.linkOutput,
			"linkErrors" : self.linkErrors,
			"parsedLinkErrors" : self.parsedLinkErrors,
			"cExtensions" : set(self.cExtensions),
			"cppExtensions" : set(self.cppExtensions),
			"asmExtensions" : set(self.asmExtensions),
			"cHeaderExtensions" : set(self.cHeaderExtensions),
			"cppHeaderExtensions" : set(self.cppHeaderExtensions),
			"ambiguousHeaderExtensions" : set(self.ambiguousHeaderExtensions),
			"chunkMutexes" : {},
			"chunkExcludes" : set(self.chunkExcludes),
			"times" : self.times,
			"summedTimes" : self.summedTimes,
			"supportedArchitectures" : set(self.supportedArchitectures),
			"supportedToolchains" : set(self.supportedToolchains),
			"linkCommand" : self.linkCommand,
			"compileCommands" : dict(self.compileCommands)
		}

		for name in self.targets:
			ret.targets.update( { name : list( self.targets[name] ) } )

		for arch in self.archFuncs:
			ret.archFuncs.update( { arch : list( self.archFuncs[arch] ) } )

		for srcFile in self.chunkMutexes:
			ret.chunkMutexes.update( { srcFile : set( self.chunkMutexes[srcFile] ) } )

		for file in self.fileOverrides:
			ret.fileOverrides.update( { file : list( self.fileOverrides[file] ) } )

		for file in self.fileOverrideSettings:
			ret.fileOverrideSettings.update( { file : self.fileOverrideSettings[file].copy() } )

		return ret


	def get_files( self, sources = None, headers = None, cheaders = None ):
		"""
		Steps through the current directory tree and finds all of the source and header files, and returns them as a list.
		Accepts two lists as arguments, which it populates. If sources or headers are excluded from the parameters, it will
		ignore files of the relevant types.
		"""

		exclude_files = set( )
		exclude_dirs = set( )
		ambiguousHeaders = set()

		for exclude in self.exclude_files:
			exclude_files |= set( glob.glob( exclude ) )

		for exclude in self.exclude_dirs:
			exclude_dirs |= set( glob.glob( exclude ) )

		for sourceDir in [ '.' ] + self.extraDirs:
			for root, dirnames, filenames in os.walk( sourceDir ):
				absroot = os.path.abspath( root )
				if absroot in exclude_dirs:
					if absroot != self.csbuild_dir:
						log.LOG_INFO( "Skipping dir {0}".format( root ) )
					continue
				if ".csbuild" in root:
					continue
				if absroot == self.csbuild_dir or absroot.startswith( self.csbuild_dir ):
					continue
				bFound = False
				for testDir in exclude_dirs:
					if absroot.startswith( testDir ):
						bFound = True
						break
				if bFound:
					if not absroot.startswith( self.csbuild_dir ):
						log.LOG_INFO( "Skipping dir {0}".format( root ) )
					continue
				log.LOG_INFO( "Looking in directory {0}".format( root ) )
				if sources is not None:
					for extension in self.cppExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in exclude_files:
								sources.append( os.path.abspath( path ) )
								self.hasCppFiles = True
					for extension in self.cExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in exclude_files:
								sources.append( os.path.abspath( path ) )

					sources.sort( key = str.lower )

				if headers is not None:
					for extension in self.cppHeaderExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in exclude_files:
								headers.append( os.path.abspath( path ) )
								self.hasCppFiles = True
				if cheaders is not None:
					for extension in self.cHeaderExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in exclude_files:
								cheaders.append( os.path.abspath( path ) )

				if headers is not None or cheaders is not None:
					for extension in self.ambiguousHeaderExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in exclude_files:
								ambiguousHeaders.add( os.path.abspath( path ) )

		if self.hasCppFiles:
			headers += list(ambiguousHeaders)
		else:
			cheaders += list(ambiguousHeaders)

		headers.sort( key = str.lower )


	def get_full_path( self, headerFile, relativeDir ):
		if relativeDir in _shared_globals.headerPaths:
			if headerFile in _shared_globals.headerPaths[relativeDir]:
				return _shared_globals.headerPaths[relativeDir][headerFile]
		else:
			_shared_globals.headerPaths[relativeDir] = {}

		if os.access(headerFile, os.F_OK):
			_shared_globals.headerPaths[relativeDir][headerFile] = headerFile
			path = os.path.join(os.getcwd(), headerFile)
			_shared_globals.headerPaths[relativeDir][headerFile] = path
			return path
		else:
			if relativeDir is not None:
				path = os.path.join( relativeDir, headerFile )
				if os.access(path, os.F_OK):
					return path

			for incDir in self.include_dirs:
				path = os.path.join( incDir, headerFile )
				if os.access(path, os.F_OK):
					_shared_globals.headerPaths[relativeDir][headerFile] = path
					return path

			_shared_globals.headerPaths[relativeDir][headerFile] = ""
			return ""


	def get_included_files( self, headerFile ):
		headers = []
		if sys.version_info >= (3, 0):
			f = open( headerFile, encoding = "latin-1" )
		else:
			f = open( headerFile )
		with f:
			for line in f:
				if line[0] != '#':
					continue

				RMatch = re.search( r"#\s*include\s*[<\"](.*?)[\">]", line )
				if RMatch is None:
					continue

				#Don't follow system headers, we should assume those are immutable
				if "." not in RMatch.group( 1 ):
					continue

				headers.append( RMatch.group( 1 ) )

		return headers


	def follow_headers( self, headerFile, allheaders ):
		"""Follow the headers in a file.
		First, this will check to see if the given header has been followed already.
		If it has, it pulls the list from the allheaders global dictionary and returns it.
		If not, it populates a new allheaders list with follow_headers2, and then adds
		that to the allheaders dictionary
		"""
		headers = []

		if not headerFile:
			return

		path = self.get_full_path( headerFile, self.workingDirectory )

		if not path:
			return

		if path in _shared_globals.allheaders:
			allheaders.update(_shared_globals.allheaders[path])
			return

		headers = self.get_included_files( path )

		for header in headers:

			#Find the header in the listed includes.
			subpath = self.get_full_path( header, os.path.dirname( headerFile ) )

			if self.ignore_external_headers and not subpath.startswith( self.workingDirectory ):
				continue

			#If we've already looked at this header (i.e., it was included twice) just ignore it
			if subpath in allheaders:
				continue

			if subpath in _shared_globals.allheaders:
				allheaders.update(_shared_globals.allheaders[subpath])
				continue

			allheaders.add( subpath )

			theseheaders = set( )

			if self.header_recursion != 1:
				self.follow_headers2( subpath, theseheaders, 1, headerFile )

			_shared_globals.allheaders.update( { subpath: theseheaders } )
			allheaders.update(theseheaders)

		_shared_globals.allheaders.update( { path: set( allheaders ) } )


	def follow_headers2( self, headerFile, allheaders, n, parent ):
		"""More intensive, recursive, and cpu-hogging function to follow a header.
		Only executed the first time we see a given header; after that the information is cached."""
		headers = []

		if not headerFile:
			return

		path = self.get_full_path( headerFile, os.path.dirname( parent ) )

		if not path:
			return

		if path in _shared_globals.allheaders:
			allheaders.update(_shared_globals.allheaders[path])
			return

		headers = self.get_included_files( path )

		for header in headers:
			subpath = self.get_full_path( header, os.path.dirname( headerFile ) )

			if self.ignore_external_headers and not subpath.startswith( self.workingDirectory ):
				continue

				#Check to see if we've already followed this header.
			#If we have, the list we created from it is already stored in _allheaders under this header's key.
			if subpath in allheaders:
				continue

			if subpath in _shared_globals.allheaders:
				allheaders.update(_shared_globals.allheaders[subpath])
				continue

			allheaders.add( subpath )

			theseheaders = set( allheaders )

			if self.header_recursion == 0 or n < self.header_recursion:
				self.follow_headers2( subpath, theseheaders, n + 1, headerFile )

			_shared_globals.allheaders.update( { subpath: theseheaders } )
			allheaders.update(theseheaders)


	def should_recompile( self, srcFile, ofile = None, for_precompiled_header = False ):
		"""Checks various properties of a file to determine whether or not it needs to be recompiled."""

		log.LOG_INFO( "Checking whether to recompile {0}...".format( srcFile ) )

		if self.recompile_all:
			log.LOG_INFO(
				"Going to recompile {0} because settings have changed in the makefile that will impact output.".format(
					srcFile ) )
			return True

		basename = os.path.basename( srcFile ).split( '.' )[0]
		if not ofile:
			ofile = os.path.join( self.obj_dir, "{}_{}{}".format( basename,
				self.targetName, self.activeToolchain.Compiler().get_obj_ext() ))

		if self.use_chunks and not _shared_globals.disable_chunks:
			chunk = self.get_chunk( srcFile )
			chunkfile = os.path.join( self.obj_dir, "{}_{}{}".format( chunk,
				self.targetName, self.activeToolchain.Compiler().get_obj_ext() ) )

			#First check: If the object file doesn't exist, we obviously have to create it.
			if not os.access(ofile , os.F_OK):
				ofile = chunkfile

		if not os.access(ofile , os.F_OK):
			log.LOG_INFO(
				"Going to recompile {0} because the associated object file does not exist.".format( srcFile ) )
			return True

		#Third check: modified time.
		#If the source file is newer than the object file, we assume it's been changed and needs to recompile.
		mtime = os.path.getmtime( srcFile )
		omtime = os.path.getmtime( ofile )

		if mtime > omtime:
			if for_precompiled_header:
				log.LOG_INFO(
					"Going to recompile {0} because it has been modified since the last successful build.".format(
						srcFile ) )
				return True

			oldmd5 = 1
			newmd5 = 9

			try:
				newmd5 = _shared_globals.newmd5s[srcFile]
			except KeyError:
				with open( srcFile, "r" ) as f:
					newmd5 = _utils.get_md5( f )
				_shared_globals.newmd5s.update( { srcFile: newmd5 } )

			if platform.system( ) == "Windows":
				src = srcFile[2:]
			else:
				src = srcFile

			if sys.version_info >= (3,0):
				src = src.encode("utf-8")
				baseName = os.path.basename( src ).decode("utf-8")
			else:
				baseName = os.path.basename( src )

			md5file = "{}.md5".format( os.path.join( self.csbuild_dir, "md5s", hashlib.md5( src ).hexdigest(), baseName ) )

			if os.access(md5file , os.F_OK):
				try:
					oldmd5 = _shared_globals.oldmd5s[md5file]
				except KeyError:
					with open( md5file, "rb" ) as f:
						oldmd5 = f.read( )
					_shared_globals.oldmd5s.update( { md5file: oldmd5 } )

			if oldmd5 != newmd5:
				log.LOG_INFO(
					"Going to recompile {0} because it has been modified since the last successful build.".format(srcFile ) )
				return True

		#Fourth check: Header files
		#If any included header file (recursive, to include headers included by headers) has been changed,
		#then we need to recompile every source that includes that header.
		#Follow the headers for this source file and find out if any have been changed o necessitate a recompile.
		headers = set()

		self.follow_headers( srcFile, headers )

		updatedheaders = []

		for header in headers:
			if not header:
				continue

			path = header

			if header in _shared_globals.headerCheck:
				b = _shared_globals.headerCheck[header]
				if b:
					updatedheaders.append( [header, path] )
				else:
					continue


			header_mtime = os.path.getmtime( path )

			if header_mtime > omtime:
				if for_precompiled_header:
					updatedheaders.append( [header, path] )
					_shared_globals.headerCheck[header] = True
					continue

				#newmd5 is 0, oldmd5 is 1, so that they won't report equal if we ignore them.
				newmd5 = 0
				oldmd5 = 1

				if platform.system( ) == "Windows":
					header = header[2:]

				if sys.version_info >= (3,0):
					header = header.encode("utf-8")
					baseName = os.path.basename( header ).decode("utf-8")
				else:
					baseName = os.path.basename( header )

				md5file = "{}.md5".format( os.path.join( self.csbuild_dir, "md5s", hashlib.md5( header ).hexdigest(), baseName ) )

				if os.access(md5file , os.F_OK):
					try:
						newmd5 = _shared_globals.newmd5s[path]
					except KeyError:
						if sys.version_info >= (3, 0):
							f = open( path, encoding = "latin-1" )
						else:
							f = open( path )
						with f:
							newmd5 = _utils.get_md5( f )
						_shared_globals.newmd5s.update( { path: newmd5 } )
					if os.access(md5file , os.F_OK):
						try:
							oldmd5 = _shared_globals.oldmd5s[md5file]
						except KeyError:
							with open( md5file, "rb" ) as f:
								oldmd5 = f.read( )
							_shared_globals.oldmd5s.update( { md5file: oldmd5 } )

				if oldmd5 != newmd5:
					updatedheaders.append( [header, path] )
					_shared_globals.headerCheck[header] = True
					continue

			_shared_globals.headerCheck[header] = False

		if updatedheaders:
			files = []
			for pair in updatedheaders:
				files.append( pair[0] )
				path = pair[1]
				if path not in self.allpaths:
					self.allpaths.append( os.path.abspath( path ) )
			log.LOG_INFO(
				"Going to recompile {0} because included headers {1} have been modified since the last successful build."
				.format(
					srcFile, files ) )
			return True

		#If we got here, we assume the object file's already up to date.
		log.LOG_INFO( "Skipping {0}: Already up to date".format( srcFile ) )
		return False


	def check_libraries( self ):
		"""Checks the libraries designated by the make script.
		Invokes ld to determine whether or not the library exists.1
		Uses the -t flag to get its location.
		And then stores the library's last modified time to a global list to be used by the linker later, to determine
		whether or not a project with up-to-date objects still needs to link against new libraries.
		"""
		log.LOG_INFO( "Checking required libraries..." )

		def check_libraries( libraries, force_static, force_shared ):
			libraries_ok = True
			for library in libraries:
				bFound = False
				for depend in self.reconciledLinkDepends:
					if _shared_globals.projects[depend].output_name.startswith(library) or \
							_shared_globals.projects[depend].output_name.startswith(
									"lib{}.".format( library ) ):
						bFound = True
						break
				if bFound:
					continue

				log.LOG_INFO( "Looking for lib{0}...".format( library ) )
				lib = self.activeToolchain.Linker().find_library( self, library, self.library_dirs,
					force_static, force_shared )
				if lib:
					log.LOG_INFO( "Found library lib{0} at {1}".format( library, lib ) )
					self.library_locs.append( lib )
				else:
					log.LOG_ERROR( "Could not locate library: {0}".format( library ) )
					libraries_ok = False
			return libraries_ok


		libraries_ok = check_libraries( self.libraries, False, False )
		libraries_ok = check_libraries( self.static_libraries, True, False ) and libraries_ok
		libraries_ok = check_libraries( self.shared_libraries, False, True ) and libraries_ok
		if not libraries_ok:
			log.LOG_ERROR( "Some dependencies are not met on your system." )
			log.LOG_ERROR( "Check that all required libraries are installed." )
			log.LOG_ERROR(
				"If they are installed, ensure that the path is included in the makefile (use csbuild.LibDirs() to set "
				"them)" )
			return False
		log.LOG_INFO( "Libraries OK!" )
		return True

	def CanJoinChunk(self, chunk, newFile):
		if not chunk:
			return True

		extension = "." + chunk[0].rsplit(".", 1)[1]
		newFileExtension = "." + newFile.rsplit(".", 1)[1]
		if(
			(extension in self.cExtensions and newFileExtension in self.cppExtensions) or
			(extension in self.cppExtensions and newFileExtension in self.cExtensions)
		):
			return False

		if newFile in self.chunkExcludes:
			return False #NEVER ok to join chunk with this file!

		for sourceFile in chunk:
			if newFile in self.chunkMutexes and sourceFile in self.chunkMutexes[newFile]:
				log.LOG_INFO("Rejecting {} for this chunk because it is labeled as mutually exclusive with {} for chunking".format(newFile, sourceFile))
				return False
			if sourceFile in self.chunkMutexes and newFile in self.chunkMutexes[sourceFile]:
				log.LOG_INFO("Rejecting {} for this chunk because it is labeled as mutually exclusive with {} for chunking".format(newFile, sourceFile))
				return False

		return True

	def make_chunks( self, l ):
		""" Converts the list into a list of lists - i.e., "chunks"
		Each chunk represents one compilation unit in the chunked build system.
		"""
		if _shared_globals.disable_chunks or not self.use_chunks:
			return [l]

		if self.unity:
			return [l]
		chunks = []
		if self.chunk_filesize > 0:
			sorted_list = sorted( l, key = os.path.getsize, reverse=True )
			while sorted_list:
				remaining = []
				chunksize = 0
				chunk = [sorted_list[0]]
				chunksize += os.path.getsize( sorted_list[0] )
				sorted_list.pop( 0 )
				for i in reversed(range(len(sorted_list))):
					srcFile = sorted_list[i]
					if not self.CanJoinChunk(chunk, srcFile):
						remaining.append(srcFile)
						continue
					filesize = os.path.getsize( srcFile )
					if chunksize + filesize > self.chunk_filesize:
						chunks.append( chunk )
						remaining += sorted_list[i::-1]
						log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
						log.LOG_INFO( "Chunk size: {0}".format( chunksize ) )
						chunk = []
						break
					else:
						chunk.append( srcFile )
						chunksize += filesize
				if remaining:
					sorted_list = sorted( remaining, key = os.path.getsize, reverse=True )
				else:
					sorted_list = None

				if chunk:
					chunks.append( chunk )
					log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
					log.LOG_INFO( "Chunk size: {0}".format( chunksize ) )
		elif self.chunk_size > 0:
			tempList = l
			while tempList:
				chunk = []
				remaining = []
				for i in range(len(tempList)):
					srcFile = tempList[i]
					if not self.CanJoinChunk(chunk, srcFile):
						remaining.append(srcFile)
						continue

					chunk.append(srcFile)

					if len(chunk) == self.chunk_size:
						remaining += tempList[i+1:]
						chunks.append( chunk )
						log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
						chunk = []
						break
				tempList = remaining
				if chunk:
					chunks.append( chunk )
					log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
		else:
			return [l]
		return chunks


	def get_chunk( self, srcFile ):
		"""Retrieves the chunk that a given file belongs to."""
		for chunk in self.chunks:
			if srcFile in chunk:
				return _utils.get_chunk_name( self.output_name, chunk )
		return None


	def save_md5( self, inFile ):
		# If we're running on Windows, we need to remove the drive letter from the input file path.
		#if platform.system( ) == "Windows":
		#	inFile = inFile[2:]

		if sys.version_info >= (3,0):
			inFile = inFile.encode("utf-8")
			baseName = os.path.basename( inFile ).decode("utf-8")
		else:
			baseName = os.path.basename( inFile )

		md5file = "{}.md5".format( os.path.join( self.csbuild_dir, "md5s", hashlib.md5( inFile ).hexdigest(), baseName ) )

		md5dir = os.path.dirname( md5file )
		if not os.access(md5dir , os.F_OK):
			os.makedirs( md5dir )
		newmd5 = ""
		try:
			newmd5 = _shared_globals.newmd5s[inFile]
		except KeyError:
			if sys.version_info >= (3, 0):
				f = open( inFile, encoding = "latin-1" )
			else:
				f = open( inFile )
			with f:
				newmd5 = _utils.get_md5( f )
		finally:
			with open( md5file, "wb" ) as f:
				f.write( newmd5 )


	def save_md5s( self, sources, headers ):
		for source in sources:
			self.save_md5( source )

		for header in headers:
			self.save_md5( header )

		for path in self.allpaths:
			self.save_md5( path )


	def precompile_headers( self ):
		if not self.needs_c_precompile and not self.needs_cpp_precompile:
			return True

		starttime = time.time( )
		log.LOG_BUILD( "Precompiling headers..." )

		self.built_something = True

		if not os.access(self.obj_dir , os.F_OK):
			os.makedirs( self.obj_dir )

		thread = None
		cthread = None
		cppobj = ""
		cobj = ""
		if self.needs_cpp_precompile:
			if not _shared_globals.semaphore.acquire( False ):
				if _shared_globals.max_threads != 1:
					log.LOG_INFO( "Waiting for a build thread to become available..." )
				_shared_globals.semaphore.acquire( True )
			if _shared_globals.interrupted:
				csbuild.Exit( 2 )

			log.LOG_BUILD(
				"Precompiling {0} ({1}/{2})...".format(
					self.cppheaderfile,
					_shared_globals.current_compile,
					_shared_globals.total_compiles ) )

			_shared_globals.current_compile += 1

			cppobj = self.activeToolchain.Compiler().get_pch_file( self.cppheaderfile )

			#precompiled headers block on current thread - run runs on current thread rather than starting a new one
			thread = _utils.threaded_build( self.cppheaderfile, cppobj, self, True )
			thread.start( )

		if self.needs_c_precompile:
			if not _shared_globals.semaphore.acquire( False ):
				if _shared_globals.max_threads != 1:
					log.LOG_INFO( "Waiting for a build thread to become available..." )
				_shared_globals.semaphore.acquire( True )
			if _shared_globals.interrupted:
				csbuild.Exit( 2 )

			log.LOG_BUILD(
				"Precompiling {0} ({1}/{2})...".format(
					self.cheaderfile,
					_shared_globals.current_compile,
					_shared_globals.total_compiles ) )

			_shared_globals.current_compile += 1

			cobj = self.activeToolchain.Compiler().get_pch_file( self.cheaderfile )

			#precompiled headers block on current thread - run runs on current thread rather than starting a new one
			cthread = _utils.threaded_build( self.cheaderfile, cobj, self, True )
			cthread.start( )

		if thread:
			thread.join( )
			_shared_globals.precompiles_done += 1
		if cthread:
			cthread.join( )
			_shared_globals.precompiles_done += 1

		totaltime = time.time( ) - starttime
		totalmin = math.floor( totaltime / 60 )
		totalsec = math.floor( totaltime % 60 )
		log.LOG_BUILD( "Precompile took {0}:{1:02}".format( int( totalmin ), int( totalsec ) ) )

		self.precompile_done = True
		self.precompileFailed = self.compile_failed

		return not self.compile_failed



class ProjectGroup( object ):
	"""
	Defines a group of projects, and also may contain subgroups.

	@ivar tempprojects: Temporary list of projects directly under this group
	@type tempprojects: dict[str, projectSettings]

	@ivar projects: Fully fleshed-out list of projects under this group
	Dict is { name : { target : project } }
	@type projects: dict[str, dict[str, projectSettings]]

	@ivar subgroups: List of child groups
	@type subgroups: dict[str, ProjectGroup]

	@ivar name: Group name
	@type name: str

	@ivar parentGroup: The group's parent group
	@type parentGroup: ProjectGroup
	"""
	def __init__( self, name, parentGroup ):
		"""
		Create a new ProjectGroup

		@param name: Group name
		@type name: str

		@param parentGroup: parent group
		@type parentGroup: ProjectGroup
		"""
		self.tempprojects = {}
		self.projects = {}
		self.subgroups = {}
		self.name = name
		self.parentGroup = parentGroup


rootGroup = ProjectGroup( "", None )
currentGroup = rootGroup
currentProject = projectSettings( )
