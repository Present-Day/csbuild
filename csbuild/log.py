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
**Logging Module**
"""

import threading
import time
import math
import sys
from . import _shared_globals
from . import terminfo

#<editor-fold desc="Logging">

logMutex = threading.Lock()

def LOG_MSG( color, level, msg, quietThreshold ):
	"""Print a message to stdout"""
	with logMutex:
		if _shared_globals.quiet < quietThreshold:
			if _shared_globals.color_supported:
				terminfo.TermInfo.SetColor( color )
				sys.stdout.write( "{}: ".format( level ) )
				sys.stdout.flush()
				terminfo.TermInfo.ResetColor( )
				sys.stdout.write( msg )
				sys.stdout.write( "\n" )
			else:
				print("{0}: {1}".format( level, msg ))
			sys.stdout.flush()
		_shared_globals.logFile.write("{0}: {1}\n".format( level, msg ))


def LOG_ERROR( msg ):
	"""
	Log an error message

	:param msg: Text to log
	:type msg: str
	"""
	LOG_MSG( terminfo.TermColor.RED, "ERROR", msg, 3 )
	_shared_globals.errors.append( msg )


def LOG_WARN( msg ):
	"""
	Log a warning

	:param msg: Text to log
	:type msg: str
	"""
	LOG_WARN_NOPUSH( msg )
	_shared_globals.warnings.append( msg )


def LOG_WARN_NOPUSH( msg ):
	"""
	Log a warning, don't push it to the list of warnings to be echoed at the end of compilation.

	:param msg: Text to log
	:type msg: str
	"""
	LOG_MSG( terminfo.TermColor.YELLOW, "WARN", msg, 3 )


def LOG_INFO( msg ):
	"""
	Log general info. This info only appears with -v specified.

	:param msg: Text to log
	:type msg: str
	"""
	LOG_MSG( terminfo.TermColor.CYAN, "INFO", msg, 1 )


def LOG_BUILD( msg ):
	"""
	Log info related to building

	:param msg: Text to log
	:type msg: str
	"""
	LOG_MSG( terminfo.TermColor.MAGENTA, "BUILD", msg, 2 )


def LOG_LINKER( msg ):
	"""
	Log info related to linking

	:param msg: Text to log
	:type msg: str
	"""
	LOG_MSG( terminfo.TermColor.GREEN, "LINKER", msg, 2 )


def LOG_THREAD( msg ):
	"""
	Log info related to threads, particularly stalls caused by waiting on another thread to finish

	:param msg: Text to log
	:type msg: str
	"""
	LOG_MSG( terminfo.TermColor.BLUE, "THREAD", msg, 2 )


def LOG_INSTALL( msg ):
	"""
	Log info related to the installer

	:param msg: Text to log
	:type msg: str
	"""
	LOG_MSG( terminfo.TermColor.WHITE, "INSTALL", msg, 2 )


#</editor-fold>


class stdoutWriter( object ):
	def __init__( self, oldstdout ):
		self.stdout = oldstdout
		self.barPresent = False
		self.mutex = threading.Lock()

	def write( self, text ):
		if not text:
			return

		with self.mutex:
			if self.barPresent:
				self.stdout.write( "\r" + " " * _shared_globals.columns + "\r" )

			self.stdout.write(text)

			if _shared_globals.forceProgressBar == "on":
				_shared_globals.columns = 80
			elif _shared_globals.forceProgressBar == "off":
				_shared_globals.columns = 0
			else:
				_shared_globals.columns = terminfo.TermInfo.GetNumColumns( )

			if text.endswith("\n") and _shared_globals.columns != 0 and not _shared_globals.buildFinished and _shared_globals.total_compiles > 0:
				self.barPresent = True
				curtime = time.time( ) - _shared_globals.starttime

				if _shared_globals.columns > 0:
					minutes = math.floor( curtime / 60 )
					seconds = math.floor( curtime % 60 )

					totalCompletedCompiles = 0
					for project in _shared_globals.sortedProjects:
						totalCompletedCompiles += project.compilationCompleted

					perc = 1 if _shared_globals.total_compiles == 0 else float(totalCompletedCompiles)/float(_shared_globals.total_compiles)
					num = int( math.floor( perc * (_shared_globals.columns - 10) ) )
					if num >= _shared_globals.columns - 10:
						num = _shared_globals.columns - 11

					perc = int(round(perc * 100))
					if perc == 100:
						perc = 99

					self.stdout.write(
						"[" + "=" * num + " " * (
							(
								_shared_globals.columns - 10
							) - num
						) + "](~{2: 3}%)".format(
							int( minutes ),
							int( seconds ),
							perc
						)
					)
					self.stdout.flush( )
			else:
				self.barPresent = False

	def flush(self):
		self.stdout.flush()
