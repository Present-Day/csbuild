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
Contains a plugin class for creating android NDK projects
"""
import glob
import platform
import os
import shutil
import subprocess
import sys
import shlex
import re
import platform

from . import toolchain_gcc
from . import log
from . import _shared_globals
import csbuild

if platform.system() == "Windows":
	__CSL = None
	import ctypes
	def symlink(source, link_name):
		'''symlink(source, link_name)
		   Creates a symbolic link pointing to source named link_name'''
		global __CSL
		if __CSL is None:
			csl = ctypes.windll.kernel32.CreateSymbolicLinkW
			csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
			csl.restype = ctypes.c_ubyte
			__CSL = csl
		flags = 0
		if source is not None and os.path.isdir(source):
			flags = 1
		if __CSL(link_name, source, flags) == 0:
			raise ctypes.WinError()
else:
	symlink = os.symlink

class AndroidBase( object ):
	def __init__(self):
		#TODO: Figure out a way to share some of this data between compiler and linker
		self._ndkHome = os.getenv("NDK_HOME")
		self._sdkHome = os.getenv("ANDROID_HOME")
		self._antHome = os.getenv("ANT_HOME")
		self._javaHome = os.getenv("JAVA_HOME")
		#self._maxSdkVersion = 19
		#TODO: Determine this from highest number in the filesystem.
		self._targetSdkVersion = 19
		self._minSdkVersion = 1
		self._packageName = "csbuild.autopackage"
		self._activityName = None
		self._usedFeatures = []
		self._sysRootDir = ""
		self._keystoreLocation = ""
		self._keystorePwFile = ""
		self._keyPwFile = ""
		self._keystoreAlias = ""
		self._stlVersion = "GNU"
		self._addNativeAppGlue = True

	def CopyTo(self, other):
		other._ndkHome = self._ndkHome
		other._sdkHome = self._sdkHome
		other._antHome = self._antHome
		other._javaHome = self._javaHome
		#other._maxSdkVersion = self._maxSdkVersion
		other._targetSdkVersion = self._targetSdkVersion
		other._minSdkVersion = self._minSdkVersion
		other._packageName = self._packageName
		other._activityName = self._activityName
		other._usedFeatures = list(self._usedFeatures)
		other._sysRootDir = self._sysRootDir
		other._keystoreLocation = self._keystoreLocation
		other._keystorePwFile = self._keystorePwFile
		other._keyPwFile = self._keyPwFile
		other._keystoreAlias = self._keystoreAlias
		other._stlVersion = self._stlVersion
		other._addNativeAppGlue = self._addNativeAppGlue

	def NdkHome(self, pathToNdk):
		self._ndkHome = os.path.abspath(pathToNdk)

	def SdkHome(self, pathToSdk):
		self._sdkHome = os.path.abspath(pathToSdk)

	def AntHome(self, pathToAnt):
		self._antHome = os.path.abspath(pathToAnt)

	def JavaHome(self, pathToJava):
		self._javaHome = os.path.abspath(pathToJava)

	def Keystore(self, pathToKeystore):
		self._keystoreLocation = os.path.abspath(pathToKeystore)
		if not self._keystorePwFile:
			self._keystorePwFile = os.path.join(csbuild.mainfileDir, os.path.basename(pathToKeystore+".pass"))

	def KeystorePwFile(self, pathToPwFile):
		self._keystorePwFile = os.path.abspath(pathToPwFile)

	def KeyPwFile(self, pathToPwFile):
		self._keyPwFile = os.path.abspath(pathToPwFile)

	def KeystoreAlias(self, alias):
		self._keystoreAlias = alias

	def MinSdkVersion(self, version):
		self._minSdkVersion = version

	#def MaxSdkVersion(self, version):
	#	self._maxSdkVersion = version

	def TargetSdkVersion(self, version):
		self._targetSdkVersion = version

	def PackageName(self, name):
		self._packageName = name

	def ActivityName(self, name):
		self._activityName = name

	def UsedFeatures(self, *args):
		self._usedFeatures += list(args)

	def AddNativeAppGlue(self, addGlue):
		self._addNativeAppGlue = addGlue

	def GetValidArchitectures(self):
		return ['x86', 'armeabi', 'armeabi-v7a', 'armeabi-v7a-hard', 'mips']

	def _getTargetTriple(self, project):
		if self.isClang:
			if project.outputArchitecture == "x86":
				return "-target i686-linux-android"
			elif project.outputArchitecture == "mips":
				return "-target mipsel-linux-android"
			elif project.outputArchitecture == "armeabi":
				return "-target armv7-linux-androideabi"
			else:
				return "-target armv7a-linux-androideabi"
		else:
			return ""

	def _getSimplifiedArch(self, project):
		if project.outputArchitecture.startswith("arm"):
			return "arm"
		return project.outputArchitecture

	def _setSysRootDir(self, project):
		toolchainsDir = os.path.join(self._ndkHome, "toolchains")
		arch = self._getSimplifiedArch(project)

		dirs = glob.glob(os.path.join(toolchainsDir, "{}*".format(arch)))

		bestCompilerVersion = ""

		for dirname in dirs:
			prebuilt = os.path.join(toolchainsDir, dirname, "prebuilt")
			if not os.access(prebuilt, os.F_OK):
				continue

			if dirname > bestCompilerVersion:
				bestCompilerVersion = dirname

		if not bestCompilerVersion:
			log.LOG_ERROR("Couldn't find compiler for architecture {}.".format(project.outputArchitecture))
			csbuild.Exit(1)

		if platform.system() == "Windows":
			platformName = "windows"
		else:
			platformName = "linux"

		sysRootDir = os.path.join(toolchainsDir, bestCompilerVersion, "prebuilt", platformName)
		dirs = list(glob.glob("{}*".format(sysRootDir)))
		self._sysRootDir = dirs[0]

	def _getCommands(self, project, cmd1, cmd2, searchInLlvmPath = False):
		toolchainsDir = os.path.join(self._ndkHome, "toolchains")
		arch = self._getSimplifiedArch(project)

		dirs = glob.glob(os.path.join(toolchainsDir, "{}*".format("llvm" if searchInLlvmPath else arch)))

		bestCompilerVersion = ""

		for dirname in dirs:
			prebuilt = os.path.join(toolchainsDir, dirname, "prebuilt")
			if not os.access(prebuilt, os.F_OK):
				continue

			if dirname > bestCompilerVersion:
				bestCompilerVersion = dirname

		if not bestCompilerVersion:
			log.LOG_ERROR("Couldn't find compiler for architecture {}.".format(project.outputArchitecture))
			csbuild.Exit(1)

		if platform.system() == "Windows":
			platformName = "windows"
			ext = ".exe"
		else:
			platformName = "linux"
			ext = ""

		cmd1Name = cmd1 + ext
		cmd2Name = cmd2 + ext

		binDir = os.path.join(toolchainsDir, bestCompilerVersion, "prebuilt", platformName)
		dirs = list(glob.glob("{}*".format(binDir)))
		binDir = os.path.join(dirs[0], "bin")
		maybeCmd1 = os.path.join(binDir, cmd1Name)

		if os.access(maybeCmd1, os.F_OK):
			cmd1Result = maybeCmd1
			cmd2Result = os.path.join(binDir, cmd2Name)
		else:
			dirs = list(glob.glob(os.path.join(binDir, "*-{}".format(cmd1Name))))
			prefix = dirs[0].rsplit('-', 1)[0]
			cmd1Result = dirs[0]
			cmd2Result = "{}-{}".format(prefix, cmd2Name)

		return cmd1Result, cmd2Result


class AndroidCompiler(AndroidBase, toolchain_gcc.compiler_gcc):
	def __init__(self):
		AndroidBase.__init__(self)
		toolchain_gcc.compiler_gcc.__init__(self)

		self._toolchainPath = ""
		self._setupCompleted = False

	def copy(self):
		ret = toolchain_gcc.compiler_gcc.copy(self)
		AndroidBase.CopyTo(self, ret)
		ret._toolchainPath = self._toolchainPath
		ret._setupCompleted = self._setupCompleted
		return ret

	def postPrepareBuildStep(self, project):
		if project.metaType == csbuild.ProjectType.Application and self._addNativeAppGlue:
			appGlueDir = os.path.join( self._ndkHome, "sources", "android", "native_app_glue" )
			project.include_dirs.append(appGlueDir)
			project.extraDirs.append(appGlueDir)
			project.RediscoverFiles()

	def GetDefaultArchitecture(self):
		return "armeabi-v7a"

	def _SetupCompiler(self, project):
		#TODO: Let user choose which compiler version to use; for now, using the highest numbered version.

		if self.isClang:
			ccName = "clang"
			cxxName = "clang++"
		else:
			ccName = "gcc"
			cxxName = "g++"

		self.settingsOverrides["cc"], self.settingsOverrides["cxx"] = self._getCommands(project, ccName, cxxName, self.isClang)

	def SetupForProject( self, project ):
		#toolchain_gcc.compiler_gcc.SetupForProject(self, project)
		if not self._setupCompleted:
			if "clang" in project.cc or "clang" in project.cxx:
				self.isClang = True
			self._SetupCompiler(project)
			self._setSysRootDir(project)
			self._setupCompleted = True

	def prePrepareBuildStep(self, project):
		self.SetupForProject(project)

	def _getSystemDirectories(self, project, isCpp):
		ret = ""
		if isCpp:
			if self._stlVersion == "GNU":
				ret += "-isystem \"{}\" ".format(os.path.join(
					self._ndkHome,
					"sources",
					"cxx-stl",
					"gnu-libstdc++",
					"4.8",
					"libs",
					project.outputArchitecture,
					"include")
				)
				ret += "-isystem \"{}\" ".format(os.path.join( self._ndkHome, "sources", "cxx-stl", "gnu-libstdc++", "4.8", "include"))
			elif self._stlVersion == "stlport":
				ret += "-isystem \"{}\" ".format(os.path.join( self._ndkHome, "sources", "cxx-stl", "system", "include"))
				ret += "-isystem \"{}\" ".format(os.path.join( self._ndkHome, "sources", "cxx-stl", "stlport", "stlport"))
			elif self._stlVersion == "libc++":
				ret += "-isystem \"{}\" ".format(os.path.join( self._ndkHome, "sources", "cxx-stl", "llvm-libc++", "libcxx", "include"))


		ret += "--sysroot \"{}\" ".format(self._sysRootDir)
		ret += "-isystem \"{}\" ".format(
			os.path.join(
				self._ndkHome,
				"platforms",
				"android-{}".format(self._targetSdkVersion),
				"arch-{}".format(self._getSimplifiedArch(project)),
				"usr",
				"include"
			)
		)

		ret += "-I {} ".format(self._ndkHome)
		return ret

	def get_base_command( self, compiler, project, isCpp ):
		self.SetupForProject(project)

		if not self.isClang:
			exitcodes = "-pass-exit-codes"
		else:
			exitcodes = ""

		if isCpp:
			standard = self.cppStandard
		else:
			standard = self.cStandard

		return "\"{}\" {} -Winvalid-pch -c {}-g{} -O{} {}{}{} {} {} {}".format(
			compiler,
			exitcodes,
			self.get_defines( project.defines, project.undefines ),
			project.debug_level,
			project.opt_level,
			"-fPIC " if project.type == csbuild.ProjectType.SharedLibrary else "",
			"-pg " if project.profile else "",
			"--std={0}".format( standard ) if standard != "" else "",
			" ".join( project.cpp_compiler_flags ) if isCpp else " ".join( project.c_compiler_flags ),
			self._getSystemDirectories(project, isCpp),
			self._getTargetTriple(project)
		)

	def get_include_dirs( self, includeDirs ): 
		"""Returns a string containing all of the passed include directories, formatted to be passed to gcc/g++.""" 
		ret = ""
		for inc in includeDirs:
			ret += "-I{} ".format( os.path.abspath( inc ) )
		return ret


class AndroidLinker(AndroidBase, toolchain_gcc.linker_gcc):
	def __init__(self):
		AndroidBase.__init__(self)
		toolchain_gcc.linker_gcc.__init__(self)
		self._setupCompleted = False

	def copy(self):
		ret = toolchain_gcc.linker_gcc.copy(self)
		AndroidBase.CopyTo(self, ret)
		ret._setupCompleted = self._setupCompleted
		return ret

	@staticmethod
	def additional_args( parser ):
		parser.add_argument("--ndk-home", help="Location of android NDK directory")
		parser.add_argument("--sdk-home", help="Location of android SDK directory")
		parser.add_argument("--ant-home", help="Location of apache ant")
		parser.add_argument("--java-home", help="Location of java")
		parser.add_argument("--keystore", help="Location of keystore to sign release apks (default is {makefile location}/{project name}.keystore")
		parser.add_argument("--keystore-pwfile", help="Location of password file for loading keystore (default is {makefile location}/{keystore_filename}.pass)")
		parser.add_argument("--alias", help="Alias to use inside the keystore (default is project name)")
		parser.add_argument("--key-pwfile", help="Location of password file for signing release apks (default is {makefile location}/{keystore_filename}.{alias}.pass)")
		parser.add_argument("--zipalign-location", help="Location of zipalign")

	def _SetupLinker(self, project):
		#TODO: Let user choose which compiler version to use; for now, using the highest numbered version.
		self._ld, self._ar = self._getCommands(project, "ld", "ar")

	def SetupForProject( self, project ):
		toolchain_gcc.linker_gcc.SetupForProject(self, project)
		if not self._setupCompleted:
			if "clang" in project.cc or "clang" in project.cxx:
				self.isClang = True
			self._SetupLinker(project)
			self._setSysRootDir(project)
			self._setupCompleted = True

			if not self._keystoreLocation:
				self._keystoreLocation = os.path.join(csbuild.mainfileDir, project.name+".keystore")

			if not self._keystoreAlias:
				self._keystoreAlias = project.name

			alias = csbuild.get_option("alias")

			if alias:
				self._keystoreAlias = alias

			if not self._keystorePwFile:
				self._keystorePwFile = os.path.join(csbuild.mainfileDir, self._keystoreLocation+".pass")

			if not self._keyPwFile:
				self._keyPwFile = os.path.join(csbuild.mainfileDir, self._keystoreAlias + ".keystore." + project.name + ".pass")


			ndkHome = csbuild.get_option("ndk_home")
			sdkHome = csbuild.get_option("sdk_home")
			antHome = csbuild.get_option("ant_home")
			javaHome = csbuild.get_option("java_home")
			keystore = csbuild.get_option("keystore")
			keystorePwFile = csbuild.get_option("keystore_pwfile")
			keyPwFile = csbuild.get_option("key_pwfile")

			if ndkHome:
				self._ndkHome = ndkHome
			if sdkHome:
				self._sdkHome = sdkHome
			if antHome:
				self._antHome = antHome
			if javaHome:
				self._javaHome = javaHome
			if keystore:
				self._keystoreLocation = keystore
			if keystorePwFile:
				self._keystorePwFile = keystorePwFile
			if keyPwFile:
				self._keyPwFile = keyPwFile

	def _getSystemLibDirs(self, project):
		ret = ""
		if project.hasCppFiles:
			if self._stlVersion == "GNU":
				ret += "-L\"{}\" ".format(os.path.join(
					self._ndkHome,
					"sources",
					"cxx-stl",
					"gnu-libstdc++",
					"4.8",
					"libs",
					project.outputArchitecture)
				)
				if project.static_runtime:
					ret += "-lgnustl_static "
				else:
					ret += "-lgnustl_shared "
			elif self._stlVersion == "stlport":
				ret += "-L\"{}\" ".format(os.path.join(
					self._ndkHome,
					"sources",
					"cxx-stl",
					"stlport",
					"libs",
					project.outputArchitecture)
				)
				if project.static_runtime:
					ret += "-lstlport_static "
				else:
					ret += "-lstlport_shared "
			elif self._stlVersion == "libc++":
				ret += "-L\"{}\" ".format(os.path.join(
					self._ndkHome,
					"sources",
					"cxx-stl",
					"llvm-libc++",
					"libs",
					project.outputArchitecture)
				)
				if project.static_runtime:
					ret += "-lc++_static "
				else:
					ret += "-lc++_shared "

		ret += "--sysroot \"{}\"".format(self._sysRootDir)
		return ret



	def get_link_command( self, project, outputFile, objList ):
		self.SetupForProject( project )

		linkFile = os.path.join(self._project_settings.csbuild_dir, "{}.cmd".format(self._project_settings.name))

		data = " ".join( objList )
		if sys.version_info >= (3, 0):
			data = data.encode("utf-8")

		file_mode = 438 # Octal 0666
		flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
		if platform.system() == "Windows":
			flags |= os.O_NOINHERIT
		fd = os.open(linkFile, flags, file_mode)
		os.write(fd, data)
		os.fsync(fd)
		os.close(fd)

		if project.type == csbuild.ProjectType.StaticLibrary:
			return "\"{}\" rcs {} {}".format( self._ar, outputFile, " ".join( objList ) )
		else:
			if project.hasCppFiles:
				cmd = project.activeToolchain.Compiler().settingsOverrides["cxx"]
			else:
				cmd = project.activeToolchain.Compiler().settingsOverrides["cc"]

			libDir = os.path.join( self._ndkHome, "platforms", "android-{}".format(self._targetSdkVersion), "arch-{}".format(self._getSimplifiedArch(project)), "usr", "lib")

			if self.isClang:
				crtbegin = os.path.join(project.obj_dir, "crtbegin_so.o")
				if not os.access(crtbegin, os.F_OK):
					symlink(os.path.join(libDir, "crtbegin_so.o"), crtbegin)
				crtend = os.path.join(project.obj_dir, "crtend_so.o")
				if not os.access(crtend, os.F_OK):
					symlink(os.path.join(libDir, "crtend_so.o"), crtend)

			return "\"{}\" {}-o{} {} {} {}{}{} {} {}-g{} -O{} {} {} {} {} -L\"{}\"".format(
				cmd,
				"-pg " if project.profile else "",
				outputFile,
				"@{}".format(linkFile),
				"-Wl,--no-as-needed -Wl,--start-group" if not self.strictOrdering else "",
				self.get_libraries( project.libraries ),
				self.get_static_libraries( project.static_libraries ),
				self.get_shared_libraries( project.shared_libraries ),
				"-Wl,--end-group" if not self.strictOrdering else "",
				self.get_library_dirs( project.library_dirs, True ),
				project.debug_level,
				project.opt_level,
				"-shared" if project.type == csbuild.ProjectType.SharedLibrary else "",
				" ".join( project.linker_flags ),
				self._getSystemLibDirs(project),
				self._getTargetTriple(project),
				libDir
			)

	def find_library( self, project, library, library_dirs, force_static, force_shared ):
		success = True
		out = ""
		self.SetupForProject( project )
		nullOut = os.path.join(project.csbuild_dir, "null")
		try:
			cmd = [self._ld, "-o", nullOut, "--verbose",
				   "-static" if force_static else "-shared" if force_shared else "", "-l{}".format( library ),
				   "-L", os.path.join( self._ndkHome, "platforms", "android-{}".format(self._targetSdkVersion), "arch-{}".format(self._getSimplifiedArch(project)), "usr", "lib")]
			cmd += shlex.split( self.get_library_dirs( library_dirs, False ), posix=(platform.system() != "Windows") )

			if _shared_globals.show_commands:
				print(" ".join(cmd))

			out = subprocess.check_output( cmd, stderr = subprocess.STDOUT )
		except subprocess.CalledProcessError as e:
			out = e.output
			success = False
		finally:
			if os.access(nullOut, os.F_OK):
				os.remove(nullOut)
			if sys.version_info >= (3, 0):
				RMatch = re.search( "attempt to open (.*) succeeded".encode( 'utf-8' ), out, re.I )
			else:
				RMatch = re.search( "attempt to open (.*) succeeded", out, re.I )
				#Some libraries (such as -liberty) will return successful but don't have a file (internal to ld maybe?)
			#In those cases we can probably assume they haven't been modified.
			#Set the mtime to 0 and return success as long as ld didn't return an error code.
			if RMatch is not None:
				lib = RMatch.group( 1 )
				if sys.version_info >= (3, 0):
					self._actual_library_names[library] = os.path.basename(lib).decode('utf-8')
				else:
					self._actual_library_names[library] = os.path.basename(lib)
				return lib
			elif not success:
				try:
					cmd = [self._ld, "-o", nullOut, "--verbose",
						   "-static" if force_static else "-shared" if force_shared else "", "-l:{}".format( library ),
						   "-L", os.path.join( self._ndkHome, "platforms", "android-{}".format(self._targetSdkVersion), "arch-{}".format(self._getSimplifiedArch(project)), "usr", "lib")]
					cmd += shlex.split( self.get_library_dirs( library_dirs, False ), posix=(platform.system() != "Windows") )

					if _shared_globals.show_commands:
						print(" ".join(cmd))

					out = subprocess.check_output( cmd, stderr = subprocess.STDOUT )
				except subprocess.CalledProcessError as e:
					out = e.output
					success = False
				finally:
					if os.access(nullOut, os.F_OK):
						os.remove(nullOut)
					if sys.version_info >= (3, 0):
						RMatch = re.search( "attempt to open (.*) succeeded".encode( 'utf-8' ), out, re.I )
					else:
						RMatch = re.search( "attempt to open (.*) succeeded", out, re.I )
						#Some libraries (such as -liberty) will return successful but don't have a file (internal to ld maybe?)
					#In those cases we can probably assume they haven't been modified.
					#Set the mtime to 0 and return success as long as ld didn't return an error code.
					if RMatch is not None:
						lib = RMatch.group( 1 )
						if sys.version_info >= (3, 0):
							self._actual_library_names[library] = os.path.basename(lib).decode('utf-8')
						else:
							self._actual_library_names[library] = os.path.basename(lib)
						return lib
					elif not success:
						return None

	def prePrepareBuildStep(self, project):
		#Everything on Android has to build as a shared library
		project.metaType = project.type
		if project.type == csbuild.ProjectType.Application:
			project.type = csbuild.ProjectType.SharedLibrary
			if not project.output_name.startswith("lib"):
				project.output_name = "lib{}".format(project.output_name)

	def postBuildStep(self, project):
		log.LOG_BUILD("Generating APK for {} ({} {}/{})".format(project.output_name, project.targetName, project.outputArchitecture, project.activeToolchainName))
		if project.metaType != csbuild.ProjectType.Application:
			return

		appDir = os.path.join(project.csbuild_dir, "apk", project.name)
		if os.access(appDir, os.F_OK):
			shutil.rmtree(appDir)

		androidTool = os.path.join(self._sdkHome, "tools", "android.bat" if platform.system() == "Windows" else "android.sh")
		fd = subprocess.Popen(
			[
				androidTool, "create", "project",
				"--path", appDir,
				"--target", "android-{}".format(self._targetSdkVersion),
				"--name", project.name,
				"--package", "com.{}.{}".format(self._packageName, project.name),
				"--activity", project.name if self._activityName is None else self._activityName
			],
			stderr=subprocess.STDOUT,
			stdout=subprocess.PIPE
		)
		output, errors = fd.communicate()
		if fd.returncode != 0:
			log.LOG_ERROR("Android tool failed to generate project skeleton!\n{}".format(output))
			return

		libDir = ""
		if project.outputArchitecture == "x86":
			libDir = "x86"
		elif project.outputArchitecture == "mips":
			libDir = "mips"
		elif project.outputArchitecture == "armeabi":
			libDir = "armeabi"
		elif project.outputArchitecture == "armeabi-v7a-hard":
			libDir = "armeabi-v7a-hard"
		else:
			libDir = "armeabi-v7a"

		libDir = os.path.join(appDir, "libs", libDir)

		if not os.access(libDir, os.F_OK):
			os.makedirs(libDir)

		for library in project.library_locs:
			#don't copy android system libraries
			if library.startswith(self._ndkHome):
				continue
			shutil.copyfile(library, os.path.join(libDir, os.path.basename(library)))

		for dep in project.linkDepends:
			depProj = _shared_globals.projects[dep]
			libFile = os.path.join(depProj.output_dir, depProj.output_name)
			shutil.copyfile(libFile, os.path.join(libDir, os.path.basename(libFile)))

		shutil.copyfile(os.path.join(project.output_dir, project.output_name), os.path.join(libDir, os.path.basename(project.output_name)))

		with open(os.path.join(appDir, "AndroidManifest.xml"), "w") as f:
			f.write("<manifest xmlns:android=\"http://schemas.android.com/apk/res/android\"\n")
			f.write("  package=\"com.csbuild.autopackage.{}\"\n".format(project.name))
			f.write("  android:versionCode=\"1\"\n")
			f.write("  android:versionName=\"1.0\">\n")
			f.write("  <uses-sdk android:minSdkVersion=\"{}\" android:targetSdkVersion=\"{}\"/>\n".format(self._minSdkVersion, self._targetSdkVersion))
			for feature in self._usedFeatures:
				#example: android:glEsVersion=\"0x00020000\"
				f.write("  <uses-feature {}></uses-feature>".format(feature))
			f.write("  <application android:label=\"{}\" android:hasCode=\"false\">\n".format(project.name))
			f.write("    <activity android:name=\"android.app.NativeActivity\"\n")
			f.write("      android:label=\"{}\">\n".format(project.name))
			f.write("      android:configChanges=\"orientation|keyboardHidden\">\n")
			f.write("      <meta-data android:name=\"android.app.lib_name\" android:value=\"{}\"/>\n".format(project.output_name[3:-3]))
			f.write("      <intent-filter>\n")
			f.write("        <action android:name=\"android.intent.action.MAIN\"/>\n")
			f.write("        <category android:name=\"android.intent.category.LAUNCHER\"/>\n")
			f.write("      </intent-filter>\n")
			f.write("    </activity>\n")
			f.write("  </application>\n")
			f.write("</manifest>\n")

		if project.opt_level != csbuild.OptimizationLevel.Max:
			antBuildType = "debug"
		else:
			antBuildType = "release"

		fd = subprocess.Popen(
			[
				os.path.join(self._antHome, "bin", "ant.bat" if platform.system() == "Windows" else "ant.sh"),
				antBuildType
			],
			stderr=subprocess.STDOUT,
			stdout=subprocess.PIPE,
			cwd=appDir
		)

		output, errors = fd.communicate()
		if fd.returncode != 0:
			log.LOG_ERROR("Ant build failed!\n{}".format(output))
			return

		appNameBase = "{}-{}".format(project.output_name[3:-3], antBuildType)
		appName = appNameBase + ".apk"
		appStartLoc = os.path.join(appDir, "bin", appName)

		if antBuildType == "release":
			appNameUnsigned = appNameBase + "-unsigned.apk"
			appUnsignedLoc = os.path.join(appDir, "bin", appNameUnsigned)
			with open(self._keystorePwFile, "r") as f:
				storePass = f.read().strip()
			if os.access(self._keyPwFile, os.F_OK):
				with open(self._keyPwFile, "r") as f:
					keyPass = f.read().strip()
			else:
				keyPass = storePass

			log.LOG_BUILD("Signing {} with key {}...".format(appName, self._keystoreLocation))

			jarsigner = os.path.join(self._javaHome, "bin", "jarsigner{}".format(".exe" if platform.system() == "Windows" else ""))
			fd = subprocess.Popen(
				[
					jarsigner,
					"-sigalg", "SHA1withRSA",
					"-digestalg", "SHA1",
					"-keystore", self._keystoreLocation,
					"-storepass", storePass,
					"-keypass", keyPass,
					appUnsignedLoc,
					self._keystoreAlias
				],
				stderr=subprocess.STDOUT,
				stdout=subprocess.PIPE,
				cwd=appDir
			)

			output, errors = fd.communicate()
			if fd.returncode != 0:
				log.LOG_ERROR("Signing failed!\n{}".format(output))
				return

			log.LOG_BUILD("Zip-Aligning {}...".format(appName, self._keystoreLocation))

			zipalign = os.path.join(self._sdkHome, "tools", "zipalign{}".format(".exe" if platform.system() == "Windows" else ""))
			fd = subprocess.Popen(
				[
					zipalign,
					"-v", "4",
					appUnsignedLoc,
					appStartLoc
				],
				stderr=subprocess.STDOUT,
				stdout=subprocess.PIPE,
				cwd=appDir
			)

			output, errors = fd.communicate()
			if fd.returncode != 0:
				log.LOG_ERROR("Zipalign failed!\n{}".format(output))
				return

		appEndLoc = os.path.join(project.output_dir, appName)
		if os.access(appEndLoc, os.F_OK):
			os.remove(appEndLoc)

		shutil.move(appStartLoc, project.output_dir)
		log.LOG_BUILD("Finished generating APK for {} ({} {}/{})".format(project.output_name, project.targetName, project.outputArchitecture, project.activeToolchainName))
