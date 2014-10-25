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
Defines shared globals used by the application. Some of these are useful to plugins, and those
are documented here. Others are left undocumented.

:var color_supported: Whether or not colored output is supported
:type color_supported: bool

:var columns: The number of columns the output window has available to it
:type columns: int

:var max_threads: Number of threads available for compilation
:type max_threads: int

:var build_success: Whether or not the build succeeded
:type build_success: bool

:var show_commands: Whether or not to print commands sent to the OS
:type show_commands: bool

:var projects: Full list of all projects
:type projects: dict[str, csbuild.projectSettings.projectSettings]

:var install_prefix: The base location that files will be installed to (defaults to /usr/local)
:type install_prefix: str

:var project_build_list: Projects the user has requested to build
:type project_build_list: set[str]

:var sortedProjects: Projects being built in build order, sorted according to dependencies
:type sortedProjects: list[csbuild.projectSettings.projectSettings]

:var project_generators: All project generators currently available
:type project_generators: dict[str, csbuild.project_generator.project_generator]

:var alltargets: All targets in the makefile, collected from all projects
:type alltargets: set[str]

:var alltoolchains: All toolchains that have been registered
:type alltoolchains: dict[str, :class:`csbuild.toolchain.toolchain`]

:var allgenerators: All project generators that have been registered
:type allgenerators: dict[str, csbuild.project_generator.project_generator]
@todo: Is allgenerators the same as project_generators? Can it be deleted?

:var sgmutex: A mutex to wrap around changes to values in _shared_globals
:type sgmutex: threading.Lock

:var target_list: List of targets requested by the user, empty if using default target
:type target_list: list[str]
"""

import threading
import multiprocessing
from . import terminfo

class ProjectState( object ):
	"""
	Defines the state for a project. A subset of these values (PENDING, BUILDING, FINISHED, FAILED, UP_TO_DATE) is also used to define
	state for individual files.
	"""
	PENDING = 0
	BUILDING = 1
	WAITING_FOR_LINK = 2
	LINK_QUEUED = 3
	LINKING = 4
	FINISHED = 5
	FAILED = 6
	LINK_FAILED = 7
	UP_TO_DATE = 8
	ABORTED = 9


class OutputLevel( object ):
	"""
	Used in GUI display, indicates the type of message that a given OutputLine contains.
	"""
	UNKNOWN = -1
	NOTE = 0
	WARNING = 1
	ERROR = 2

class OutputLine( object ):
	"""
	Defines a line of parsed output from the compiler.

	:type level: :OutputLevel:
	:ivar level: the output level associated with this line

	:type text: str
	:ivar text: The actual text of the message

	:type file: str
	:ivar file: The file that generated the message, as indicated by the compiler

	:type line: int
	:ivar line: The line that the message occurred on. -1 if this information is not available.

	:type column: int
	:ivar column: The column that the message occurred on. -1 if this information is not available.

	:type details: list[:OutputLine:]
	:ivar details: Additional details (such as callstacks, macro expansions, or notes) related to this line of output
	"""
	def __init__(self):
		self.level = OutputLevel.UNKNOWN
		self.text = ""
		self.file = ""
		self.line = -1
		self.column = -1
		self.details = []


def MetaClass(meta):
	def wrap(cls):
		return meta(cls.__name__, cls.__bases__, dict(cls.__dict__))
	return wrap


color_supported = terminfo.TermInfo.SupportsColor( )
columns = terminfo.TermInfo.GetNumColumns( ) if color_supported else 0

max_threads = multiprocessing.cpu_count( )
max_linker_threads = max_threads

semaphore = threading.BoundedSemaphore( value = max_threads )
link_semaphore = threading.BoundedSemaphore( value = max_linker_threads )

lock = threading.Lock( )

build_success = True
called_something = False
overrides = ""

quiet = 1

interrupted = False

show_commands = False

oldmd5s = { }
newmd5s = { }

times = []

starttime = 0
esttime = 0
lastupdate = -1

buildtime = -1

target = ""
CleanBuild = False
do_install = False

tempprojects = { }

projects = { }
""" :type: dict[str, csbuild.projectSettings.projectSettings]"""

finished_projects = set( )
built_files = set( )

allfiles = set()
total_precompiles = 0
precompiles_done = 0
total_compiles = 0

install_prefix = "/usr/local/"
install_libdir = "{prefix}/lib"
install_incdir = "{prefix}/include"

makefile_dict = { }

allheaders = { }
headerPaths = {}
headerCheck = {}

current_compile = 1

project_build_list = set( )

sortedProjects = []

errors = []
warnings = []

disable_precompile = False
disable_chunks = False

project_generators = { }

alltargets = set( )
allarchitectures = set( )
alltoolchains = { }
allgenerators = { }
allToolchainArchStrings = { }

selectedToolchains = set( )

rebuild = False

sgmutex = threading.Lock( )

stopOnError = False

target_list = []

autoCloseGui = False

warningcount = 0
errorcount = 0

profile = False

buildFinished = False

logFile = None
cacheDirectory = None

forceProgressBar = ""

class dummy_block( object ):
	"""Some versions of python have a bug in threading where a dummy thread will try to use a value that it deleted.
	To keep that from erroring on systems with those versions of python, this is a dummy object with the required
	methods in it, which can be recreated in __init__ for the thread object to prevent this bug from happening.
	"""


	def __init__( self ):
		"""Dummy __init__ method"""
		return


	def acquire( self ):
		"""Dummy acquire method"""
		return


	def release( self ):
		"""Dummy release method"""
		return


	def notify_all( self ):
		"""Dummy notify_all method"""
		return
