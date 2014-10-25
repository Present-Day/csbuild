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

import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import os
import sys
import uuid
import codecs
import tempfile
import hashlib

from . import project_generator
from . import projectSettings
from . import log
from . import _shared_globals

import csbuild


def GenerateNewUuid(uuidList, name):
	nameIndex = 0
	nameToHash = name

	# Keep generating new UUIDs until we've found one that isn't already in use. This is only useful in cases where we have a pool of objects
	# and each one needs to be guaranteed to have a UUID that doesn't collide with any other object in the same pool.  Though, because of the
	# way UUIDs work, having a collision should be extremely rare anyway.
	while True:
		newUuid = uuid.uuid5(uuid.NAMESPACE_OID, nameToHash)
		if not newUuid in uuidList:
			uuidList.add(newUuid)
			return newUuid

		# Name collision!  The easy solution here is to slightly modify the name in a predictable way.
		nameToHash = "{}{}".format(name, nameIndex)
		++nameIndex


def GetPlatformName(toolchain, architecture):
	# The mapped architectures have special names in Visual Studio.
	platformNameMap = {
		"msvc": {
			"x86": "Win32",
			"arm": "ARM",
		},

		# Android architectures will always build under the Tegra-Android platform.
		"android": {
			"x86": "Tegra-Android",
			"armeabi": "Tegra-Android",
			"armeabi-v7a": "Tegra-Android",
			"armeabi-v7a-hard": "Tegra-Android",
			"mips": "Tegra-Android",
		},
	}

	# If the given architecture is mapped to a name, use that name.
	if toolchain in platformNameMap and architecture in platformNameMap[toolchain]:
		return platformNameMap[toolchain][architecture]

	# Otherwise, use the architecture itself as a fallback.
	return architecture


def IsMicrosoftPlatform(platformName):
	microsoftPlatforms = set(["Win32", "x64", "ARM"])
	return platformName in microsoftPlatforms


def GetPlatformToolsetString(versionNumber):
	platformToolsetMap = {
		2010: "vc100",
		2012: "vc110",
		2013: "vc120",
	}
	return platformToolsetMap[versionNumber]


def CorrectConfigName(configName):
	# Visual Studio can be exceptionally picky about configuration names.  For instance, if your build script has the "debug" target,
	# you may run into problems with Visual Studio showing that alongside it's own "Debug" configuration, which is may have decided
	# to just add alongside your own.  The solution is to just put the configurations in a format it expects (first letter upper case,
	# the rest lowercase).  That way, it will see "Debug" already there and won't try to silently 'fix' that up for you.
	return configName.capitalize()


class Project:
	"""
	Container class for Visual Studio projects.
	"""

	def __init__(self, name, globalProjectUuidList):
		self.name = name
		self.outputPath = ""
		self.dependencyList = set()
		self.id = "{{{}}}".format(str(GenerateNewUuid(globalProjectUuidList, name)).upper())
		self.isFilter = False
		self.isBuildAllProject = False
		self.isRegenProject = False
		self.platformConfigList = []
		self.fullSourceFileList = set()
		self.fullHeaderFileList = set()
		self.fullIncludePathList = set()
		self.fileFilterMap = {}
		self.makefilePath = ""


	def HasConfigAndPlatform(self, config, platform):
		for configName, platformName, _ in self.platformConfigList:
			if configName == config and platformName == platform:
				return True

		return False


class CachedFileData:

	def __init__(self, outputFilePath, fileData, isUserFile):
		self._outputFilePath = outputFilePath
		self._fileData = fileData
		self._isUserFile = isUserFile
		self._md5FileDataHash = hashlib.md5()
		self._md5FileDataHash.update(self._fileData)
		self._md5FileDataHash = self._md5FileDataHash.hexdigest()


	def SaveFile(self):
		canWriteOutputFile = True
		if os.access(self._outputFilePath, os.F_OK):
			# Any user files that already exist will be ignored to preserve user debug settings.
			if self._isUserFile and not csbuild.GetOption("do-not-ignore-user-files"):
				log.LOG_BUILD("Ignoring: {}".format(self._outputFilePath))
				return

			with open(self._outputFilePath, "rb") as fileHandle:
				fileData = fileHandle.read()
				fileDataHash = hashlib.md5()
				fileDataHash.update(fileData)
				fileDataHash = fileDataHash.hexdigest()
				canWriteOutputFile = (fileDataHash != self._md5FileDataHash)

		if canWriteOutputFile:
			log.LOG_BUILD("Writing file {}...".format(self._outputFilePath))
			with open(self._outputFilePath, "wb") as fileHandle:
				fileHandle.write(self._fileData)
		else:
			log.LOG_BUILD("Up-to-date: {}".format(self._outputFilePath))


