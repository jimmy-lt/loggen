# loggen/__init__.py
# ==================
#
# Copying
# -------
#
# Copyright (c) 2018 loggen authors and contributors.
#
# This file is part of the *loggen* project.
#
# Loggen is a free software project. You can redistribute it and/or
# modify if under the terms of the MIT License.
#
# This software project is distributed *as is*, WITHOUT WARRANTY OF ANY
# KIND; including but not limited to the WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE and NONINFRINGEMENT.
#
# You should have received a copy of the MIT License along with
# loggen. If not, see <http://opensource.org/licenses/MIT>.
#
import os
import sys
import time
import signal
import socket
import logging
import threading

import itertools
import fileinput
import collections

import random

import semver
import argparse

from enum import Enum
from contextlib import suppress
from multiprocessing import Pipe

from logging.handlers import SysLogHandler, SYSLOG_UDP_PORT
from rfc5424logging import Rfc5424SysLogHandler


#: Semantic version information of the program.
VERSION_INFO = semver.VersionInfo(
    major=1,
    minor=2,
    patch=1,
    prerelease=None,
    build=None
)

#: Name of the program.
PROG_NAME = 'loggen'
#: String version of the program.
PROG_VERSION = semver.format_version(*VERSION_INFO)
#: Short description of the program.
PROG_DESCRIPTION = 'A syslog message generator.'


#: Python's logger.
log = logging.getLogger(__name__)


#: Tuple to store socket information.
SockInfo = collections.namedtuple('SockInfo', [
    'address',
    'type',
])


class RawSyslogHandler(SysLogHandler):
    """A log handler class which sends unaltered logging messages to a syslog
    server.


    :param address: Remote server to send the messages to in the form of a
                    (host, port) tuple. If address is specified as a string, a
                    UNIX socket is used.
    :type address: python:tuple or python:str

    :param socktype: The type of socket to use. Most likely one of
                     :data:`socket.SOCK_STREAM` (TCP) or
                     :data:`socket.SOCK_DGRAM` (UDP).
    :type socktype: python:~socket.SocketKind

    """
    def __init__(self, address=('localhost', SYSLOG_UDP_PORT), socktype=None):
        """Constructor for :class:`loggen.RawSyslogHandler`."""
        super().__init__(address=address, socktype=socktype)


    def emit(self, record):
        """Emit a record.


        :param record: Log record to be emitted.
        :type record: python:~logging.LogRecord

        """
        try:
            msg = self.format(record).encode('utf-8')
            if self.unixsocket:
                try:
                    self.socket.send(msg)
                except OSError:
                    self.socket.close()
                    self._connect_unixsocket(self.address)
                    self.socket.send(msg)
            elif self.socktype == socket.SOCK_DGRAM:
                self.socket.sendto(msg, self.address)
            else:
                self.socket.sendall(msg)
        except Exception:
            self.handleError(record)


class SyslogFormat(Enum):
    """Log formats enumeration."""
    RAW = RawSyslogHandler
    RFC3164 = SysLogHandler
    RFC5424 = Rfc5424SysLogHandler


class RFC3164Formatter(logging.Formatter):
    """RFC 3164 syslog message formatter."""
    def __init__(self):
        """Constructor for :class:`loggen.RFC3164Formatter`."""
        super().__init__(fmt='%(asctime)s %(hostname)s %(message)s')


class TaskControl(object):
    """Control a task execution by using different events and conditions."""

    def __init__(self, tasks_active=1, tasks_idle=0):
        """Constructor for :class:`~loggen.TaskControl`."""
        #: Barrier for threads to wait the start signal.
        self.start = threading.Barrier(tasks_active + tasks_idle + 1)
        #: Barrier to notify that a thread has done its task.
        self.done = threading.Barrier(tasks_active + 2)
        #: Event to stop and terminate the task.
        self.shutdown = threading.Event()

        # Register signal handlers.
        signal.signal(signal.SIGINT, self.notify_shutdown)


    def notify_shutdown(self, *args):
        """Send a shutdown event."""
        self.done.abort()
        self.shutdown.set()


