//
//  main.cpp
//  
//
//  Created by Brandon on 11/5/14.
//
//

#include <staticLibrary/library.h>
#include <sharedLibrary/library.h>

#include <stdio.h>
#include <dlfcn.h>


typedef void (*DoWorkModuleFunc)();

int main(int argc, char* argv[])
{
	printf("\n");

	// Static library test

	printf("[Static Library Test]\n");
	StaticLibrary::DoWork();


	// Shared library test

	printf("[Shared Library Test]\n");
	SharedLibrary::DoWork();


	// Loadable module test

	printf("[Loadable Module Test]\n");
	
	void* bundleModule = nullptr;
	void* functionSymbol = nullptr;

	// Load the bundle into a file image.
	bundleModule = dlopen("loadableModule.bundle", RTLD_GLOBAL);
	if(!bundleModule)
	{
		fprintf(stderr, "ERROR: Could not load loadableModule.bundle!\n");
		return -1;
	}

	// Try to retrieve the symbol of the function we want to call.
	functionSymbol = dlsym(bundleModule, "DoWork");
	if(!functionSymbol)
	{
		fprintf(stderr, "ERROR: Could not find symbol \"Mul\" in loadableModule.bundle!\n");
		return -1;
	}

	// Cast the symbol to the function signature we expect it to be.
	DoWorkModuleFunc doWork_module = DoWorkModuleFunc(functionSymbol);

	doWork_module();

	// We're done with bundle, so we can close it for now.
	dlclose(bundleModule);

	printf("\n");
	
	return 0;
}