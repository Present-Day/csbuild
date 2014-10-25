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
Contains a plugin class for interfacing with GCC
"""

import os
import shlex
import subprocess
import re
import sys
import platform
from . import _shared_globals
from . import toolchain
import csbuild
from . import log

class gccBase( object ):
	def __init__( self ):
		self.isClang = False
		self._objcAbiVersion = None

		if platform.system() == "Darwin":
			#TODO: Find the best SDK available instead of hardcoding one.
			self._sysroot = "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.9.sdk"
		else:
			self._sysroot = "/"

	def _copyTo(self, other):
		other.isClang = self.isClang
		other._objcAbiVersion = self._objcAbiVersion
		other._sysroot = self._sysroot

	def GetValidArchitectures(self):
		return ['x86', 'x64']

	def SetObjcAbiVersion(self, version):
		self._objcAbiVersion = version

	def _getObjcAbiVersion(self):
		return "-fobjc-abi-version={} ".format(self._objcAbiVersion) if self._objcAbiVersion else ""

	def _getArchFlag(self, project):
		archArg = ""
		if project.outputArchitecture == 'x86':
			archArg = "-m32 "
		elif project.outputArchitecture == 'x64':
			archArg = "-m64 "
		else:
			log.LOG_ERROR("Architecture {} is not natively supported by GCC toolchain. Cross-compiling must be implemented by the makefile.")
		return archArg

	def _parseClangOutput(self, outputStr):
		command = re.compile("^clang(\\+\\+)?: +(fatal +)?(warning|error|note): (.*)$")
		inLine = re.compile("^In (.*) included from (.*):(\\d+):$")
		message = re.compile("^(<command line>|([A-Za-z]:)?[^:]+\\.[^:]+)(:(\\d+):(\\d+)|\\((\\d+)\\) *): +(fatal +)?(error|warning|note): (.*)$")

		linkError = re.compile("^(<command line>|([A-Za-z]:)?[^:]+\\.[^:]+): (.*)$")
		linkDetail = re.compile("^(<command line>|([A-Za-z]:)?[^:]+\\.[^:]+):\\([^)]*\\): (.*)$")
		summary = re.compile("^\\d+ (warnings?|errors?)( and \\d (warnings?|errors?))? generated.$")
		codesign = re.compile("^Code ?Sign error: (.*)$")

		line = None
		ret = []
		detailsToAppend = []
		lastLine = -1
		lastCol = -1
		lastFile = ""
		try:
			for text in outputStr.split('\n'):
				if not text.strip():
					continue

				if "linker command failed with exit code" in text:
					continue

				match = summary.match(text)
				if match is not None:
					return ret

				match = command.match(text)
				if match is not None:
					line = _shared_globals.OutputLine()

					str = match.group(3)
					if str == "error":
						line.level = _shared_globals.OutputLevel.ERROR
					elif str == "warning":
						line.level = _shared_globals.OutputLevel.WARNING
					else:
						line.level = _shared_globals.OutputLevel.NOTE

					lastLine = -1
					lastCol = -1
					lastFile = ""

					line.text = match.group(4)
					line.details = detailsToAppend
					detailsToAppend = []
					ret.append(line)
					continue

				match = inLine.match(text)
				if match is not None:
					subline = _shared_globals.OutputLine()
					subline.text = text
					subline.file = match.group(2)
					subline.line = int(match.group(3))
					subline.column = 0
					detailsToAppend.append(subline)

					lastLine = -1
					lastCol = -1
					lastFile = ""
					continue

				match = message.match(text)
				if match is not None:
					newLine = _shared_globals.OutputLine()
					newLine.file = match.group(1)
					try:
						newLine.line = int(match.group(4))
						newLine.column = int(match.group(5))
					except:
						newLine.line = int(match.group(5))
						newLine.column = int(match.group(6))

					lastLine = newLine.line
					lastCol = newLine.column
					lastFile = newLine.file

					str = match.group(8)
					if str == "error":
						newLine.level = _shared_globals.OutputLevel.ERROR
					elif str == "warning":
						newLine.level = _shared_globals.OutputLevel.WARNING
					else:
						newLine.level = _shared_globals.OutputLevel.NOTE

					newLine.text = match.group(9)
					newLine.details = detailsToAppend
					detailsToAppend = []
					if newLine.level == _shared_globals.OutputLevel.NOTE:
						line.details.append(newLine)
					else:
						line = newLine
						ret.append(line)
					continue

				match = linkError.match(text)
				if match is not None:
					line = _shared_globals.OutputLine()
					line.file = match.group(1)

					line.level = _shared_globals.OutputLevel.ERROR

					line.text = match.group(3)
					line.details = detailsToAppend
					detailsToAppend = []
					ret.append(line)
					continue

				match = linkDetail.match(text)
				if match is not None:
					subline = _shared_globals.OutputLine()
					subline.file = match.group(1)
					subline.text = match.group(3)
					subline.level = _shared_globals.OutputLevel.ERROR
					line.details.append(subline)
					continue

				match = codesign.match(text)
				if match is not None:
					line = _shared_globals.OutputLine()
					line.level = _shared_globals.OutputLevel.ERROR
					line.text = match.group(1)

					lastLine = -1
					lastCol = -1
					lastFile = ""
					continue

				if line:
					subline = _shared_globals.OutputLine()
					subline.text = text
					subline.line = lastLine
					subline.column = lastCol
					subline.file = lastFile
					line.details.append(subline)

			return ret
		except Exception as e:
			print(e)
			return None



	def _parseGccOutput(self, outputStr):
		return None


	def _parseOutput(self, outputStr):
		if self.isClang:
			return self._parseClangOutput(outputStr)
		else:
			return self._parseGccOutput(outputStr)


class compiler_gcc( gccBase, toolchain.compilerBase ):
	def __init__( self ):
		gccBase.__init__(self)
		toolchain.compilerBase.__init__( self )

		self.warnFlags = set()
		self.cppStandard = ""
		self.cStandard = ""

		#self._settingsOverrides["cxx"] = "g++"
		#self._settingsOverrides["cc"] = "gcc"


	def copy(self):
		ret = toolchain.compilerBase.copy(self)
		gccBase._copyTo(self, ret)
		ret.warnFlags = set(self.warnFlags)
		ret.cppStandard = self.cppStandard
		ret.cStandard = self.cStandard
		return ret


	def _getWarnings( self, warnFlags, noWarnings ):
		"""Returns a string containing all of the passed warning flags, formatted to be passed to gcc/g++."""
		if noWarnings:
			return "-w "
		ret = ""
		for flag in warnFlags:
			ret += "-W{} ".format( flag )
		return ret


	def _getDefines( self, defines, undefines ):
		"""Returns a string containing all of the passed defines and undefines, formatted to be passed to gcc/g++."""
		ret = ""
		for define in defines:
			ret += "-D{} ".format( define )
		for undefine in undefines:
			ret += "-U{} ".format( undefine )
		return ret


	def _getIncludeDirs( self, includeDirs ):
		"""Returns a string containing all of the passed include directories, formatted to be passed to gcc/g++."""
		ret = ""
		for inc in includeDirs:
			ret += "-I{} ".format( os.path.abspath( inc ) )
		ret += "-I/usr/include -I/usr/local/include "
		return ret


	def _getOptFlag(self, optLevel):
		if optLevel == csbuild.OptimizationLevel.Max:
			return "3"
		elif optLevel == csbuild.OptimizationLevel.Speed:
			return ""
		elif optLevel == csbuild.OptimizationLevel.Size:
			return "s"
		else:
			return "0"


	def _getBaseCommand( self, compiler, project, isCpp ):
		exitcodes = ""
		if "clang" not in compiler:
			exitcodes = "-pass-exit-codes"
		else:
			self.isClang = True

		if isCpp:
			standard = self.cppStandard
		else:
			standard = self.cStandard

		archArg = self._getArchFlag(project)

		return "\"{}\" {}{} -Winvalid-pch -c -isysroot \"{}\" {}{}{} -O{} {}{}{} {}".format(
			compiler,
			archArg,
			exitcodes,
			self._sysroot,
			self._getObjcAbiVersion(),
			self._getDefines( project.defines, project.undefines ),
			"-g" if project.debugLevel != csbuild.DebugLevel.Disabled else "",
			self._getOptFlag(project.optLevel),
			"-fPIC " if project.type == csbuild.ProjectType.SharedLibrary else "",
			"-pg " if project.profile else "",
			"--std={0}".format( standard ) if standard != "" else "",
			" ".join( project.cxxCompilerFlags ) if isCpp else " ".join( project.ccCompilerFlags )
		)


	def GetBaseCxxCommand( self, project ):
		return self._getBaseCommand( project.cxx, project, True )


	def GetBaseCcCommand( self, project ):
		return self._getBaseCommand( project.cc, project, False )


	def GetExtendedCommand( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		inc = ""
		if forceIncludeFile:
			inc = "-include {0}".format( forceIncludeFile )
		return "{} {}{}{} -o\"{}\" \"{}\"".format( baseCmd,
			self._getWarnings( self.warnFlags, project.noWarnings ),
			self._getIncludeDirs( project.includeDirs ), inc, outObj,
			inFile )


	def GetBaseCxxPrecompileCommand( self, project ):
		return self.GetBaseCxxCommand( project )


	def GetBaseCcPrecompileCommand( self, project ):
		return self.GetBaseCcCommand( project )


	def GetExtendedPrecompileCommand( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		return self.GetExtendedCommand( baseCmd, project, forceIncludeFile, outObj, inFile )


	def InterruptExitCode( self ):
		return 2


	def GetPreprocessCommand(self, baseCmd, project, inFile ):
		return "\"{}\" -E {} \"{}\"".format(baseCmd, self._getIncludeDirs( project.includeDirs ), inFile)


	def PragmaMessage(self, message):
		return "#pragma message \"{}\"".format(message)


	def GetExtraPostPreprocessorFlags(self):
		return " -ftemplate-backtrace-limit=0 -fno-show-source-location -fno-caret-diagnostics -fno-diagnostics-fixit-info -W#pragma-messages"

	def GetPostPreprocessorSanitationLines(self):
		return ["In included file:"]


	def GetObjExt(self):
		return ".o"


	def GetPchFile( self, fileName ):
		return fileName + ".gch"


	def AddWarnFlags( self, *args ):
		"""
		Sets warn flags to be passed to the compiler.

		:param args: List of flags
		:type args: an arbitrary number of strings
		"""
		self.warnFlags |= set( args )


	def ClearWarnFlags( self ):
		"""Clears the list of warning flags"""
		self.warnFlags = set()


	def SetCppStandard( self, s ):
		"""
		The C/C++ standard to be used when compiling. Possible values are C++03, C++-11, etc.

		:param s: The standard to use
		:type s: str
		"""
		self.cppStandard = s


	def SetCStandard( self, s ):
		"""
		The C/C++ standard to be used when compiling. Possible values are C99, C11, etc.

		:param s: The standard to use
		:type s: str
		"""
		self.cStandard = s


class linker_gcc( gccBase, toolchain.linkerBase ):
	def __init__( self ):
		gccBase.__init__(self)
		toolchain.linkerBase.__init__( self )

		self.strictOrdering = False
		self._ld = "ld"
		self._ar = "ar"

		self._actual_library_names = { }
		self._setup = False
		self._project_settings = None

		self._frameworks = set()
		self._frameworkDirs = set()

		#self._settingsOverrides["cxx"] = "g++"
		#self._settingsOverrides["cc"] = "gcc"


	def copy(self):
		ret = toolchain.linkerBase.copy(self)
		gccBase._copyTo(self, ret)
		ret.strictOrdering = self.strictOrdering
		ret._actual_library_names = dict(self._actual_library_names)
		ret._project_settings = self._project_settings
		return ret


	def _getFrameworkDirectories(self, project):
		ret = ""
		for directory in project.frameworkDirs:
			ret += "-F{} ".format(directory)
		return ret


	def _getFrameworks(self, project):
		ret = ""
		for framework in project.frameworks:
			ret += "-framework {} ".format(framework)
		return ret


	def InterruptExitCode( self ):
		return 2


	def _setupForProject( self, project ):
		self._include_lib64 = False
		self._project_settings = project

		# Only include lib64 if we're on a 64-bit platform and we haven't specified whether to build a 64bit or 32bit
		# binary or if we're explicitly told to build a 64bit binary.
		if project.outputArchitecture == "x64":
			self._include_lib64 = True

	def _getLibraryArg(self, lib):
		for depend in self._project_settings.reconciledLinkDepends:
			dependProj = _shared_globals.projects[depend]
			if dependProj.type == csbuild.ProjectType.Application:
				continue
			dependLibName = dependProj.outputName
			splitName = os.path.splitext(dependLibName)[0]
			if splitName == lib or splitName == "lib{}".format( lib ):
				if platform.system() == "Darwin":
					return "{} ".format( os.path.join( dependProj.outputDir, dependLibName ) )
				else:
					return '-l:{} '.format( dependLibName )
		if platform.system() == "Darwin":
			return "{} ".format( self._actual_library_names[lib] )
		else:
			return "-l:{} ".format( self._actual_library_names[lib] )

	def _getLibraries( self, libraries ):
		"""Returns a string containing all of the passed libraries, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libraries:
			ret += self._getLibraryArg(lib)
		return ret


	def _getStaticLibraries( self, libraries ):
		"""Returns a string containing all of the passed libraries, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libraries:
			ret += "-static {}".format( self._getLibraryArg(lib) )
		return ret


	def _getSharedLibraries( self, libraries ):
		"""Returns a string containing all of the passed libraries, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libraries:
			ret += "-shared {}".format( self._getLibraryArg(lib) )
		return ret


	def _getLibraryDirs( self, libDirs, forLinker ):
		"""Returns a string containing all of the passed library dirs, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libDirs:
			ret += "-L{} ".format( lib )
		# OSX doesn't require the /usr lib directories.
		if platform.system() != "Darwin":
			ret += "-L/usr/lib -L/usr/local/lib "
			if self._include_lib64:
				ret += "-L/usr/lib64 -L/usr/local/lib64 "
			if forLinker:
				for lib in libDirs:
					ret += "-Wl,-R{} ".format( os.path.abspath( lib ) )
				ret += "-Wl,-R/usr/lib -Wl,-R/usr/local/lib "
				if self._include_lib64:
					ret += "-Wl,-R/usr/lib64 -Wl,-R/usr/local/lib64 "
		return ret


	def _getStartGroupFlags(self):
		if platform.system() == "Darwin":
			# OSX doesn't support the start/end group flags.
			return ""
		return "-Wl,--no-as-needed -Wl,--start-group"


	def _getEndGroupFlags(self):
		if platform.system() == "Darwin":
			# OSX doesn't support he start/end group flags.
			return ""
		return "-Wl,--end-group"


	def GetLinkCommand( self, project, outputFile, objList ):
		self._setupForProject( project )
		linkFile = os.path.join(self._project_settings.csbuildDir, "{}.cmd".format(self._project_settings.name))

		data = " ".join( objList )
		if sys.version_info >= (3, 0):
			data = data.encode("utf-8")

		file_mode = 438 # Octal 0666
		flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
		if platform.system() == "Windows":
			flags |= os.O_NOINHERIT
		fd = os.open(linkFile, flags, file_mode)
		os.write(fd, data)
		os.fsync(fd)
		os.close(fd)

		if project.type == csbuild.ProjectType.StaticLibrary:
			return "\"{}\" rcs {} {}".format( self._ar, outputFile, " ".join( objList ) )
		else:
			if project.hasCppFiles:
				cmd = project.cxx
			else:
				cmd = project.cc

			archArg = self._getArchFlag(project)

			return "\"{}\" -isysroot \"{}\" {}{}{}{}{}-o{} {} {} {} {}{}{} {} {}-g{} -O{} {} {}".format(
				cmd,
				self._sysroot,
				self._getObjcAbiVersion(),
				archArg,
				self._getFrameworkDirectories(project),
				self._getFrameworks(project),
				"-pg " if project.profile else "",
				outputFile,
				"@{}".format(linkFile),
				"-static-libgcc -static-libstdc++ " if project.useStaticRuntime else "",
				"{}".format(self._getStartGroupFlags()) if not self.strictOrdering else "",
				self._getLibraries( project.libraries ),
				self._getStaticLibraries( project.staticLibraries ),
				self._getSharedLibraries( project.sharedLibraries ),
				"{}".format(self._getEndGroupFlags()) if not self.strictOrdering else "",
				self._getLibraryDirs( project.libraryDirs, True ),
				project.debugLevel,
				project.optLevel,
				"-shared" if project.type == csbuild.ProjectType.SharedLibrary else "",
				" ".join( project.linkerFlags )
			)


	def _findLibraryUnix( self, project, library, libraryDirs, force_static, force_shared ):
		success = True
		out = ""
		self._setupForProject( project )
		try:
			if _shared_globals.show_commands:
				print("{} -o /dev/null --verbose {} {} -l{}".format(
					self._ld,
					self._getLibraryDirs( libraryDirs, False ),
					"-static" if force_static else "-shared" if force_shared else "",
					library ))
			cmd = [self._ld, "-o", "/dev/null", "--verbose",
				   "-static" if force_static else "-shared" if force_shared else "", "-l{}".format( library )]
			cmd += shlex.split( self._getLibraryDirs( libraryDirs, False ), posix=(platform.system() != "Windows") )
			out = subprocess.check_output( cmd, stderr = subprocess.STDOUT )
		except subprocess.CalledProcessError as e:
			out = e.output
			success = False
		finally:
			if sys.version_info >= (3, 0):
				RMatch = re.search( "attempt to open (.*) succeeded".encode( 'utf-8' ), out, re.I )
			else:
				RMatch = re.search( "attempt to open (.*) succeeded", out, re.I )
				#Some libraries (such as -liberty) will return successful but don't have a file (internal to ld maybe?)
			#In those cases we can probably assume they haven't been modified.
			#Set the mtime to 0 and return success as long as ld didn't return an error code.
			if RMatch is not None:
				lib = RMatch.group( 1 )
				if sys.version_info >= (3, 0):
					self._actual_library_names[library] = os.path.basename(lib).decode('utf-8')
				else:
					self._actual_library_names[library] = os.path.basename(lib)
				return lib
			elif not success:
				try:
					if _shared_globals.show_commands:
						print("{} -o /dev/null --verbose {} {} -l:{}".format(
							self._ld,
							self._getLibraryDirs( libraryDirs, False ),
							"-static" if force_static else "-shared" if force_shared else "",
							library ))
					cmd = [self._ld, "-o", "/dev/null", "--verbose",
						   "-static" if force_static else "-shared" if force_shared else "", "-l{}".format( library )]
					cmd += shlex.split( self._getLibraryDirs( libraryDirs, False ), posix=(platform.system() != "Windows") )
					out = subprocess.check_output( cmd, stderr = subprocess.STDOUT )
				except subprocess.CalledProcessError as e:
					out = e.output
					success = False
				finally:
					if sys.version_info >= (3, 0):
						RMatch = re.search( "attempt to open (.*) succeeded".encode( 'utf-8' ), out, re.I )
					else:
						RMatch = re.search( "attempt to open (.*) succeeded", out, re.I )
						#Some libraries (such as -liberty) will return successful but don't have a file (internal to ld maybe?)
					#In those cases we can probably assume they haven't been modified.
					#Set the mtime to 0 and return success as long as ld didn't return an error code.
					if RMatch is not None:
						lib = RMatch.group( 1 )
						if sys.version_info >= (3, 0):
							self._actual_library_names[library] = os.path.basename(lib).decode('utf-8')
						else:
							self._actual_library_names[library] = os.path.basename(lib)
						return lib
					elif not success:
						return None

	def _findLibraryDarwin( self, project, library, libraryDirs ):
		self._setupForProject(project)

		for lib_dir in libraryDirs:
			log.LOG_INFO("Looking for library {} in directory {}...".format(library, lib_dir))
			lib_file_path = os.path.join( lib_dir, library )
			libFileStatic = "{}.a".format( lib_file_path )
			libFileDynamic = "{}.dylib".format( lib_file_path )
			# Check for a static lib.
			if os.access(libFileStatic , os.F_OK):
				self._actual_library_names.update( { library : libFileStatic } )
				return libFileStatic
			# Check for a dynamic lib.
			if os.access(libFileDynamic , os.F_OK):
				self._actual_library_names.update( { library : libFileDynamic } )
				return libFileDynamic

		for lib_dir in libraryDirs:
			# Compatibility with Linux's way of adding lib- to the front of its libraries
			libfileCompat = "lib{}".format( library )
			log.LOG_INFO("Looking for library {} in directory {}...".format(libfileCompat, lib_dir))
			lib_file_path = os.path.join( lib_dir, libfileCompat )
			libFileStatic = "{}.a".format( lib_file_path )
			libFileDynamic = "{}.dylib".format( lib_file_path )
			# Check for a static lib.
			if os.access(libFileStatic , os.F_OK):
				self._actual_library_names.update( { library : libFileStatic } )
				return libFileStatic
			# Check for a dynamic lib.
			if os.access(libFileDynamic , os.F_OK):
				self._actual_library_names.update( { library : libFileDynamic } )
				return libFileDynamic

		# The library wasn't found.
		return None


	def FindLibrary( self, project, library, libraryDirs, force_static, force_shared ):
		if platform.system() == "Darwin":
			return self._findLibraryDarwin( project, library, libraryDirs )
		else:
			return self._findLibraryUnix( project, library, libraryDirs, force_static, force_shared )


	def GetDefaultOutputExtension( self, projectType ):
		if projectType == csbuild.ProjectType.Application:
			if platform.system() == "Windows":
				return ".exe"
			else:
				return ""
		elif projectType == csbuild.ProjectType.StaticLibrary:
			if platform.system() == "Windows":
				return ".lib"
			else:
				return ".a"
		elif projectType == csbuild.ProjectType.SharedLibrary:
			if platform.system() == "Darwin":
				return ".dylib"
			elif platform.system() == "Windows":
				return ".dll"
			else:
				return ".so"


	def EnableStrictOrdering( self ):
		"""
		By default, csbuild uses --start-group and --end-group to eliminate GCC's requirements of
		strictly managed link order. This comes with a performance cost when linking, however, so
		if you would prefer to manage your link order manually, this function will disable csbuild's
		default --start-group/--end-group behavior.
		"""
		self.strictOrdering = True


	def DisableStrictOrdering( self ):
		"""
		Use --start-group/--end-group to eliminate the need to strictly order libraries when linking.
		This is the default behavior.
		"""
		self.strictOrdering = False
