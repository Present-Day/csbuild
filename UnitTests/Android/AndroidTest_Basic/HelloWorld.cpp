//Make sure both c and c++ includes are working correctly
#include "stdio.h"
#include <string>

//int main()
//{
//	puts(std::string("Hello, world!").c_str());
//}
#ifdef __ANDROID__
#include <android/log.h>
#include <android_native_app_glue.h>
#define LOGI(...) ((void)__android_log_print(ANDROID_LOG_INFO, "NativeActivitySimpleExample", __VA_ARGS__))
#else
#define LOGI(...) printf(__VA_ARGS__)
#endif
 
void android_main(struct android_app* state)
{
	LOGI(std::string("Hello, World, I'm on Android!").c_str());
}

int main()
{
	LOGI(std::string("Hello, World, I'm on a PC!").c_str());
}