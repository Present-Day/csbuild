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
**Project Generator Module**

Defines the base class for project generation.
"""

from abc import abstractmethod, ABCMeta
import os
from . import _shared_globals


@_shared_globals.MetaClass(ABCMeta)
class project_generator( object ):
	"""
	Base class used for project generation.
	To create a new project generator, inherit from this class, and then use
	:func:`csbuild.RegisterProjectGenerator`
	"""
	def __init__( self, path, solutionname, extraargs ):
		"""
		:param path: The output path for the solution
		:type path: str

		:param solutionname: The name for the output solution file
		:type solutionname: str

		:param extraargs: Additional arguments specified by the user to be used in the solution's build command
		:type extraargs: str
		"""
		self.rootpath = os.path.abspath( path )
		self.solutionname = solutionname
		self.extraargs = extraargs


	@staticmethod
	def AdditionalArgs( parser ):
		"""
		Asks for additional command-line arguments to be added by the generator.

		:param parser: A parser for these arguments to be added to
		:type parser: argparse.argument_parser
		"""
		pass


	@abstractmethod
	def WriteProjectFiles( self ):
		"""
		Actually performs the work of writing the project files to disk.
		"""
		pass