"""Listen on IPv4 and IPv6, including Railway's private network."""

import os
import socket

import uvicorn


def main() -> None:
    with socket.create_server(
        ("::", int(os.getenv("PORT", "8000"))),
        family=socket.AF_INET6,
        dualstack_ipv6=True,
    ) as listener:
        config = uvicorn.Config("app.main:create_app", factory=True)
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
