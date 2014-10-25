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

import os
import re
import hashlib
import shlex
import subprocess
import threading
import time
import sys
import datetime
import glob
import traceback
import platform
if sys.version_info >= (3,0):
	import io
	StringIO = io.StringIO
else:
	import cStringIO
	StringIO = cStringIO.StringIO

import csbuild
from . import log
from . import _shared_globals


def remove_comments( text ):
	def replacer( match ):
		s = match.group( 0 )
		if s.startswith( '/' ):
			return ""
		else:
			return s


	pattern = re.compile(
		r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
		re.DOTALL | re.MULTILINE
	)
	return re.sub( pattern, replacer, text )


def RemoveWhitespace( text ):
	#This isn't working correctly, turning it off.
	return text
	#shlexer = shlex.shlex(text)
	#out = []
	#token = ""
	#while True:
	#    token = shlexer.get_token()
	#    if token == "":
	#        break
	#    out.append(token)
	#return "".join(out)


def GetMd5( inFile ):
	if sys.version_info >= (3, 0):
		return hashlib.md5( RemoveWhitespace( remove_comments( inFile.read( ) ) ).encode( 'utf-8' ) ).digest( )
	else:
		return hashlib.md5( RemoveWhitespace( remove_comments( inFile.read( ) ) ) ).digest( )


def GetSize( chunk ):
	size = 0
	if type( chunk ) == list:
		for source in chunk:
			size += os.path.getsize( source )
		return size
	else:
		return os.path.getsize( chunk )