def parse_args(args):
    """Parse command line arguments passed to *loggen*.


    :param args: List of arguments passed to the program.
    :type args: python:list


    :returns: A dictionary with the parsed arguments.
    :rtype: python:dict

    """
    parser = argparse.ArgumentParser(prog=PROG_NAME,
                                     description=PROG_DESCRIPTION)

    # Positional arguments.
    parser.add_argument('destination',
                        metavar='DESTINATION',
                        help="remote machine address to send the messages to")

    parser.add_argument('message',
                        nargs='?',
                        metavar='MESSAGE',
                        default='-',
                        help="message to send to the remote host")

    # Program version.
    parser.add_argument('-V', '--version',
                        action='version',
                        version='%(prog)s {version}'.format(
                            version=PROG_VERSION
                        ))

    # Connection settings.
    parser.add_argument('-p', '--port',
                        type=int,
                        default=514,
                        help=(
                            "port to connect to on the remote host"
                            " (default: 514)"
                        ))

    parser.add_argument('-N', '--active',
                        type=int,
                        default=1,
                        help="number of active connections (default: 1)")

    parser.add_argument('-I', '--idle',
                        type=int,
                        default=0,
                        help="number of idle connections (default: 0)")

    # Socket type.
    sock_type = parser.add_mutually_exclusive_group()
    sock_type.add_argument('-t', '--tcp',
                           action='store_const',
                           const=socket.SOCK_STREAM,
                           default=socket.SOCK_DGRAM,
                           dest='sock_type',
                           help="use TCP rather than default UDP")

    sock_type.add_argument('-u', '--udp',
                           action='store_const',
                           const=socket.SOCK_DGRAM,
                           dest='sock_type',
                           help="force use of UDP")

    # Messages.
    syslog = parser.add_mutually_exclusive_group()
    syslog.add_argument('-s', '--rfc5424',
                        action='store_const',
                        const=SyslogFormat.RFC5424,
                        default=SyslogFormat.RFC5424,
                        dest='syslog_format',
                        help="send messages following the RFC5424 syslog format")

    syslog.add_argument('-S', '--rfc3164',
                        action='store_const',
                        const=SyslogFormat.RFC3164,
                        dest='syslog_format',
                        help="send messages following the BSD syslog format")

    syslog.add_argument('-R', '--raw',
                        action='store_const',
                        const=SyslogFormat.RAW,
                        dest='syslog_format',
                        help="send messages as is without any alteration")

    loop = parser.add_mutually_exclusive_group()
    loop.add_argument('-8', '--loop',
                      action='store_const',
                      const=-1,
                      dest='loop',
                      help="send given log messages indefinitely")

    loop.add_argument('-c', '--count',
                      type=int,
                      default=1,
                      dest='loop',
                      help="number of times to send messages")

    parser.add_argument('-w', '--wait',
                        type=int,
                        default=0,
                        help=(
                            "delay in milliseconds to wait between each message"
                        ))

    parser.add_argument('-d', '--delay',
                        action='store_true',
                        help="randomly delay startup of the active tasks")

    parser.add_argument('-f', '--file',
                        action='append',
                        help="read log messages from file or directory")

    parser.add_argument('-r', '--recursive',
                        action='store_true',
                        help="recursively look for files in directories")

    return vars(parser.parse_args(args))


def message_generator(sources, loop=1, recursive=False):
    """Generate a list of messages from given sources.


    :param sources: List of sources to read the messages from. If source is
                    ``'-'``, messages will be read from :attr:`sys.stdin`.
    :type sources: python:str or ~collections.abc.Iterable

    :param loop: Number of time to send messages from the sources. If set to
                 ``-1``, messages are sent indefinitely.
    :type loop: python:int

    :param recursive: Recursively look for files in given directories.
    :type recursive: python:bool


    :returns: A list of messages.
    :rtype: python:~typing.Generator

    """
    def _get_files(name):
        """Generate a list of file paths in given directory.


        :param name: Directory name to walk through.
        :type name: python:str


        :returns: A list of files found into the directory.
        :rtype: python:~typing.Generator

        """
        if recursive:
            return (os.path.join(y[0], x) for y in os.walk(name) for x in y[2])
        return (x.path for x in os.scandir(name) if x.is_file())

    src_str = isinstance(sources, str)
    stdin = sources == '-' if src_str else any(map(lambda x: x == '-', sources))
    if loop not in {0, 1} and stdin:
        log.error("Cannot loop over standard input.")
        raise StopIteration

    if not src_str:
        sources = tuple(itertools.chain(
            (x for x in sources if not os.path.isdir(x)),
            (x for y in sources for x in _get_files(y) if os.path.isdir(y))
        ))

    while loop:
        try:
            # Source can still be a file so let's first try to read it.
            yield from map(lambda x: str(x).strip(), fileinput.input(sources))
        except OSError:
            # Nope! Not a file.
            yield sources.strip()

        if loop > 0:
            loop -= 1


def socket_isinet(destination, port):
    """Test if given destination is an Internet domain address.


    :param destination: Address to the remote host.
    :type destination: python:str

    :param port: Port to connect to on the remote host.
    :type port: python:int


    :returns: Whether given destination is an Internet domain address or not.
    :rtype: python:bool

    """
    try:
        return bool(socket.getaddrinfo(destination, port))
    except socket.gaierror:
        return False


