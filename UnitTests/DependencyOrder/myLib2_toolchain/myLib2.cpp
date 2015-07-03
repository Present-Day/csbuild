#include "myLib2.h"
#include "stdio.h"

#ifdef WITH_PRINT
#	error WITH_PRINT should not be defined
#endif

#ifdef HAS_MYLIB2
#	error HAS_MYLIB2 should not be defined
#endif

namespace MyLib2
{
	void Print(const char* const str)
	{
		puts(str);
	}
}
