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
from csbuild import _shared_globals
from csbuild import toolchain
import csbuild
import platform

class gccBase( object ):
	def __init__( self ):
		self.isClang = False

	def copyTo(self, other):
		other.isClang = self.isClang

	def parseClangOutput(self, outputStr):
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



	def parseGccOutput(self, outputStr):
		return None


	def parseOutput(self, outputStr):
		if self.isClang:
			return self.parseClangOutput(outputStr)
		else:
			return self.parseGccOutput(outputStr)


class compiler_gcc( gccBase, toolchain.compilerBase ):
	def __init__( self ):
		gccBase.__init__(self)
		toolchain.compilerBase.__init__( self )

		self.warnFlags = []
		self.cppStandard = ""
		self.cStandard = ""


	def copy(self):
		ret = toolchain.compilerBase.copy(self)
		gccBase.copyTo(self, ret)
		ret.warnFlags = list(self.warnFlags)
		ret.cppStandard = self.cppStandard
		ret.cStandard = self.cStandard
		return ret


	def get_warnings( self, warnFlags, noWarnings ):
		"""Returns a string containing all of the passed warning flags, formatted to be passed to gcc/g++."""
		if noWarnings:
			return "-w "
		ret = ""
		for flag in warnFlags:
			ret += "-W{} ".format( flag )
		return ret


	def get_defines( self, defines, undefines ):
		"""Returns a string containing all of the passed defines and undefines, formatted to be passed to gcc/g++."""
		ret = ""
		for define in defines:
			ret += "-D{} ".format( define )
		for undefine in undefines:
			ret += "-U{} ".format( undefine )
		return ret


	def get_include_dirs( self, includeDirs ):
		"""Returns a string containing all of the passed include directories, formatted to be passed to gcc/g++."""
		ret = ""
		for inc in includeDirs:
			ret += "-I{} ".format( os.path.abspath( inc ) )
		ret += "-I/usr/include -I/usr/local/include "
		return ret

	def _get_cross_compile_flag( self, compiler, project ):
		if not project.outputArchitecture:
			return ""
		if "clang" in compiler.lower( ):
			return "-target {}".format( project.outputArchitecture.clangTriple )
		else:
			return "-b {}".format( project.outputArchitecture.archString )


	def get_base_command( self, compiler, project, isCpp ):
		exitcodes = ""
		if "clang" not in compiler:
			exitcodes = "-pass-exit-codes"
		else:
			self.isClang = True

		if isCpp:
			standard = self.cppStandard
		else:
			standard = self.cStandard

		return "{} {}{} -Winvalid-pch -c {}-g{} -O{} {}{}{} {} {}".format(
			compiler,
			"-m32 " if project.force_32_bit else "-m64 " if project.force_64_bit else "",
			exitcodes,
			self.get_defines( project.defines, project.undefines ),
			project.debug_level,
			project.opt_level,
			"-fPIC " if project.type == csbuild.ProjectType.SharedLibrary else "",
			"-pg " if project.profile else "",
			"--std={0}".format( standard ) if standard != "" else "",
			" ".join( project.cpp_compiler_flags ) if isCpp else " ".join( project.c_compiler_flags ),
			self._get_cross_compile_flag( compiler, project )
		)


	def get_base_cxx_command( self, project ):
		return self.get_base_command( project.cxx, project, True )


	def get_base_cc_command( self, project ):
		return self.get_base_command( project.cc, project, False )


	def get_extended_command( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		inc = ""
		if forceIncludeFile:
			inc = "-include {0}".format( forceIncludeFile )
		return "{} {}{}{} -o\"{}\" \"{}\"".format( baseCmd,
			self.get_warnings( self.warnFlags, project.no_warnings ),
			self.get_include_dirs( project.include_dirs ), inc, outObj,
			inFile )


	def get_base_cxx_precompile_command( self, project ):
		return self.get_base_cxx_command( project )


	def get_base_cc_precompile_command( self, project ):
		return self.get_base_cc_command( project )


	def get_extended_precompile_command( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		return self.get_extended_command( baseCmd, project, forceIncludeFile, outObj, inFile )


	def interrupt_exit_code( self ):
		return 2


	def get_preprocess_command(self, baseCmd, project, inFile ):
		return "{} -E {} \"{}\"".format(baseCmd, self.get_include_dirs( project.include_dirs ), inFile)


	def pragma_message(self, message):
		return "#pragma message \"{}\"".format(message)


	def get_extra_post_preprocess_flags(self):
		return " -ftemplate-backtrace-limit=0 -fno-show-source-location -fno-caret-diagnostics -fno-diagnostics-fixit-info"

	def get_post_preprocess_sanitation_lines(self):
		return ["In included file:"]


	def get_obj_ext(self):
		return ".o"


	def get_pch_file( self, fileName ):
		return fileName + ".gch"

	def WarnFlags( self, *args ):
		"""
		Sets warn flags to be passed to the compiler.

		@param args: List of flags
		@type args: an arbitrary number of strings
		"""
		self.warnFlags += list( args )


	def ClearWarnFlags( self ):
		"""Clears the list of warning flags"""
		self.warnFlags = []


	def CppStandard( self, s ):
		"""
		The C/C++ standard to be used when compiling. Possible values are C++03, C++-11, etc.

		@param s: The standard to use
		@type s: str
		"""
		self.cppStandard = s


	def CStandard( self, s ):
		"""
		The C/C++ standard to be used when compiling. Possible values are C99, C11, etc.

		@param s: The standard to use
		@type s: str
		"""
		self.cStandard = s

class linker_gcc( gccBase, toolchain.linkerBase ):
	def __init__( self ):
		gccBase.__init__(self)
		toolchain.linkerBase.__init__( self )

		self.strictOrdering = False


	def copy(self):
		ret = toolchain.linkerBase.copy(self)
		gccBase.copyTo(self, ret)
		ret.strictOrdering = self.strictOrdering
		return ret


	def interrupt_exit_code( self ):
		return 2


	def SetupForProject( self, project ):
		valid_x64_archs = [
			"amd64",
			"ia64",
			"x64",
			"x86_64",
			"sparc64",
			"ppc64",
			"i686-64",
		]
		is_64bit_platform = True if platform.machine( ).lower( ) in valid_x64_archs else False

		self._include_lib64 = False

		# Only include lib64 if we're on a 64-bit platform and we haven't specified whether to build a 64bit or 32bit
		# binary or if we're explicitly told to build a 64bit binary.
		if (is_64bit_platform and not project.force_64_bit and not project.force_32_bit) or project.force_64_bit:
			self._include_lib64 = True


	def get_libraries( self, libraries ):
		"""Returns a string containing all of the passed libraries, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libraries:
			ret += "-l{} ".format( lib )
		return ret


	def get_static_libraries( self, libraries ):
		"""Returns a string containing all of the passed libraries, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libraries:
			ret += "-static -l{} ".format( lib )
		return ret


	def get_shared_libraries( self, libraries ):
		"""Returns a string containing all of the passed libraries, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libraries:
			ret += "-shared -l{} ".format( lib )
		return ret


	def get_library_dirs( self, libDirs, forLinker ):
		"""Returns a string containing all of the passed library dirs, formatted to be passed to gcc/g++."""
		ret = ""
		for lib in libDirs:
			ret += "-L{} ".format( lib )
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


	def get_link_command( self, project, outputFile, objList ):
		self.SetupForProject( project )
		if project.type == csbuild.ProjectType.StaticLibrary:
			return "ar rcs {} {}".format( outputFile, " ".join( objList ) )
		else:
			if project.hasCppFiles:
				cmd = project.cxx
			else:
				cmd = project.cc

			return "{} {}{}-o{} {} {} {} {}{}{} {} {}-g{} -O{} {} {}".format(
				cmd,
				"-m32 " if project.force_32_bit else "-m64 " if project.force_64_bit else "",
				"-pg " if project.profile else "",
				outputFile,
				" ".join( objList ),
				"-static-libgcc -static-libstdc++ " if project.static_runtime else "",
				"-Wl,--start-group" if not self.strictOrdering else "",
				self.get_libraries( project.libraries ),
				self.get_static_libraries( project.static_libraries ),
				self.get_shared_libraries( project.shared_libraries ),
				"-Wl,--end-group" if not self.strictOrdering else "",
				self.get_library_dirs( project.library_dirs, True ),
				project.debug_level,
				project.opt_level,
				"-shared" if project.type == csbuild.ProjectType.SharedLibrary else "",
				" ".join( project.linker_flags )
			)


	def find_library( self, project, library, library_dirs, force_static, force_shared ):
		success = True
		out = ""
		self.SetupForProject( project )
		try:
			if _shared_globals.show_commands:
				print("ld -o /dev/null --verbose {} {} -l{}".format(
					self.get_library_dirs( library_dirs, False ),
					"-static" if force_static else "-shared" if force_shared else "",
					library ))
			cmd = ["ld", "-o", "/dev/null", "--verbose",
				   "-static" if force_static else "-shared" if force_shared else "", "-l{}".format( library )]
			cmd += shlex.split( self.get_library_dirs( library_dirs, False ) )
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
				return lib
			elif not success:
				return None


	def get_default_extension( self, projectType ):
		if projectType == csbuild.ProjectType.Application:
			return ""
		elif projectType == csbuild.ProjectType.StaticLibrary:
			return ".a"
		elif projectType == csbuild.ProjectType.SharedLibrary:
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
