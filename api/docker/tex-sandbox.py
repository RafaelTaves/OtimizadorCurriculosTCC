"""Linux-only launcher. Fail closed if chroot, privilege drop or seccomp fails."""

import ctypes
import errno
import os
import resource
import sys


def enter(root: str) -> None:
    # Load before chroot; the jail contains only Tectonic, fonts and its cache.
    seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("seccomp_init")
    try:
        for syscall in (
            b"socket",
            b"socketpair",
            b"connect",
            b"ptrace",
            b"mount",
            b"unshare",
            b"setns",
            b"fork",
            b"vfork",
            b"io_uring_setup",
        ):
            number = seccomp.seccomp_syscall_resolve_name(syscall)
            if (
                number < 0
                or seccomp.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0
            ):
                raise RuntimeError("seccomp_rule")
        os.chroot(root)
        os.chdir("/work")
        os.setgroups([])
        os.setgid(10002)
        os.setuid(10002)
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (35, 35))
        resource.setrlimit(resource.RLIMIT_FSIZE, (20_000_000, 20_000_000))
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # libseccomp sets no_new_privs when loading an unprivileged filter.
        if seccomp.seccomp_load(context) != 0:
            raise RuntimeError("seccomp_load")
    finally:
        seccomp.seccomp_release(context)


def main() -> None:
    enter(sys.argv[1])
    os.execve(
        "/usr/local/bin/tectonic",
        [
            "tectonic",
            "-X",
            "compile",
            "--untrusted",
            "--only-cached",
            "--reruns",
            "1",
            "--outdir",
            "/work",
            "/work/main.tex",
        ],
        {"HOME": "/home/compiler", "TECTONIC_UNTRUSTED_MODE": "1", "TMPDIR": "/work"},
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("SANDBOX_UNAVAILABLE\n")
        sys.exit(1)
