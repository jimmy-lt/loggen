News
====

1.1.0
-----

Initial release.

Added
#####

- Send log messages from a customizable number of threads.
- A customizable number of idle threads can be created to connect to the remote
  host.
- Support INET, INET6 or Unix domain sockets both in stream or datagram modes.
- Messages are sent following the `RFC 5424`_ format.
- Message source can be the command line, the standard input or a file.
- Message source can be looped upon for infinite transmission.
- A delay (in milliseconds) between each message sent can be defined.


.. _RFC 5424: https://tools.ietf.org/html/rfc5424
