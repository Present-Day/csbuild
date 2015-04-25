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
Contains a plugin class for generating property list data on OSX/iOS.
"""

# Reference:
#   https://developer.apple.com/library/ios/documentation/general/Reference/InfoPlistKeyReference/Introduction/Introduction.html

import time

from . import log


class PListNodeType( object ):
	Array = 0
	Dictionary = 1
	Boolean = 2
	Data = 3
	Date = 4
	Number = 5
	String = 6


class PListGenerator( object ):
	"""
	Utility class for building a property list and outputting the result as a binary '.plist' file.
	"""

	class Node( object ):
		def __init__( self, nodeType , key, value):
			self.nodeType = nodeType
			self.key = key
			self.value = value
			self.parent = None
			self.children = set()

			formatFunction = {
				PListNodeType.Array: self._formatNullValue,
				PListNodeType.Dictionary: self._formatNullValue,
				PListNodeType.Boolean: self._formatBoolValue,
				PListNodeType.Data: self._formatDataValue,
				PListNodeType.Date: self._formatDateValue,
				PListNodeType.Number: self._formatNumberValue,
				PListNodeType.String: self._formatStringValue,
			}

			# Make sure we have a valid type.
			if not nodeType in formatFunction:
				raise Exception( "Invalid plist node type!" )

			# Call the value formatting function.
			function = formatFunction[nodeType]
			function()


		def _formatNullValue( self ):
			# Some nodes should not have a value.
			self.value = None


		def _formatBoolValue( self ):
			if not isinstance( self.value, bool ):
				self.value = False


		def _formatDataValue( self ):
			if not isinstance( self.value, bytes ):
				self.value = b""


		def _formatDateValue( self ):
			# Ignore the user's custom value and replace it with an ISO string representing the current date and time.
			self.value = time.strftime( "%Y-%m-%dT%H:%M:%SZ" )


		def _formatNumberValue( self ):
			if not isinstance( self.value, int ):
				self.value = 0


		def _formatStringValue( self ):
			if not isinstance( self.value, str ):
				self.value = ""



	def __init__( self ):
		self._rootNodes = set()


	def AddNode( self, nodeType, key, value = None, parent = None):
		newNode = PListGenerator.Node( nodeType, key, value )
		if parent:
			# Don't allow adding children to nodes that won't support them.
			if parent.nodeType != PListNodeType.Array and parent.nodeType != PListNodeType.Dictionary:
				log.LOG_WARN( 'PListNode "{}" is not an array or dictionary; cannot add "{}" as its child!'.format( parent.key, key ) )
				return None

			parent.children.add( newNode )
			newNode.parent = parent
		else:
			self._rootNodes.add( newNode )

		return newNode
