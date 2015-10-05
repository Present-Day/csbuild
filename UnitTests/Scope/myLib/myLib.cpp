#include "../myLib2/myLib2.h"
#include "myLib.h"

#ifdef WITH_HELLO
#	error WITH_HELLO should not be defined
#endif

#ifdef HAS_MYLIB2
#	error HAS_MYLIB2 should not be defined
#endif

namespace MyLib
{
	void PrintHello()
	{
		MyLib2::Print("HelloWorld");
	}
}
