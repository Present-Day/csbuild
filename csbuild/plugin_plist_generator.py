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

import os
import subprocess
import sys
import tempfile
import time

import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

from . import _utils
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
		self._cmakeStringSubstitutionMap = dict()
		self._variableSubstitutionMap = dict()
		self._externalPlistPath = ""
		self._resolvedPlistPath = ""


	def AddNode( self, nodeType, key, value = None, parent = None):
		"""
		Add a new node to the plist.

		:param nodeType: Type of the new node.
		:type nodeType: :class:`plugin_plist_generator.PListNodeType`

		:param key: Node key
		:type key: str

		:param value: Node value
		:type value: str

		:param parent: Parent to the new node.
		:type parent: :class:`plugin_plist_generator.PListGenerator.Node`

		:return: :class:`plugin_plist_generator.PListGenerator.Node`
		"""
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


	def SetExternalFile( self, filePath ):
		"""
		Set an external file path as the ASCII plist file. If this is set before Output() is called, the file this
		path points to will be used as the input plist rather than generating one.

		:param filePath: File path to the external plist.
		:type filePath: str

		:return: None
		"""
		filePath = _utils.FixupRelativePath( filePath )
		filePath = _utils.PathWorkingDirPair( filePath )
		self._externalPlistPath = filePath

		# Reset the resolved path if the external path whenever the external path has been changed.
		self._resolvedPlistPath = ""


	def AddCmakeStringSubstitution(self, key, value):
		"""
		Add a key/value pair to be used for string substitution in the ASCII plist before a binary version is generated.
		This is intended to mimic CMake's behavior so as to be compatible with any plist template files one might also use with CMake.
		What this means is that if you were to call AddCmakeStringSubstitution( "VERSION_NUMBER", "1.1.0" ), it would look for
		the string "@VERSION_NUMBER@" and replace it with "1.1.0".

		Example:
		(before) <key>CFBundleVersion</key><string>@VERSION_NUMBER@</string>
		(after)  <key>CFBundleVersion</key><string>1.1.0</string>

		:param key: Substitution key to search for.
		:type key: str

		:param value: Value to substitute for the key.
		:type value: str

		:return: None
		"""
		assert isinstance( key, str ), "Key must be a string!"
		assert isinstance( value, str ), "Value must be a string!"
		self._cmakeStringSubstitutionMap[key] = value


	def AddVariableSubstitution(self, key, value):
		"""
		Add a key/value pair to be used for variable substitution in the ASCII plist before a binary version is generated.
		What this means is that if you were to call AddVariableSubstitution( "EXECUTABLE_NAME", "MyApp" ), it would look for
		the string "$(EXECUTABLE_NAME)" and replace it with "MyApp".

		Example:
		(before) <key>CFBundleVersion</key><string>$(EXECUTABLE_NAME)</string>
		(after)  <key>CFBundleVersion</key><string>MyApp</string>

		:param key: Substitution key to search for.
		:type key: str

		:param value: Value to substitute for the key.
		:type value: str

		:return: None
		"""
		assert isinstance( key, str ), "Key must be a string!"
		assert isinstance( value, str ), "Value must be a string!"
		self._variableSubstitutionMap[key] = value


	def Output( self, project, outputFilePath ):
		"""
		Create a binary plist file.

		:param outputFilePath: Output path for the plist file.
		:type outputFilePath: str

		:return: bool
		"""
		# Process the ascii plist, generating a temporary copy with the string substitutions.
		if self._externalPlistPath:
			# Only resolve the file path if it hasn't been already.
			if not self._resolvedPlistPath:
				self._resolvedPlistPath = os.path.normpath( os.path.join( self._externalPlistPath.workingDir, _utils.ResolveProjectMacros( self._externalPlistPath.path, project ) ) )
			tempAsciiFilePath = self._processExternalFile()
		else:
			tempAsciiFilePath = self._generateTempAsciiFile()

		# Generate the binary plist.
		success = self._generateFinalBinary( tempAsciiFilePath, outputFilePath )

		# Remove the temporary ascii plist.
		os.remove(tempAsciiFilePath)

		return success


	def _doSubstitutionsOnString( self, inputString ):
		# Handle the string substitution here.
		for key, value in self._cmakeStringSubstitutionMap.items():
			inputString = inputString.replace( "@{}@".format( key ), value )

		# Handle the variable substitution here.
		for key, value in self._variableSubstitutionMap.items():
			inputString = inputString.replace( "$({})".format( key ), value )

		return inputString


	def _processExternalFile( self ):
		if not os.access( self._resolvedPlistPath, os.F_OK ):
			raise FileNotFoundError( "External plist file not found: {}".format( self._resolvedPlistPath ) )

		# Read in the external plist.
		with open( self._resolvedPlistPath, mode = "r" ) as fileHandle:
			inputFileString = fileHandle.read()

		inputFileString = self._doSubstitutionsOnString( inputFileString )

		fd, tempFilePath = tempfile.mkstemp()

		# Write out the substituted plist to a temporary file.
		with os.fdopen(fd, "w") as fileHandle:
			fileHandle.write(inputFileString)

		return tempFilePath


	def _generateTempAsciiFile( self ):
		CreateRootNode = ET.Element
		AddNode = ET.SubElement

		def ProcessPlistNode( plistNode, parentXmlNode ):
			if not plistNode.parent or plistNode.parent.nodeType != PListNodeType.Array:
				keyNode = AddNode( parentXmlNode, "key" )
				keyNode.text = plistNode.key

			valueNode = None

			# Determine the tag for the value node since it differs between node types.
			if plistNode.nodeType == PListNodeType.Array:
				valueNode = AddNode( parentXmlNode, "array" )
			elif plistNode.nodeType == PListNodeType.Dictionary:
				valueNode = AddNode( parentXmlNode, "dict" )
			elif plistNode.nodeType == PListNodeType.Boolean:
				valueNode = AddNode( parentXmlNode, "true" if plistNode.value else "false" )
			elif plistNode.nodeType == PListNodeType.Data:
				valueNode = AddNode( parentXmlNode, "data")
				if sys.version_info() >= (3, 0):
					valueNode.text = plistNode.value.decode( "utf-8" )
				else:
					valueNode.text = plistNode.value
			elif plistNode.nodeType == PListNodeType.Date:
				valueNode = AddNode( parentXmlNode, "date")
				valueNode.text = plistNode.value
			elif plistNode.nodeType == PListNodeType.Number:
				valueNode = AddNode( parentXmlNode, "integer" )
				valueNode.text = str( plistNode.value )
			elif plistNode.nodeType == PListNodeType.String:
				valueNode = AddNode( parentXmlNode, "string" )
				valueNode.text = plistNode.value

			# Save the children only if the the current node is an array or a dictionary.
			if plistNode.nodeType == PListNodeType.Array or plistNode.nodeType == PListNodeType.Dictionary:
				for child in sorted( plistNode.children, key=lambda x: x.key ):
					ProcessPlistNode( child, valueNode )

		rootNode = CreateRootNode( "plist", attrib={ "version": "1.0" } )
		topLevelDict = AddNode( rootNode, "dict" )

		# Recursively process each node to build the XML node tree.
		for node in sorted( self._rootNodes, key=lambda x: x.key ):
			ProcessPlistNode( node, topLevelDict )

		# Grab a string of the XML document we've created and save it.
		xmlString = ET.tostring( rootNode )

		# Convert to the original XML to a string on Python3.
		if sys.version_info >= ( 3, 0 ):
			xmlString = xmlString.decode( "utf-8" )

		xmlString = self._doSubstitutionsOnString( xmlString )

		# Use minidom to reformat the XML since ElementTree doesn't do it for us.
		formattedXmlString = minidom.parseString( xmlString ).toprettyxml( "\t", "\n", encoding = "utf-8" )
		if sys.version_info >= ( 3, 0 ):
			formattedXmlString = formattedXmlString.decode( "utf-8" )

		inputLines = formattedXmlString.split( "\n" )
		outputLines = []

		# Copy each line of the XML to a list of strings.
		for line in inputLines:
			outputLines.append( line )

		# Plists require the DOCTYPE, but neither elementtree nor minidom will add that for us.
		# The easiest way to add it manually is to split each line of the XML into a list, then
		# reformat it with the DOCTYPE inserted as the 2nd line in the string.
		finalXmlString = '{}\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n{}'.format( outputLines[0], "\n".join( outputLines[1:] ) )

		# Generate a temporary file for us to write the ascii plist contents into.
		fd, tempFilePath = tempfile.mkstemp()

		# Write out the plist contents.
		with os.fdopen(fd, "w") as fileHandle:
			fileHandle.write( finalXmlString )

		return tempFilePath


	def _generateFinalBinary( self, inputFilePath, outputDirPath ):
		# Run plutil to convert the XML plist file to binary.
		fd = subprocess.Popen(
			[
				"plutil",
				"-convert", "binary1",
				"-o", os.path.join( outputDirPath, "Info.plist" ),
				inputFilePath
			],
			stderr = subprocess.STDOUT,
			stdout = subprocess.PIPE,
		)

		output, errors = fd.communicate()
		if fd.returncode != 0:
			return False

		return True
