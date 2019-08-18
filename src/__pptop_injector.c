#include <stdio.h>
#include <string.h>
#include <Python.h>

static int __attribute__((used))
  __pptop_start_injection(char *libpath, int pid, int protocol, char* logfile) {
    char cmd[1024];
    int result;
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();
    sprintf(cmd,
        "import sys\nif '%s' not in sys.path: sys.path.insert(0, '%s')\n" \
        "import pptop.injection; pptop.injection.start(%u, %u, '%s')",
        libpath, libpath, pid, protocol, logfile);
    result = PyRun_SimpleString(cmd);
    PyGILState_Release(gstate);
    return result;
}
