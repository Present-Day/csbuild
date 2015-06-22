##CSB

CSBuild is a C/C++-oriented cross-platform build and project generation system written in Python. CSBuild attempts to address a number of issues with existing build systems, including performance, maintainability, and usability. CSBuild focuses on providing an easy, understandable, readable syntax for defining a build structure, and then providing your builds to you in the shortest possible amount of time.

CSBuild uses a number of techniques to accomplish these goals.

To achieve better build performance, CSBuild uses:

- "Chunked" builds with intelligent chunking and un-chunking to provide efficient builds for both full and incremental build types
- Effective parallel building, including parallelism between projects, between targets, between platforms - as long as there's something for CSBuild to do, it will make maximum use of the number of threads you give it (which, by default, is the number of CPU cores available to your system)
- Incremental links with static libraries in the msvc toolchain - by linking in the intermediate .obj files instead of the .lib file, CSBuild is able to take advantage of incremental links even when static libraries have been changed
- Better change detection - CSBuild uses MD5 checksums in addition to modification dates to determine whether or not to recompile a translation unit
- Manual build order adjustments - CSBuild attempts to build things in an appropriate order for the dependency structure set up in the makefile, but sometimes this order isn't the most ideal. To solve this problem, CSBuild allows you to set project build priorities to move long builds earlier in the process.

To improve maintainability and usability:

- CSBuild makefiles themselves are written in Python, which for many developers provides an already-familiar syntax, and also provides the power of a full programming language to handle any special project needs
- Abstraction of compiler functionality - in many cases, setting a flag for all your project's supported toolchains can be accomplished with a single function call
- Easy, human-readable organization - projects exist within clearly visible blocks of code, and if desired, can even be separated into their own individual files
- Source file discovery - instead of specifying your files (requiring maintanence every time your file structure changes), CSBuild searches a specified directory (or directories) to find files. Adding a new file is as simple as dropping it into the right folder.

Beyond this, though, CSBuild also provides a number of powerful tools for build analysis.

- When compiling on the command line, CSBuild provides easily readable, color-coded output, with multiple levels of verbosity, so you can easily see and comprehend everything CSBuild does.
- In interactive terminals, CSBuild also provides a progress bar so you can watch your build and understand approximately how much build time is left. Even in non-interactive terminals, each file that is compiled includes in its output the current and total file counts, so you know where you are in your build process even without the progress bar.
- Each action presents calculated times associated with it, so you can see how long each project takes to build and link, and how long your total build process takes to complete, as well.
- Dependency graph generation - CSBuild can generate a dependency graph that can be opened with graphvis to see all the connections between your projects, and even the external libraries being linked into them. With the python 'graphvis' module installed, CSBuild will also additionally take the extra step of converting this dependency graph directly to a .png image, so you can view it immediately without the intermediate step of opening it with graphvis.

Even more powerful, however, are the GUI tools included with CSBuild (gui requires PyQt 4 to be present on your system). The GUI displays an unprecedented amount of information about your build process, providing you the tools and understanding needed to diagnose and improve build problems. Among the features of the CSBuild GUI are:

- Progress bars for every project, color-coded to show exactly what's happening and when
- Expandable projects so you can see what files are pending, compiling, and finished at the micro level
- Readouts of build times for each project and file
- A timeline view that allows you to look back on the history of a build even after it finished and see what was happening at any given point in the build, and what items in the build took particularly long times to complete
- Error and warning parsing, with all output from the compiler and linker being organized into a hierarchical, expandable/collapsible view
- A built-in text editor for fixing build problems, which opens at the right line and column when you double-click any error
- A line-by-line build profiler, giving you minute detail about the compile costs of every line of code in your codebase, including costs of each #include, enabling you to find opportunities to shorten your build times by rearranging your code

CSBuild is also cross-platform compatible (comes stock with toolchains to build using msvc, gcc, clang, or the android NDK, and provides easy and straight-forward methods of extending that support to additional toolchains, and has been tested to function on windows, mac, and linux, though it currently does not have support for frameworks on mac), and capable of generating project files that you can open with your favorite IDE, which will then execute csbuild to maintain optimal build speed. (Currently, CSBuild comes stock with generators for Visual Studio, SlickEdit, and QtCreator; Eclipse, XCode, NetBeans, and other additional IDEs will be added over time. As with toolchains, CSBuild also provides methods to extend the types of projects it can generate.)

For an example CSBuild makefile, check out https://github.com/Present-Day/Sprawl/blob/master/make.py

Documentation is available at api.csbuild.org
