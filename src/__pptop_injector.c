#include <stdio.h>
#include <string.h>
#include <Python.h>

static int __attribute__((used))
  __pptop_start_injection(char *libpath, int pid, char* logfile) {
    char cmd[3000];
    int result;
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();
    sprintf(cmd,
        "import sys; sys.path.insert(0, '%s');" \
        "import pptop.injection; pptop.injection.start(%u,'%s')",
        libpath, pid, logfile);
    result = PyRun_SimpleString(cmd);
    PyGILState_Release(gstate);
    return result;
}
