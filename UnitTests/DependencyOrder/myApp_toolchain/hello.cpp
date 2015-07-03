#include "../myLib/myLib.h"

#ifdef WITH_PRINT
#	error WITH_PRINT should not be defined!
#endif

#ifndef HAS_MYLIB2
#	error HAS_MYLIB2 should be defined
#endif

int main()
{
	MyLib::PrintHello();
	return 0;
}