class ProjectFileType:
	Unknown = None
	VCPROJ = "vcproj"
	VCXPROJ = "vcxproj"


class VisualStudioVersion:
	v2005 = 2005
	v2008 = 2008
	v2010 = 2010
	v2012 = 2012
	v2013 = 2013
	All = [v2005, v2008, v2010, v2012, v2013]


class project_generator_visual_studio(project_generator.project_generator):
	"""
	Generator used to create Visual Studio project files.
	"""

	def __init__(self, path, solutionName, extraArgs):
		project_generator.project_generator.__init__(self, path, solutionName, extraArgs)

		versionNumber = csbuild.GetOption("visual-studio-version")

		self._createNativeProject = False # csbuild.GetOption("create-native-project")
		self._visualStudioVersion = versionNumber
		self._projectMap = {}
		self._configList = []
		self._platformList = []
		self._archMap = {}
		self._reverseConfigMap = {} # A reverse look-up map for the configuration names.
		self._projectFileType = ProjectFileType.Unknown
		self._extraBuildArgs = self.extraargs.replace(",", " ")
		self._fullIncludePathList = set() # Should be a set starting out so duplicates are eliminated.
		self._projectUuidList = set()
		self._orderedProjectList = []

		# Compile a list of the targets and a reverse-lookup list.
		for configName in _shared_globals.alltargets:
			correctedConfigName = CorrectConfigName(configName)
			self._configList.append(correctedConfigName)
			self._reverseConfigMap[correctedConfigName] = configName

		# Compile a list of the platforms for the solution.
		for toolchainName in _shared_globals.selectedToolchains:
			for archName in csbuild.Toolchain(toolchainName).GetValidArchitectures():
				platformName = GetPlatformName(toolchainName, archName)
				if not platformName in self._archMap:
					self._archMap[platformName] = archName
					self._platformList.append(platformName)

		self._configList = sorted(self._configList)
		self._platformList = sorted(self._platformList)

		# Try to convert the version provided by the user into a string.  If that fails, do nothing because we want to keep the original value for error reporting.
		try:
			self._visualStudioVersion = int(self._visualStudioVersion)
		except:
			pass


	@staticmethod
	def AdditionalArgs(parser):
		parser.add_argument("--visual-studio-version",
			help = "Select the version of Visual Studio the generated solution will be compatible with.",
			choices = VisualStudioVersion.All,
			default = VisualStudioVersion.v2012,
			type = int,
		)
		parser.add_argument("--do-not-ignore-user-files",
			help = "When generating project files, do not ignore existing .vcxproj.user files.",
			action = "store_true",
		)
		#parser.add_argument("--create-native-project",
		#	help = "Create a native solution that calls into MSBuild and NOT the makefiles.",
		#	action = "store_true,
		#)


	def WriteProjectFiles(self):

		def recurseGroups(projectMap_out, parentFilter_out, projectOutputPath, projectGroup):
			# Setup the projects first.
			for projectName, projectSettingsMap in projectGroup.projects.items():

				# Fill in the project data.
				projectData = Project(projectName, self._projectUuidList) # Create a new object to contain project data.
				projectData.name = projectName
				projectData.outputPath = os.path.join(self.rootpath, projectOutputPath)

				# Add the current project to the parent filter dependency list. In the case of filters,
				# this isn't really a depencency list, it's just a list of nested projects.
				if parentFilter_out:
					parentFilter_out.dependencyList.add(projectName)

				# Because the list of sources and headers can differ between configurations and architectures,
				# we need to generate a complete list so the project can reference them all. Also, keep track
				# of the project settings per configuration and supported architecture.
				for toolchainName, configMap in projectSettingsMap.items():
					for configName, archMap in configMap.items():
						for archName, settings in archMap.items():
							platformName = GetPlatformName(toolchainName, archName)
							configName = CorrectConfigName(configName)
							projectData.platformConfigList.append((configName, platformName, toolchainName, settings))
							projectData.fullSourceFileList.update(set(settings.allsources))
							projectData.fullHeaderFileList.update(set(settings.allheaders))
							projectData.fullIncludePathList.update(set(settings.includeDirs))
							for source in projectData.fullSourceFileList:
								projectData.fileFilterMap[source] = os.path.join("Source Files", os.path.dirname(os.path.relpath(source, settings.workingDirectory)).replace(".." + os.path.sep, "")).rstrip(os.path.sep)
							for header in projectData.fullHeaderFileList:
								projectData.fileFilterMap[header] = os.path.join("Header Files", os.path.dirname(os.path.relpath(header, settings.workingDirectory)).replace(".." + os.path.sep, "")).rstrip(os.path.sep)

				projectData.fullSourceFileList = sorted(projectData.fullSourceFileList)
				projectData.fullHeaderFileList = sorted(projectData.fullHeaderFileList)
				projectData.platformConfigList = sorted(projectData.platformConfigList)

				# Grab the projectSettings for the first key in the config map and fill in a set of names for dependent projects.
				# We only need the names for now. We can handle resolving them after we have all of the projects mapped.

				configMap = list(projectSettingsMap.values())[0]
				archMap = list(configMap.values())[0]
				settings = list(archMap.values())[0]
				for dependentProjectKey in settings.linkDepends:
					projectData.dependencyList.add(_shared_globals.projects[dependentProjectKey].name)

				# Grab the path to this project's makefile.
				projectData.makefilePath = settings.scriptFile

				projectData.dependencyList = set(sorted(projectData.dependencyList)) # Sort the dependency list.
				projectMap_out[projectData.name] = projectData

			# Sort the parent filter dependency list.
			if parentFilter_out:
				parentFilter_out.dependencyList = set(sorted(parentFilter_out.dependencyList))

			# Next, iterate through each subgroup and handle each one recursively.
			for subGroupName, subGroup in projectGroup.subgroups.items():
				groupPath = os.path.join(projectOutputPath, subGroupName)

				groupPathFinal = os.path.join(self.rootpath, groupPath)

				filterData = Project(subGroupName, self._projectUuidList) # Subgroups should be treated as project filters in the solution.
				filterData.isFilter = True

				# Explicitly map the filter names with a different name to help avoid possible naming collisions.
				projectMap_out["{}.Filter".format(filterData.name)] = filterData

				# Create the group path if it doesn't exist.
				if not os.access(groupPathFinal, os.F_OK):
					os.makedirs(groupPathFinal)

				recurseGroups(projectMap_out, filterData, groupPath, subGroup)


		def resolveDependencies(projectMap):
			for projectId, projectData in projectMap.items():
				resolvedDependencyList = []

				# Sort the dependency name list before parsing it.
				projectData.dependencyList = sorted(projectData.dependencyList)

				# Resolve each project name to their associated project objects.
				for dependentProjectName in projectData.dependencyList:
					resolvedDependencyList.append(projectMap[dependentProjectName])

				# Replace the old name list with the new resolved list.
				projectData.dependencyList = resolvedDependencyList


		# Create the base output directory if necessary.
		if not os.access(self.rootpath, os.F_OK):
			os.makedirs(self.rootpath)

		# When not creating a native project, a custom project must be injected in order to achieve full solution builds
		# since Visual Studio doesn't give us a way to override the behavior of the "Build Solution" command.
		if not self._createNativeProject:
			# Fill in the project data.
			buildAllProjectName = "(BUILD_ALL)"
			buildAllProjectData = Project(buildAllProjectName, self._projectUuidList) # Create a new object to contain project data.
			buildAllProjectData.outputPath = self.rootpath
			buildAllProjectData.isBuildAllProject = True
			buildAllProjectData.makefilePath = csbuild.scriptFiles[0] # Reference the main makefile.

			regenProjectName = "(REGENERATE_SOLUTION)"
			regenProjectData = Project(regenProjectName, self._projectUuidList) # Create a new object to contain project data.
			regenProjectData.outputPath = self.rootpath
			regenProjectData.isRegenProject = True
			regenProjectData.makefilePath = csbuild.scriptFiles[0] # Reference the main makefile.

			# The Build All project doesn't have any project settings, but it still needs all of the platforms and configurations.
			for platformName in self._platformList:
				for configName in self._configList:
					buildAllProjectData.platformConfigList.append((configName, platformName, "", None))
					regenProjectData.platformConfigList.append((configName, platformName, "", None))

			# Add the Build All and Regen projects to the project map.
			self._projectMap[buildAllProjectData.name] = buildAllProjectData
			self._projectMap[regenProjectData.name] = regenProjectData

		recurseGroups(self._projectMap, None, "", projectSettings.rootGroup)
		resolveDependencies(self._projectMap)

		# Copy the project names into a list.
		for projectName, projectData in self._projectMap.items():
			self._orderedProjectList.append(projectName)

		# Sort the list of project names.
		self._orderedProjectList = sorted(self._orderedProjectList)

		# Replace the list of names in the project list with the actual project data.
		for i in range(0, len(self._orderedProjectList)):
			projectName = self._orderedProjectList[i]
			self._orderedProjectList[i] = self._projectMap[projectName]

		# Create a single list of every include search path.
		for projectName, projectData in self._projectMap.items():
			self._fullIncludePathList.update(projectData.fullIncludePathList)

		self._fullIncludePathList = sorted(self._fullIncludePathList)

		is2005 = (self._visualStudioVersion == VisualStudioVersion.v2005)
		is2008 = (self._visualStudioVersion == VisualStudioVersion.v2008)
		is2010 = (self._visualStudioVersion == VisualStudioVersion.v2010)
		is2012 = (self._visualStudioVersion == VisualStudioVersion.v2012)
		is2013 = (self._visualStudioVersion == VisualStudioVersion.v2013)

		if is2005:
			self._GenerateFilesForVs2005()
		elif is2008:
			self._GenerateFilesForVs2008()
		elif is2010:
			self._GenerateFilesForVs2010()
		elif is2012:
			self._GenerateFilesForVs2012()
		elif is2013:
			self._GenerateFilesForVs2013()
		else:
			log.LOG_ERROR("Invalid Visual Studio version: {}".format(self._visualStudioVersion));


	def _GenerateFilesForVs2005(self):
		self._projectFileType = ProjectFileType.VCPROJ
		self._WriteSolutionFile()


	def _GenerateFilesForVs2008(self):
		self._projectFileType = ProjectFileType.VCPROJ
		self._WriteSolutionFile()


	def _GenerateFilesForVs2010(self):
		self._projectFileType = ProjectFileType.VCXPROJ
		self._WriteSolutionFile()
		self._WriteVcxprojFiles()
		self._WriteVcxprojFiltersFiles()
		self._WriteVcxprojUserFiles()


	def _GenerateFilesForVs2012(self):
		self._projectFileType = ProjectFileType.VCXPROJ
		self._WriteSolutionFile()
		self._WriteVcxprojFiles()
		self._WriteVcxprojFiltersFiles()
		self._WriteVcxprojUserFiles()


	def _GenerateFilesForVs2013(self):
		self._projectFileType = ProjectFileType.VCXPROJ
		self._WriteSolutionFile()
		self._WriteVcxprojFiles()
		self._WriteVcxprojFiltersFiles()
		self._WriteVcxprojUserFiles()


	def _WriteSolutionFile(self):

		def writeLineToFile(indentLevel, fileHandle, stringToWrite):
			fileHandle.write("{}{}\r\n".format("\t" * indentLevel, stringToWrite))

		fileFormatVersionNumber = {
			2005: "9.00",
			2008: "10.00",
			2010: "11.00",
			2012: "12.00",
			2013: "12.00",
		}

		tempRootPath = tempfile.mkdtemp()
		finalSolutionPath = "{}.sln".format(os.path.join(self.rootpath, self.solutionname))
		tempSolutionPath = "{}.sln".format(tempRootPath, self.solutionname)

		# Create the temporary root path.
		if not os.access(tempRootPath, os.F_OK):
			os.makedirs(tempRootPath)

		# Visual Studio solution files need to be UTF-8 with the byte order marker because Visual Studio is VERY picky about these files.
		# If ANYTHING is missing or not formatted properly, the Visual Studio version selector may not open the right version or Visual
		# Studio itself may refuse to even attempt to load the file.
		with codecs.open(tempSolutionPath, "w", "utf-8-sig") as fileHandle:
			writeLineToFile(0, fileHandle, "") # Required empty line.
			writeLineToFile(0, fileHandle, "Microsoft Visual Studio Solution File, Format Version {}".format(fileFormatVersionNumber[self._visualStudioVersion]))
			writeLineToFile(0, fileHandle, "# Visual Studio {}".format(self._visualStudioVersion))

			projectFilterList = []

			for projectData in self._orderedProjectList:
				if not projectData.isFilter:
					relativeProjectPath = os.path.relpath(projectData.outputPath, self.rootpath)
					projectFilePath = os.path.join(relativeProjectPath, "{}.{}".format(projectData.name, self._projectFileType))
					nodeId = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"
				else:
					projectFilePath = projectData.name
					nodeId = "{2150E333-8FDC-42A3-9474-1A3956D46DE8}"

					# Keep track of the filters because we need to record those after the projects.
					projectFilterList.append(projectData)

				beginProject = 'Project("{}") = "{}", "{}", "{}"'.format(nodeId, projectData.name, projectFilePath, projectData.id)

				writeLineToFile(0, fileHandle, beginProject)

				# Only write out project dependency information if the current project has any dependencies and if we're creating a native project.
				# If we're not creating a native project, it doesn't matter since csbuild will take care of all that for us behind the scenes.
				# Also, don't list any dependencies for filters. Those will be written out under NestedProjects.
				if self._createNativeProject and not projectData.isFilter and len(projectData.dependencyList) > 0:
					writeLineToFile(1, fileHandle, "ProjectSection(ProjectDependencies) = postProject")

					# Write out the IDs for each dependent project.
					for dependentProjectData in projectData.dependencyList:
						writeLineToFile(2, fileHandle, "{0} = {0}".format(dependentProjectData.id))

					writeLineToFile(1, fileHandle, "EndProjectSection")

				writeLineToFile(0, fileHandle, "EndProject")

			writeLineToFile(0, fileHandle, "Global")

			# Write all of the supported configurations and platforms.
			writeLineToFile(1, fileHandle, "GlobalSection(SolutionConfigurationPlatforms) = preSolution")
			for buildTarget in self._configList:
				for platformName in self._platformList:
					writeLineToFile(2, fileHandle, "{0}|{1} = {0}|{1}".format(buildTarget, platformName))
			writeLineToFile(1, fileHandle, "EndGlobalSection")

			writeLineToFile(1, fileHandle, "GlobalSection(ProjectConfigurationPlatforms) = postSolution")
			for projectData in self._orderedProjectList:
				if not projectData.isFilter:
					for buildTarget in self._configList:
						for platformName in self._platformList:
							writeLineToFile(2, fileHandle, "{0}.{1}|{2}.ActiveCfg = {1}|{2}".format(projectData.id, buildTarget, platformName))
							# A project is only enabled for a given platform if it's the Build All project (only applies to non-native solutions)
							# or if the project is listed under the current configuration and platform.
							if projectData.isBuildAllProject or (self._createNativeProject and projectData.HasConfigAndPlatform(buildTarget, platformName)):
								writeLineToFile(2, fileHandle, "{0}.{1}|{2}.Build.0 = {1}|{2}".format(projectData.id, buildTarget, platformName))
			writeLineToFile(1, fileHandle, "EndGlobalSection")

			writeLineToFile(1, fileHandle, "GlobalSection(SolutionProperties) = preSolution")
			writeLineToFile(2, fileHandle, "HideSolutionNode = FALSE")
			writeLineToFile(1, fileHandle, "EndGlobalSection")

			# Write out any information about nested projects.
			if len(projectFilterList) > 0:
				writeLineToFile(1, fileHandle, "GlobalSection(NestedProjects) = preSolution")
				for filterData in projectFilterList:
					for nestedProjectData in filterData.dependencyList:
						writeLineToFile(2, fileHandle, "{} = {}".format(nestedProjectData.id, filterData.id))
				writeLineToFile(1, fileHandle, "EndGlobalSection")

			writeLineToFile(0, fileHandle, "EndGlobal")

		with open(tempSolutionPath, "rb") as fileHandle:
			fileData = fileHandle.read()
			cachedFile = CachedFileData(finalSolutionPath, fileData, False)
			cachedFile.SaveFile()

		if os.access(tempSolutionPath, os.F_OK):
			os.remove(tempSolutionPath)
			try:
				# Attempt to remove the temp directory.  This will only fail if the directory already existed with files in it.
				# In that case, just catch the exception and move on.
				os.rmdir(tempRootPath)
			except:
				pass


	def _WriteVcxprojFiles(self):
		CreateRootNode = ET.Element
		AddNode = ET.SubElement

		for projectData in self._orderedProjectList:
			if not projectData.isFilter:
				rootNode = CreateRootNode("Project")
				rootNode.set("DefaultTargets", "Build")
				rootNode.set("ToolsVersion", "4.0")
				rootNode.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")

				itemGroupNode = AddNode(rootNode, "ItemGroup")
				itemGroupNode.set("Label", "ProjectConfigurations")

				# Add the project configurations
				for configName, platformName, toolchainName, _ in projectData.platformConfigList:
					projectConfigNode = AddNode(itemGroupNode, "ProjectConfiguration")
					configNode = AddNode(projectConfigNode, "Configuration")
					platformNode = AddNode(projectConfigNode, "Platform")

					projectConfigNode.set("Include", "{}|{}".format(configName, platformName))
					configNode.text = configName
					platformNode.text = platformName

				# Add the project's source files.
				if len(projectData.fullSourceFileList) > 0:
					itemGroupNode = AddNode(rootNode, "ItemGroup")
					for sourceFilePath in projectData.fullSourceFileList:
						sourceFileNode = AddNode(itemGroupNode, "ClCompile")
						sourceFileNode.set("Include", os.path.relpath(sourceFilePath, projectData.outputPath))

						# Handle any configuration or platform excludes for the current file.
						for configName, platformName, toolchainName, settings in projectData.platformConfigList:
							if not sourceFilePath in settings.allsources:
								excludeNode = AddNode(sourceFileNode, "ExcludedFromBuild")
								excludeNode.text = "true"
								excludeNode.set("Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format(configName, platformName))

				# Add the project's header files.
				if len(projectData.fullHeaderFileList) > 0:
					itemGroupNode = AddNode(rootNode, "ItemGroup")
					for sourceFilePath in projectData.fullHeaderFileList:
						sourceFileNode = AddNode(itemGroupNode, "ClInclude")
						sourceFileNode.set("Include", os.path.relpath(sourceFilePath, projectData.outputPath))

						# Handle any configuration or platform excludes for the current file.
						for configName, platformName, toolchainName, settings in projectData.platformConfigList:
							if not sourceFilePath in settings.allheaders:
								excludeNode = AddNode(sourceFileNode, "ExcludedFromBuild")
								excludeNode.text = "true"
								excludeNode.set("Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format(configName, platformName))

				if not self._createNativeProject:
					itemGroupNode = AddNode(rootNode, "ItemGroup")
					makefileNode = AddNode(itemGroupNode, "None")

					makefileNode.set("Include", os.path.relpath(projectData.makefilePath, projectData.outputPath))

				propertyGroupNode = AddNode(rootNode, "PropertyGroup")
				importNode = AddNode(rootNode, "Import")
				projectGuidNode = AddNode(propertyGroupNode, "ProjectGuid")
				namespaceNode = AddNode(propertyGroupNode, "RootNamespace")

				propertyGroupNode.set("Label", "Globals")
				importNode.set("Project", r"$(VCTargetsPath)\Microsoft.Cpp.Default.props")
				projectGuidNode.text = projectData.id
				namespaceNode.text = projectData.name

				# If we're not creating a native project, Visual Studio needs to know this is a makefile project.
				if not self._createNativeProject:
					keywordNode = AddNode(propertyGroupNode, "Keyword")
					keywordNode.text = "MakeFileProj"

				for configName, platformName, toolchainName, _ in projectData.platformConfigList:
					propertyGroupNode = AddNode(rootNode, "PropertyGroup")
					propertyGroupNode.set("Label", "Configuration")
					propertyGroupNode.set("Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format(configName, platformName))

					if IsMicrosoftPlatform(platformName):
						platformToolsetNode = AddNode(propertyGroupNode, "PlatformToolset")
						platformToolsetNode.text = GetPlatformToolsetString(self._visualStudioVersion)

					if self._createNativeProject:
						# TODO: Add properties for native projects.
						pass
					else:
						configTypeNode = AddNode(propertyGroupNode, "ConfigurationType")
						configTypeNode.text = "Makefile"

				importNode = AddNode(rootNode, "Import")
				importNode.set("Project", r"$(VCTargetsPath)\Microsoft.Cpp.props")

				for configName, platformName, toolchainName, _ in projectData.platformConfigList:
					importGroupNode = AddNode(rootNode, "ImportGroup")
					importGroupNode.set("Label", "PropertySheets")
					importGroupNode.set("Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format(configName, platformName))

					# Microsoft platforms import special property sheets.
					if IsMicrosoftPlatform(platformName):
						importNode = AddNode(importGroupNode, "Import")
						importNode.set("Label", "LocalAppDataPlatform")
						importNode.set("Project", r"$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props")
						importNode.set("Condition", "exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')")

				for configName, platformName, toolchainName, settings in projectData.platformConfigList:
					propertyGroupNode = AddNode(rootNode, "PropertyGroup")
					propertyGroupNode.set("Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format(configName, platformName))

					if self._createNativeProject:
						# TODO: Add properties for non-native projects.
						pass
					else:
						buildCommandNode = AddNode(propertyGroupNode, "NMakeBuildCommandLine")
						cleanCommandNode = AddNode(propertyGroupNode, "NMakeCleanCommandLine")
						rebuildCommandNode = AddNode(propertyGroupNode, "NMakeReBuildCommandLine")
						includePathNode = AddNode(propertyGroupNode, "NMakeIncludeSearchPath")
						outDirNode = AddNode(propertyGroupNode, "OutDir")
						intDirNode = AddNode(propertyGroupNode, "IntDir")

						pythonExePath = os.path.normcase(sys.executable)
						mainMakefile = os.path.relpath(os.path.join(os.getcwd(), csbuild.mainFile), projectData.outputPath)

						if not projectData.isRegenProject:
							archName = self._archMap[platformName]
							projectArg = " --project={}".format(projectData.name) if not projectData.isBuildAllProject else ""
							properConfigName = self._reverseConfigMap[configName]

							buildCommandNode.text = "{} {} --target={} --architecture={}{} {}".format(pythonExePath, mainMakefile, properConfigName, archName, projectArg, self._extraBuildArgs)
							cleanCommandNode.text = "{} {} --clean --target={} --architecture={}{} {}".format(pythonExePath, mainMakefile, properConfigName, archName, projectArg, self._extraBuildArgs)
							rebuildCommandNode.text = "{} {} --rebuild --target={} --architecture={}{} {}".format(pythonExePath, mainMakefile, properConfigName, archName, projectArg, self._extraBuildArgs)
							includePathNode.text = ";".join(self._fullIncludePathList)
						else:
							buildCommandNode.text = "{} {} {}".format(pythonExePath, mainMakefile, " ".join(sys.argv[1:]))
							rebuildCommandNode.text = buildCommandNode.text
							cleanCommandNode.text = buildCommandNode.text

						if settings and settings.defines and len(settings.defines) > 0:
							preprocessorNode = AddNode(propertyGroupNode, "NMakePreprocessorDefinitions")
							preprocessorNode.text = ""
							for define in settings.defines:
								preprocessorNode.text += "{};".format(define)
							preprocessorNode.text += "$(NMakePreprocessorDefinitions)"

						if not projectData.isBuildAllProject and not projectData.isRegenProject:
							outputNode = AddNode(propertyGroupNode, "NMakeOutput")

							outDirNode.text = os.path.relpath(settings.outputDir, projectData.outputPath)
							intDirNode.text = os.path.relpath(settings.objDir, projectData.outputPath)
							outputNode.text = os.path.relpath(os.path.join(settings.outputDir, settings.outputName), projectData.outputPath)
						else:
							# Gotta put this stuff somewhere for the Build All project.
							outDirNode.text = projectData.name + "_log"
							intDirNode.text = "$(OutDir)"

				importNode = AddNode(rootNode, "Import")
				importNode.set("Project", r"$(VCTargetsPath)\Microsoft.Cpp.targets")

				self._SaveXmlFile(rootNode, os.path.join(projectData.outputPath, "{}.{}".format(projectData.name, self._projectFileType)), False)


	def _WriteVcxprojFiltersFiles(self):
		CreateRootNode = ET.Element
		AddNode = ET.SubElement

		for projectData in self._orderedProjectList:
			if not projectData.isFilter:
				rootNode = CreateRootNode("Project")
				rootNode.set("ToolsVersion", "4.0")
				rootNode.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")

				if not projectData.isBuildAllProject and not projectData.isRegenProject:
					itemGroupNode = AddNode(rootNode, "ItemGroup")

					# Gather a list of filter paths.
					filterList = set()
					for file, filter in projectData.fileFilterMap.items():
						filterList.add(filter)
						# Visual Studio requires that each directory level be registered as individual filters.
						while True:
							filter = os.path.dirname(filter)
							if filter:
								filterList.add(filter)
							else:
								break

					# Add each path as a new filter node.
					filterGuidList = set()
					for filter in sorted(filterList):
						filterNode = AddNode(itemGroupNode, "Filter")
						uniqueIdNode = AddNode(filterNode, "UniqueIdentifier")

						filterNode.set("Include", filter)
						uniqueIdNode.text = "{{{}}}".format(GenerateNewUuid(filterGuidList, filter))

					# Add the project's source files.
					if len(projectData.fullSourceFileList) > 0:
						itemGroupNode = AddNode(rootNode, "ItemGroup")
						for sourceFilePath in projectData.fullSourceFileList:
							sourceFileNode = AddNode(itemGroupNode, "ClCompile")
							filterNode = AddNode(sourceFileNode, "Filter")
							sourceFileNode.set("Include", os.path.relpath(sourceFilePath, projectData.outputPath))
							filterNode.text = projectData.fileFilterMap[sourceFilePath]

					# Add the project's header files.
					if len(projectData.fullHeaderFileList) > 0:
						itemGroupNode = AddNode(rootNode, "ItemGroup")
						for headerFilePath in projectData.fullHeaderFileList:
							headerFileNode = AddNode(itemGroupNode, "ClInclude")
							filterNode = AddNode(headerFileNode, "Filter")
							headerFileNode.set("Include", os.path.relpath(headerFilePath, projectData.outputPath))
							filterNode.text = projectData.fileFilterMap[headerFilePath]

				self._SaveXmlFile(rootNode, os.path.join(projectData.outputPath, "{}.{}.filters".format(projectData.name, self._projectFileType)), False)


	def _WriteVcxprojUserFiles(self):
		CreateRootNode = ET.Element
		AddNode = ET.SubElement

		for projectData in self._orderedProjectList:
			if not projectData.isFilter:
				rootNode = CreateRootNode("Project")
				rootNode.set("ToolsVersion", "4.0")
				rootNode.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")

				if not projectData.isBuildAllProject and not projectData.isRegenProject:
					for configName, platformName, toolchainName, _ in projectData.platformConfigList:
						if IsMicrosoftPlatform(platformName):
							propertyGroupNode = AddNode(rootNode, "PropertyGroup")
							workingDirNode = AddNode(propertyGroupNode, "LocalDebuggerWorkingDirectory")
							debuggerTypeNode = AddNode(propertyGroupNode, "LocalDebuggerDebuggerType")
							debuggerFlavorNode = AddNode(propertyGroupNode, "DebuggerFlavor")

							propertyGroupNode.set("Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format(configName, platformName))
							workingDirNode.text = "$(OutDir)"
							debuggerTypeNode.text = "NativeOnly"
							debuggerFlavorNode.text = "WindowsLocalDebugger"


				self._SaveXmlFile(rootNode, os.path.join(projectData.outputPath, "{}.{}.user".format(projectData.name, self._projectFileType)), True)


	def _SaveXmlFile(self, rootNode, xmlFilename, isUserFile):
		# Grab a string of the XML document we've created and save it.
		xmlString = ET.tostring(rootNode)

		# Convert to the original XML to a string on Python3.
		if sys.version_info >= (3, 0):
			xmlString = xmlString.decode("utf-8")

		# Use minidom to reformat the XML since ElementTree doesn't do it for us.
		formattedXmlString = minidom.parseString(xmlString).toprettyxml("\t", "\n", encoding = "utf-8")
		if sys.version_info >= (3, 0):
			formattedXmlString = formattedXmlString.decode("utf-8")

		inputLines = formattedXmlString.split("\n")
		outputLines = []

		# Copy each line of the XML to a list of strings.
		for line in inputLines:
			outputLines.append(line)

		# Concatenate each string with a newline.
		finalXmlString = "\n".join(outputLines)
		if sys.version_info >= (3, 0):
			finalXmlString = finalXmlString.encode("utf-8")

		cachedFile = CachedFileData(xmlFilename, finalXmlString, isUserFile)
		cachedFile.SaveFile()
