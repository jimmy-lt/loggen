News
====

1.2.1
-----

Fixed
#####

- It was impossible to send a message multiple times even if the standard input
  was not used.
- It was not possible to use multiple active threads due to our messages were
  generated.


1.2.0
-----

Added
#####

- Syslog messages can now be sent in 3 formats: `RFC 5424`_, the old `RFC 3164`_
  format or unaltered (as is, raw format).
- It is possible to send a defined count of messages.
- ``loggen`` can recursively look into a folder for files with messages to be
  sent.
- Active tasks startup can be delayed before they start sending log messages.


.. _RFC 3164: https://tools.ietf.org/html/rfc3164


Fixed
#####

- Active tasks are properly synchronized on exit even when an error occurs.


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
