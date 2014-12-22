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

"""Contains the interface for all vsgen platforms."""


class PlatformBase( object ):
	def __init__( self ):
		self._outputNameMap = dict()
		self._outDirMap = dict()
		self._intDirMap = dict()
		self._definesMap = dict()


	@staticmethod
	def GetToolchainName():
		"""
		Retrieve the toolchain-architecture name combination that this platform will apply to.

		:return: str
		"""
		pass


	@staticmethod
	def GetVisualStudioName():
		"""
		Retrieve the name value that will be show up in Visual Studio for a platform.  Must be a name that Visual Studio recognizes.

		:return: str
		"""
		pass


	def AddOutputName( self, vsConfigName, projectName, outputName ):
		"""
		Map an output name to a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:param outputName: Output directory to add.
		:type outputName: str
		"""
		mapKey = ( vsConfigName, projectName )
		if not mapKey in self._outputNameMap:
			self._outputNameMap.update( { mapKey: outputName } )
		else:
			self._outputNameMap[mapKey] = outputName


	def AddOutputDirectory( self, vsConfigName, projectName, outDir ):
		"""
		Map an output directory to a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:param outDir: Output directory to add.
		:type outDir: str
		"""
		mapKey = ( vsConfigName, projectName )
		if not mapKey in self._outDirMap:
			self._outDirMap.update( { mapKey: outDir } )
		else:
			self._outDirMap[mapKey] = outDir


	def AddIntermediateDirectory( self, vsConfigName, projectName, intDir ):
		"""
		Map an output directory to a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:param intDir: Intermediate directory to add.
		:type intDir: str
		"""
		mapKey = ( vsConfigName, projectName )
		if not mapKey in self._intDirMap:
			self._intDirMap.update( { mapKey: intDir } )
		else:
			self._intDirMap[mapKey] = intDir


	def AddDefines( self, vsConfigName, projectName, defines ):
		"""
		Map a list of preprocessor defines to a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:param defines: Defines to add.
		:type defines: list
		"""
		mapKey = ( vsConfigName, projectName )
		if not mapKey in self._definesMap:
			self._definesMap.update( { mapKey: defines } )
		else:
			self._definesMap[mapKey].append( defines )


	def GetOutputName( self, vsConfigName, projectName ):
		"""
		Retrieve an output name from a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:return: str
		"""
		mapKey = ( vsConfigName, projectName )
		assert mapKey in self._outputNameMap
		return self._outputNameMap[mapKey]


	def GetOutputDirectory( self, vsConfigName, projectName ):
		"""
		Retrieve an output directory from a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:return: str
		"""
		mapKey = ( vsConfigName, projectName )
		assert mapKey in self._outDirMap
		return self._outDirMap[mapKey]


	def GetIntermediateDirectory( self, vsConfigName, projectName ):
		"""
		Retrieve an intermediate from a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:return: str
		"""
		mapKey = ( vsConfigName, projectName )
		assert mapKey in self._intDirMap
		return self._intDirMap[mapKey]


	def GetDefines( self, vsConfigName, projectName ):
		"""
		Retrieve an list of preprocessor defines from a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:return: list
		"""
		mapKey = ( vsConfigName, projectName )
		assert mapKey in self._definesMap
		return self._definesMap[mapKey]


	def WriteProjectConfiguration( self, parentXmlNode, vsConfigName ):
		"""
		Write the project configuration nodes for this platform.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`_elementtree.SubElement`

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str
		"""
		pass


	def WritePropertyGroup( self, parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative ):
		"""
		Write the project's property group nodes for this platform.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`_elementtree.SubElement`

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str

		:param vsPlatformToolsetName: Name of the platform toolset for the selected version of Visual Studio.
		:type vsPlatformToolsetName: str

		:param isNative: Is this a native project?
		:type isNative: bool
		"""
		pass


	def WriteImportProperties( self, parentXmlNode, vsConfigName, isNative ):
		"""
		Write any special import properties for this platform.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`_elementtree.SubElement'

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str

		:param isNative: Is this a native project?
		:type isNative: bool
		"""
		pass
