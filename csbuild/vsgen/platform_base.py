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

from abc import abstractmethod


class PlatformBase( object ):
	def __init__( self ):
		self._outputNameMap = dict()
		self._outDirMap = dict()
		self._intDirMap = dict()
		self._definesMap = dict()
		self._projectSettingsMap = dict()


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
		self._definesMap[mapKey] = self._definesMap.get( mapKey, [] ) + defines


	def AddProjectSettings( self, vsConfigName, projectName, projectSettings ):
		"""
		Map a projectSettings object to a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:param projectSettings: Defines to add.
		:type projectSettings: class`csbuild.projectSettings`
		"""
		mapKey = ( vsConfigName, projectName )
		self._projectSettingsMap[mapKey] = projectSettings


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
		return self._outputNameMap.get( mapKey, "" )


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
		return self._outDirMap.get( mapKey, "" )


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
		return self._intDirMap.get( mapKey, "" )


	def GetDefines( self, vsConfigName, projectName ):
		"""
		Retrieve a list of preprocessor defines from a project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:return: list
		"""
		mapKey = ( vsConfigName, projectName )
		return self._definesMap.get( mapKey, [] )


	def GetProjectSettings( self, vsConfigName, projectName ):
		"""
		Retrieve the projectSettings object mapped to a specific project and configuration.

		:param vsConfigName: Output configuration name.
		:type vsConfigName: str

		:param projectName: Name of the project associated with the defines.
		:type projectName: str

		:return: class`csbuild.projectSettings`
		"""
		mapKey = ( vsConfigName, projectName )
		return self._projectSettingsMap.get( mapKey, None )


	@abstractmethod
	def WriteGlobalHeader( self, parentXmlNode ):
		"""
		Write any top-level information about this platform at the start of the project.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`
		"""
		pass


	@abstractmethod
	def WriteGlobalFooter( self, parentXmlNode ):
		"""
		Write any final data nodes needed by the project.

		:param parentXmlNode: Parent project XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`
		"""
		pass


	@abstractmethod
	def WriteProjectConfiguration( self, parentXmlNode, vsConfigName ):
		"""
		Write the project configuration nodes for this platform.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str
		"""
		pass


	@abstractmethod
	def WriteConfigPropertyGroup( self, parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative ):
		"""
		Write the property group nodes for the project's configuration and platform.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str

		:param vsPlatformToolsetName: Name of the platform toolset for the selected version of Visual Studio.
		:type vsPlatformToolsetName: str

		:param isNative: Is this a native project?
		:type isNative: bool
		"""
		pass


	@abstractmethod
	def WriteImportProperties( self, parentXmlNode, vsConfigName, isNative ):
		"""
		Write any special import properties for this platform.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str

		:param isNative: Is this a native project?
		:type isNative: bool
		"""
		pass


	@abstractmethod
	def WriteUserDebugPropertyGroup( self, parentXmlNode, vsConfigName, projectData ):
		"""
		Write the property group nodes specifying the user debug settings.

		:param parentXmlNode: Parent XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str

		:param projectData: Project data.
		:type projectData: class`csbuild.project_generator_visual_studio_v2.Project`
		"""
		pass


	@abstractmethod
	def WriteExtraPropertyGroupBuildNodes( self, parentXmlNode, vsConfigName, projectData ):
		"""
		Write extra property group nodes related to platform build properties.

		:param parentXmlNode: Parent property group XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`

		:param vsConfigName: Visual Studio configuration name.
		:type vsConfigName: str

		:param projectData: Project data.
		:type projectData: class`csbuild.project_generator_visual_studio_v2.Project`
		"""
		pass


	@abstractmethod
	def WriteGlobalImportTargets( self, parentXmlNode, isNative ):
		"""
		Write global import target needed for the project.

		:param parentXmlNode: Parent project XML node.
		:type parentXmlNode: class`xml.etree.ElementTree.SubElement`

		:param isNative: Is this a native project?
		:type isNative: bool
		"""
		pass
