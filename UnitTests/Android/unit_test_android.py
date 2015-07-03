import csbuild

#csbuild.SetActiveToolchain("android")

@csbuild.project("AndroidTest_Basic", "AndroidTest_Basic")
def AndroidTest_Basic():
	csbuild.Toolchain("android").SetCcCommand("gcc")
	csbuild.Toolchain("android").SetCxxCommand("g++")
	csbuild.Toolchain("android").SetPackageName("csbuild.UnitTest.AndroidBasic")
	csbuild.Toolchain("android").SetActivityName("CSBUnitTestAndroidBasic")
	csbuild.DisablePrecompile()
	csbuild.SetOutput("AndroidTest_Basic", csbuild.ProjectType.Application)
	csbuild.Toolchain("android").AddLibraries("android", "m", "log", "dl", "c")
	csbuild.SetSupportedToolchains("msvc", "android")