class ThreadedBuild( threading.Thread ):
	"""Multithreaded build system, launches a new thread to run the compiler in.
	Uses a threading.BoundedSemaphore object to keep the number of threads equal to the number of processors on the
	machine.
	"""


	def __init__( self, infile, inobj, proj, forPrecompiledHeader = False ):
		"""Initialize the object. Also handles above-mentioned bug with dummy threads."""
		threading.Thread.__init__( self )
		self.file = os.path.normcase(infile)

		self.originalIn = self.file
		self.obj = os.path.abspath( inobj )
		self.project = proj
		self.forPrecompiledHeader = forPrecompiledHeader
		#Prevent certain versions of python from choking on dummy threads.
		if not hasattr( threading.Thread, "_Thread__block" ):
			threading.Thread._Thread__block = _shared_globals.dummy_block( )


	def run( self ):
		"""Actually run the build process."""
		starttime = time.time( )
		try:
			with self.project.mutex:
				self.project.fileStatus[self.file] = _shared_globals.ProjectState.BUILDING
				self.project.fileStart[self.file] = time.time()
				self.project.updated = True

			inc = ""
			headerfile = ""
			extension = "." + self.file.rsplit(".", 1)[1]
			if extension in self.project.cExtensions or self.file == self.project.cHeaderFile:
				if( (self.project.chunkedPrecompile and self.project.cHeaders) or self.project.precompileAsC )\
					and not self.forPrecompiledHeader:
					headerfile = self.project.cHeaderFile

				if self.forPrecompiledHeader:
					if self.originalIn in self.project.ccpcOverrideCmds:
						baseCommand = self.project.ccpcOverrideCmds[self.originalIn]
					else:
						baseCommand = self.project.ccpccmd
				else:
					if self.originalIn in self.project.ccOverrideCmds:
						baseCommand = self.project.ccOverrideCmds[self.originalIn]
					else:
						baseCommand = self.project.ccCmd
			else:
				if (self.project.precompile or self.project.chunkedPrecompile) \
					and not self.forPrecompiledHeader:
					headerfile = self.project.cppHeaderFile

				if self.forPrecompiledHeader:
					if self.originalIn in self.project.cxxpcOverrideCmds:
						baseCommand = self.project.cxxpcOverrideCmds[self.originalIn]
					else:
						baseCommand = self.project.cxxpccmd
				else:
					if self.originalIn in self.project.cxxOverrideCmds:
						baseCommand = self.project.cxxOverrideCmds[self.originalIn]
					else:
						baseCommand = self.project.cxxCmd

			indexes = {}
			reverseIndexes = {}

			if self.originalIn in self.project.fileOverrideSettings:
				project = self.project.fileOverrideSettings[self.originalIn]
			else:
				project = self.project

			if _shared_globals.profile:
				profileIn = os.path.join( self.project.csbuildDir, "profileIn")
				if not os.access(profileIn, os.F_OK):
					os.makedirs(profileIn)
				self.file = os.path.join( profileIn, "{}.{}".format(hashlib.md5(self.file).hexdigest(), self.file.rsplit(".", 1)[1]) )

				preprocessCmd = self.project.activeToolchain.Compiler().GetPreprocessCommand( baseCommand, project, os.path.abspath( self.originalIn ))
				if _shared_globals.show_commands:
					print(preprocessCmd)

				if platform.system() != "Windows":
					preprocessCmd = shlex.split(preprocessCmd)
				fd = subprocess.Popen(preprocessCmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

				data = StringIO()
				lastLine = 0
				lastFile = 0

				highIndex = 0

				op, er = fd.communicate()
				if sys.version_info >= (3, 0):
					op = op.decode("utf-8")
					er = er.decode("utf-8")

				if fd.returncode == 0:
					text = op.split("\n")

					for line in text:
						stripped = line.rstrip()

						data.write(stripped)
						data.write("\n")

						if not stripped:
							lastLine += 1
							continue

						if stripped.startswith("#line") or stripped.startswith("# "):
							split = stripped.split(" ",2)
							filename = split[2].split('"')[1]
							lastLine = int(split[1])
							if filename in indexes:
								lastFile = indexes[filename]
							else:
								highIndex += 1
								indexes[filename] = highIndex
								lastFile = highIndex
								filename = os.path.normcase(os.path.abspath(filename))
								filename = filename.replace("\\\\", "\\")
								reverseIndexes[highIndex] = filename

							data.write(self.project.activeToolchain.Compiler().PragmaMessage("CSBPF[{}][{}]".format(lastFile, lastLine)))
							data.write("\n")
						else:
							data.write(self.project.activeToolchain.Compiler().PragmaMessage("CSBPL[{}][{}]".format(lastFile, lastLine)))
							data.write("\n")
							lastLine += 1
					if platform.system() == "Windows":
						file_mode = 438 # Octal 0666
						fd = os.open(self.file, os.O_WRONLY | os.O_CREAT | os.O_NOINHERIT | os.O_TRUNC, file_mode)
						os.write(fd, data.getvalue())
						os.fsync(fd)
						os.close(fd)
					else:
						with open(self.file, "w") as f:
							f.write(data.getvalue())
				else:
					print(er)

			if headerfile:
				inc += headerfile
			if self.forPrecompiledHeader:
				cmd = self.project.activeToolchain.Compiler().GetExtendedPrecompileCommand( baseCommand,
					project, inc, self.obj, os.path.abspath( self.file ) )
			else:
				cmd = self.project.activeToolchain.Compiler().GetExtendedCommand( baseCommand,
					project, inc, self.obj, os.path.abspath( self.file ) )

			if _shared_globals.profile:
				cmd += self.project.activeToolchain.Compiler().GetExtraPostPreprocessorFlags()

			self.project.compileCommands[self.originalIn] = cmd
			if _shared_globals.show_commands:
				print(cmd)
			if os.access(self.obj , os.F_OK):
				os.remove( self.obj )

			class StringRef(object):
				def __init__(self):
					self.str = ""

			errors = StringRef()
			output = StringRef()
			if platform.system() != "Windows":
				cmd = shlex.split(cmd)

			fd = subprocess.Popen( cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE, cwd = self.project.workingDirectory )
			running = True

			times = {}
			lastTimes = {}

			if platform.system() == "Windows":
				timeFunc = time.clock
			else:
				timeFunc = time.time

			sanitation_lines = self.project.activeToolchain.Compiler().GetPostPreprocessorSanitationLines()
			ansi_escape = re.compile(r'\x1b[^m]*m')

			summedTimes = {}

			def GatherData(pipe, buffer):
				while running:
					try:
						line = pipe.readline()
					except IOError as e:
						continue
					if not line:
						break

					if sys.version_info >= (3, 0):
						line = line.decode("utf-8");

					stripped = line.strip()
					baseFile = os.path.basename(self.file)
					if stripped == baseFile:
						continue
					if not " " in stripped:
						baseStripped = stripped.rsplit(".",1)[0]
						baseFile = baseFile.rsplit(".", 1)[0]
						if baseStripped == baseFile:
							continue

					if _shared_globals.profile:
						sanitized = False
						for sanitationLine in sanitation_lines:
							if stripped == sanitationLine:
								sanitized = True
								break
						if sanitized:
							continue

						if "CSBPF" in line:
							sub = re.sub(ansi_escape, '', line)
							split = sub.split("[")
							file = reverseIndexes[int(split[1].split("]")[0])]
							lineNo = int(split[2].split("]")[0]) - 1
							now = timeFunc()
							if file in lastTimes:
								if file not in times:
									times[file] = {}
								if lineNo not in times[file]:
									times[file][lineNo] = 0
								times[file][lineNo] += now - lastTimes[file]
							else:
								summedTimes[file] = 0
							lastTimes[file] = now
							continue

						if "CSBPL" in line:
							sub = re.sub(ansi_escape, '', line)
							split = sub.split("[")
							file = reverseIndexes[int(split[1].split("]")[0])]
							lineNo = int(split[2].split("]")[0])
							if file not in times:
								times[file] = {}
							if lineNo not in times[file]:
								times[file][lineNo] = 0
							now = timeFunc()
							times[file][lineNo] += now - lastTimes[file]
							summedTimes[file] += now - lastTimes[file]
							lastTimes[file] = now
							continue

					buffer.str += line

			outputThread = threading.Thread(target=GatherData, args=(fd.stdout, output))
			errorThread = threading.Thread(target=GatherData, args=(fd.stderr, errors))

			outputThread.start()
			errorThread.start()

			fd.wait()
			running = False

			outputThread.join()
			errorThread.join()

			with self.project.mutex:
				self.project.times[self.originalIn] = times
				for file in summedTimes:
					if file in self.project.summedTimes:
						self.project.summedTimes[file] += summedTimes[file]
					else:
						self.project.summedTimes[file] = summedTimes[file]

			ret = fd.returncode

			sys.stdout.write( output.str )
			sys.stderr.write( errors.str )

			with self.project.mutex:
				stripped_errors = re.sub(ansi_escape, '', errors.str)
				self.project.compileOutput[self.originalIn] = output.str
				self.project.compileErrors[self.originalIn] = stripped_errors
				errorlist = self.project.activeToolchain.Compiler()._parseOutput(output.str)
				errorlist2 = self.project.activeToolchain.Compiler()._parseOutput(stripped_errors)
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

					self.project.errors += errorcount
					self.project.warnings += warningcount
					self.project.errorsByFile[self.originalIn] = errorcount
					self.project.warningsByFile[self.originalIn] = warningcount
					self.project.parsedErrors[self.originalIn] = errorlist

					if errorcount > 0:
						self.project.fileStatus[self.originalIn] = _shared_globals.ProjectState.FAILED
					else:
						self.project.fileStatus[self.originalIn] = _shared_globals.ProjectState.FINISHED
				else:
					self.project.fileStatus[self.originalIn] = _shared_globals.ProjectState.FINISHED


			with _shared_globals.sgmutex:
				_shared_globals.warningcount += warningcount
				_shared_globals.errorcount += errorcount

			if ret:
				if str( ret ) == str( self.project.activeToolchain.Compiler().InterruptExitCode( ) ):
					_shared_globals.lock.acquire( )
					if not _shared_globals.interrupted:
						log.LOG_ERROR( "Keyboard interrupt received. Aborting build." )
					_shared_globals.interrupted = True
					log.LOG_BUILD( "Releasing lock..." )
					_shared_globals.lock.release( )
					log.LOG_BUILD( "Releasing semaphore..." )
					_shared_globals.semaphore.release( )
					log.LOG_BUILD( "Closing thread..." )
				if not _shared_globals.interrupted:
					log.LOG_ERROR( "Compile of {} failed!  (Return code: {})".format( self.originalIn, ret ) )
				_shared_globals.build_success = False

				self.project.mutex.acquire( )
				self.project.compilationFailed = True
				self.project.fileStatus[self.originalIn] = _shared_globals.ProjectState.FAILED
				self.project.updated = True
				self.project.mutex.release( )
		except Exception as e:
			#If we don't do this with ALL exceptions, any unhandled exception here will cause the semaphore to never
			# release...
			#Meaning the build will hang. And for whatever reason ctrl+c won't fix it.
			#ABSOLUTELY HAVE TO release the semaphore on ANY exception.
			#if os.path.dirname(self.originalIn) == _csbuildDir:
			#   os.remove(self.originalIn)
			_shared_globals.semaphore.release( )

			self.project.mutex.acquire( )
			self.project.compilationFailed = True
			self.project.compilationCompleted += 1
			self.project.fileStatus[self.originalIn] = _shared_globals.ProjectState.FAILED
			self.project.fileEnd[self.originalIn] = time.time()
			self.project.updated = True
			self.project.mutex.release( )

			traceback.print_exc()
			raise e
		else:
			#if os.path.dirname(self.originalIn) == _csbuildDir:
			#   os.remove(self.originalIn)
			#if inc or (not self.project.precompile and not self.project.chunkedPrecompile):
			#endtime = time.time( )
			#_shared_globals.sgmutex.acquire( )
			#_shared_globals.times.append( endtime - starttime )
			#_shared_globals.sgmutex.release( )

			_shared_globals.semaphore.release( )

			self.project.mutex.acquire( )
			self.project.compilationCompleted += 1
			self.project.fileEnd[self.originalIn] = time.time()
			self.project.updated = True
			self.project.mutex.release( )


def BaseNames( l ):
	ret = []
	for srcFile in l:
		ret.append( os.path.basename( srcFile ) )
	return ret


def GetBaseName( name ):
	"""This converts an output name into a directory name. It removes extensions, and also removes the prefix 'lib'"""
	ret = name.split( "." )[0]
	if ret.startswith( "lib" ):
		ret = ret[3:]
	return ret


def CheckVersion( ):
	"""Checks the currently installed version against the latest version, and logs a warning if the current version
	is out of date."""
	if "Dev-" in csbuild.__version__:
		return

	if not os.access(os.path.expanduser( "~/.csbuild/check" ) , os.F_OK):
		csbuild_date = ""
	else:
		with open( os.path.expanduser( "~/.csbuild/check" ), "r" ) as f:
			csbuild_date = f.read( )

	date = datetime.date.today( ).isoformat( )

	if date == csbuild_date:
		return

	if not os.access(os.path.expanduser( "~/.csbuild" ) , os.F_OK):
		os.makedirs( os.path.expanduser( "~/.csbuild" ) )

	with open( os.path.expanduser( "~/.csbuild/check" ), "w" ) as f:
		f.write( date )

	try:
		out = subprocess.check_output( ["pip", "search", "csbuild"] )
	except:
		return
	else:
		pattern = "LATEST:\s*(\S*)$"
		if sys.version_info >= (3, 0):
			pattern = pattern.encode("utf-8")
		RMatch = re.search( pattern, out )
		if not RMatch:
			return
		latest_version = RMatch.group( 1 )
		if latest_version != csbuild.__version__:
			log.LOG_WARN(
				"A new version of csbuild is available. Current version: {0}, latest: {1}".format( csbuild.__version__,
					latest_version ) )
			log.LOG_WARN( "Use 'sudo pip install csbuild --upgrade' to get the latest version." )


def SortProjects( projects_to_sort ):
	ret = []

	already_errored_link = { }
	already_errored_source = { }


	def insert_depends( project, already_inserted = set( ) ):
		if project.ignoreDependencyOrdering:
			return
		already_inserted.add( project.key )
		if project not in already_errored_link:
			already_errored_link[project] = set( )
			already_errored_source[project] = set( )

		for depend in project.reconciledLinkDepends:
			if depend in already_inserted:
				log.LOG_WARN(
					"Circular dependencies detected: {0} and {1} in linkDepends".format( depend.rsplit( "@", 1 )[0],
						project.name ) )
				continue
			if depend not in projects_to_sort:
				if depend not in already_errored_link[project]:
					log.LOG_ERROR( "Project {} references non-existent link dependency {}".format(
						project.name, depend.rsplit( "@", 1 )[0] ) )
					already_errored_link[project].add( depend )
					project.reconciledLinkDepends.remove(depend)
				continue
			insert_depends( projects_to_sort[depend], already_inserted )

		for index in range( len( project.srcDepends ) ):
			depend = project.srcDepends[index]
			if depend in already_inserted:
				log.LOG_WARN(
					"Circular dependencies detected: {0} and {1} in srcDepends".format( depend.rsplit( "@", 1 )[0],
						project.name ) )
				continue
			if depend not in projects_to_sort:
				if depend not in already_errored_source[project]:
					log.LOG_ERROR( "Project {} references non-existent source dependency {}".format(
						project.name, depend.rsplit( "@", 1 )[0] ) )
					already_errored_source[project].add( depend )
					del project.srcDepends[index]
				continue
			insert_depends( projects_to_sort[depend], already_inserted )
		if project not in ret:
			ret.append( project )
		already_inserted.remove( project.key )


	dependencyFreeProjects = []
	for project in sorted(projects_to_sort.values( ), key=lambda proj: proj.priority, reverse=True):
		if project.ignoreDependencyOrdering:
			dependencyFreeProjects.append(project)
		else:
			insert_depends( project )

	return sorted(dependencyFreeProjects, key=lambda proj: proj.priority, reverse=True) + ret


def PreparePrecompiles( ):
	if _shared_globals.disable_precompile:
		return

	wd = os.getcwd( )
	for project in _shared_globals.projects.values( ):
		os.chdir( project.workingDirectory )

		precompileExcludeFiles = set( )
		for exclude in project.precompileExcludeFiles:
			precompileExcludeFiles |= set( glob.glob( exclude ) )


		def handleHeaderFile( headerfile, allheaders, forCpp ):
			obj = project.activeToolchain.Compiler().GetPchFile( headerfile )

			precompile = False
			if not os.access(headerfile, os.F_OK ) or project.should_recompile( headerfile, obj, True ):
				precompile = True
			else:
				for header in allheaders:
					if project.should_recompile( header, obj, True ):
						precompile = True
						break

			if not precompile:
				return False, headerfile

			with open( headerfile, "w" ) as f:
				for header in allheaders:
					if header in precompileExcludeFiles:
						continue
					externed = False

					#TODO: This may no longer be relevant due to other changes, needs review.
					isPlainC = False
					if header in project.cHeaders:
						isPlainC = True
					else:
						extension = "." + header.rsplit(".", 1)[1]
						if extension in project.cHeaderExtensions:
							isPlainC = True
						elif extension in project.ambiguousHeaderExtensions and not project.hasCppFiles:
							isPlainC = True

					if forCpp and isPlainC:
						f.write( "extern \"C\"\n{\n\t" )
						externed = True
					f.write( '#include "{0}"\n'.format( os.path.abspath( header ) ) )
					if forCpp:
						project.cppPchContents.append( header )
					else:
						project.cPchContents.append( header )
					if externed:
						f.write( "}\n" )
			return True, headerfile


		if project.chunkedPrecompile or project.precompile or project.precompileAsC:

			if project.chunkedPrecompile:
				cppHeaders = project.cppHeaders
				cHeaders = project.cHeaders
			else:
				if not project.hasCppFiles:
					cppHeaders = []
					cHeaders = project.precompile + project.precompileAsC
				else:
					cppHeaders = project.precompile
					cHeaders = project.precompileAsC

			if cppHeaders:
				project.cppHeaderFile = os.path.join( project.csbuildDir, "{}_cpp_precompiled_headers_{}.hpp".format(
					project.outputName.split( '.' )[0],
					project.targetName ))

				project.needsPrecompileCpp, project.cppHeaderFile = handleHeaderFile( project.cppHeaderFile, cppHeaders, True )

				_shared_globals.total_precompiles += int( project.needsPrecompileCpp )
			else:
				project.needsPrecompileCpp = False

			if cHeaders:
				project.cHeaderFile = os.path.join(project.csbuildDir, "{}_c_precompiled_headers_{}.h".format(
					project.outputName.split( '.' )[0],
					project.targetName ))

				project.needsPrecompileC, project.cHeaderFile = handleHeaderFile( project.cHeaderFile, cHeaders, False )

				_shared_globals.total_precompiles += int( project.needsPrecompileC )
			else:
				project.needsPrecompileC = False



	os.chdir( wd )


def ChunkedBuild( ):
	"""Prepares the files for a chunked build.
	This function steps through all of the sources that are on the slate for compilation and determines whether each
	needs to be compiled individually or as a chunk. If it is to be compiled as a chunk, this function also creates
	the chunk file to be compiled. It then returns an updated list of files - individual files, chunk files, or both -
	that are to be compiled.
	"""

	chunks_to_build = set()
	totalBuildThreads = 0
	owningProject = None

	for project in _shared_globals.projects.values( ):
		for source in project.sources:
			chunk = (project.key, project.get_chunk( source ))
			if chunk[1]:
				if chunk not in chunks_to_build:
					chunks_to_build.add( chunk )
					totalBuildThreads += 1
					owningProject = project
			else:
				totalBuildThreads += 1

	if not chunks_to_build:
		return

	if len(chunks_to_build) == 1 and not owningProject.unity:
		chunkname = list(chunks_to_build)[0][1]

		obj = GetSourceObjPath( owningProject, chunkname, sourceIsChunkPath=owningProject.ContainsChunk( chunkname ) )
		for chunk in owningProject.chunks:
			if GetChunkName( owningProject.outputName, chunk ) == chunkname:
				if os.access(obj , os.F_OK):
					os.remove(obj)
					log.LOG_WARN_NOPUSH(
						"Breaking chunk ({0}) into individual files to improve future iteration turnaround.".format(
							chunk
						)
					)
					for filename in chunk:
						owningProject.splitChunks[filename] = chunkname
					owningProject._finalChunkSet = chunk
					return
				else:
					owningProject._finalChunkSet = owningProject.sources
					return
		return

	for project in _shared_globals.projects.values( ):
		for chunk in project.chunks:
			sources_in_this_chunk = []
			for source in project.sources:
				if source in chunk:
					sources_in_this_chunk.append( source )

			chunksize = GetSize( sources_in_this_chunk )

			extension = "." + chunk[0].rsplit(".", 1)[1]

			if extension in project.cExtensions:
				extension = ".c"
			else:
				extension = ".cpp"

			if project.unity:
				outFile = os.path.join( project.csbuildDir, "{}_unity{}".format(
					project.outputName,
					extension
				))
			else:
				outFile = os.path.join( project.csbuildDir, "{}{}".format(
					GetChunkName( project.outputName, chunk ),
					extension
				))

			# We want to try and achieve ideal parallelism.
			# ALWAYS SPLIT if we're building fewer total translation units than the number of threads available to us.
			# Otherwise, follow the rules set by the project for chunk size, chunk filesize, etc.
			if(
				project.useChunks
				and not _shared_globals.disable_chunks
				and len( chunk ) > 1
				and (
					totalBuildThreads >= _shared_globals.max_threads
					and not project.unity #Unity means never split.
				)
				and (
					(
						project.chunkSize > 0
						and len( sources_in_this_chunk ) > project.chunkTolerance
					) or (
						project.chunkFilesize > 0
						and chunksize > project.chunkSizeTolerance
					) or (
						(
							project.unity
							or os.access(outFile, os.F_OK)
						) and len(sources_in_this_chunk ) > 0
					)
				)
			):
				log.LOG_INFO( "Going to build chunk {0} as {1}".format( chunk, outFile ) )
				with open( outFile, "w" ) as f:
					f.write( "//Automatically generated file, do not edit.\n" )
					for source in chunk:
						f.write(
							'#include "{0}" // {1} bytes\n'.format( os.path.abspath( source ),
								os.path.getsize( source ) ) )
						obj = GetSourceObjPath( project, source )
						if os.access(obj , os.F_OK):
							os.remove( obj )
					f.write( "//Total size: {0} bytes".format( chunksize ) )

				project._finalChunkSet.append( outFile )
				project.chunksByFile.update( { outFile : chunk } )
			elif len( sources_in_this_chunk ) > 0:
				chunkname = GetChunkName( project.outputName, chunk )
				
				obj = GetSourceObjPath( project, chunkname, sourceIsChunkPath=project.ContainsChunk( chunkname ) )
				if os.access(obj , os.F_OK):
					#If the chunk object exists, the last build of these files was the full chunk.
					#We're now splitting the chunk to speed things up for future incremental builds,
					# which means the chunk
					#is getting deleted and *every* file in it needs to be recompiled this time only.
					#The next time any of these files changes, only that section of the chunk will get built.
					#This keeps large builds fast through the chunked build, without sacrificing the speed of smaller
					#incremental builds (except on the first build after the chunk)
					os.remove( obj )
					add_chunk = chunk
					if project.useChunks and not _shared_globals.disable_chunks:
						log.LOG_WARN_NOPUSH(
							"Breaking chunk ({0}) into individual files to improve future iteration turnaround.".format(
								chunk ) )

						for filename in chunk:
							owningProject.splitChunks[filename] = chunkname
				else:
					add_chunk = sources_in_this_chunk
					if project.useChunks and not _shared_globals.disable_chunks:
						log.LOG_INFO(
							"Keeping chunk ({0}) broken up because chunking has been disabled for this project".format(
								chunk ) )
				if len( add_chunk ) == 1:
					if len( chunk ) == 1:
						log.LOG_INFO(
							"Going to build {0} as an individual file because it's the only file in its chunk.".format(
								chunk[0] ) )
					else:
						log.LOG_INFO( "Going to build {0} as an individual file.".format( add_chunk ) )
				else:
					log.LOG_INFO( "Going to build chunk {0} as individual files.".format( add_chunk ) )
				project._finalChunkSet += add_chunk
				totalBuildThreads += len(add_chunk) - 1 #Subtract one because we're removing the chunk and adding its contents

def GetChunkName( projectName, chunk ):
	chunk_names = "__".join( BaseNames( chunk ) )
	if sys.version_info >= (3, 0):
		chunk_names = chunk_names.encode()
	return "{}_chunk_{}".format(
		projectName.split( '.' )[0],
		hashlib.md5( chunk_names ).hexdigest()
	)


def GetChunkedObjPath(project, chunk):
	if isinstance(chunk, list):
		chunk = GetChunkName(project.outputName, chunk)
	return os.path.join(project.objDir, "{}_{}{}".format(
		chunk,
		project.targetName,
		project.activeToolchain.Compiler().GetObjExt()
	))


def GetSourceObjPath(project, source, sourceIsChunkPath=False):
	if not sourceIsChunkPath:
		objSubPath = os.path.dirname(os.path.relpath(os.path.abspath(source), project.workingDirectory))
	else:
		objSubPath = ""
	return os.path.join(project.objDir, objSubPath, "{}_{}{}".format(
		os.path.basename( source ).split( '.' )[0],
		project.targetName,
		project.activeToolchain.Compiler().GetObjExt() ) )


def GetUnityChunkObjPath(project):
	return os.path.join(project.objDir, "{}_unity_{}{}".format(
		project.outputName,
		project.targetName,
		project.activeToolchain.Compiler().GetObjExt()
	))