def task_feeder(ctrl, queues, buffer=()):
    """A task to send messages to the active tasks.


    :param ctrl: Task execution control class instance.
    :type ctrl: ~loggen.TaskControl

    :param queues: Communication queues with the active tasks.
    :type queues: python:~collections.abc.Iterable

    :param buffer: List of messages to send to the active tasks.
    :type buffer: python:~collections.abc.Iterable

    """
    excluded = []
    xapp = excluded.append
    receivers = list(queues)

    ctrl.start.wait()
    for msg in buffer:
        if ctrl.shutdown.is_set():
                break

        del excluded[:]
        for i, q in enumerate(receivers):
            try:
                q.send(msg)
            except BrokenPipeError:
                # If we get an error, close the connection and put it to the
                # excluded list.
                q.close()
                xapp(i)

        # Remove stale connections to win some CPU cycles.
        for i in excluded:
            receivers.pop(i)

        # No one is listening, let's get out of here.
        if not receivers:
            break

    # Closing remaining connections.
    for q in receivers:
        with suppress(BrokenPipeError):
            q.send('---EOF---')
        q.close()

    with suppress(threading.BrokenBarrierError):
        ctrl.done.wait()
    ctrl.shutdown.wait()


def task_idle(ctrl, sock_info):
    """A task to create an idle connection to a remote host.


    :param ctrl: Task execution control class instance.
    :type ctrl: ~loggen.TaskControl

    :param sock_info: Information to be passed for the socket creation.
    :type sock_info: ~python:typing.Any

    """
    ctrl.start.wait()
    try:
        syslog = SyslogFormat.RFC3164.value(address=sock_info.address,
                                            socktype=sock_info.type)
    except ConnectionError:
        log.error("Could not connect host at: {}".format(sock_info.address))

    ctrl.shutdown.wait()


def task_active(ctrl, sock_info, queue,
                fmt=SyslogFormat.RFC5424, wait=0, delay=False):
    """A task to send syslog messages to a remote host.


    :param ctrl: Task execution control class instance.
    :type ctrl: ~loggen.TaskControl

    :param sock_info: Information to be passed for the socket creation.
    :type sock_info: ~python:typing.Any

    :param queue: Communication queue with the feeder thread.
    :type queue: python:~multiprocessing.Connection

    :param fmt: Syslog message format to be used.
    :type fmt: ~loggen.SyslogFormat

    :param wait: Time to wait before sending the next message.
    :type wait: python:int

    :param delay: Randomly delay startup of the task.
    :type delay: python:bool

    """
    hostname = socket.gethostname()
    ctrl.start.wait()
    if delay:
        time.sleep(random.randint(0, wait or 1000) / 1000)

    try:
        syslog = fmt.value(address=sock_info.address, socktype=sock_info.type)
        if fmt is SyslogFormat.RFC3164:
            syslog.formatter = RFC3164Formatter()
    except ConnectionError:
        log.error("Could not connect host at: {}".format(sock_info.address))
    except AttributeError:
        log.error("Unknown syslog message format: {!r}".format(fmt))
    else:
        with suppress(OSError):
            for msg in iter(queue.recv, '---EOF---'):
                if ctrl.shutdown.is_set():
                    break

                syslog.emit(logging.makeLogRecord({
                    'hostname': hostname,
                    'msg': msg
                }))

                if wait > 0 and not ctrl.shutdown.is_set():
                    time.sleep(wait / 1000)

    queue.close()
    with suppress(threading.BrokenBarrierError):
        ctrl.done.wait()
    ctrl.shutdown.wait()


def main():
    """Entry point of the *loggen* program."""
    opts = parse_args(sys.argv[1:])
    info = SockInfo(opts['destination'], opts['sock_type'])
    if socket_isinet(opts['destination'], opts['port']):
        info = SockInfo(
            (opts['destination'], opts['port']),
            opts['sock_type'],
        )

    # Creating our tasks.
    ctrl = TaskControl(opts['active'], opts['idle'])
    buff = message_generator(opts['file'] or opts['message'],
                             opts['loop'],
                             opts['recursive'])

    queues = [Pipe(duplex=False) for _ in range(opts['active'])]
    threading.Thread(target=task_feeder,
                     args=(ctrl, (x[1] for x in queues), buff),
                     name='{}-f0'.format(PROG_NAME)).start()

    for i in range(opts['idle']):
        threading.Thread(target=task_idle,
                         args=(ctrl, info),
                         name='{}-i{}'.format(PROG_NAME, i)).start()

    for i in range(opts['active']):
        threading.Thread(target=task_active,
                         args=(
                             ctrl,
                             info,
                             queues[i][0],
                             opts['syslog_format'],
                             opts['wait'],
                             opts['delay'],
                         ),
                         name='{}-a{}'.format(PROG_NAME, i)).start()

    with suppress(threading.BrokenBarrierError):
        ctrl.done.wait()
    ctrl.shutdown.set()
