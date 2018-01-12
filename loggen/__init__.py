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
import sys
import time
import signal
import socket
import logging
import threading

import itertools
import fileinput
import collections

import semver
import argparse

from contextlib import suppress

from logging.handlers import SysLogHandler
from rfc5424logging import Rfc5424SysLogHandler


#: Semantic version information of the program.
VERSION_INFO = semver.VersionInfo(
    major=1,
    minor=1,
    patch=0,
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


class TaskControl(object):
    """Control a task execution by using different events and conditions."""

    def __init__(self, tasks_active=1, tasks_idle=0):
        """Constructor for :class:`~loggen.TaskControl`."""
        #: Barrier for threads to wait the start signal.
        self.start = threading.Barrier(tasks_active + tasks_idle)
        #: Barrier to notify that a thread has done its task.
        self.done = threading.Barrier(tasks_active + 1)
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
    parser.add_argument('-8', '--loop',
                        action='store_true',
                        help="send given log messages in loop")

    parser.add_argument('-w', '--wait',
                        type=int,
                        default=0,
                        help=(
                            "delay in milliseconds to wait between each message"
                        ))

    parser.add_argument('-f', '--file',
                        action='append',
                        help="read log messages from file")

    return vars(parser.parse_args(args))


def buffer_generate(sources):
    """Generate a buffer of messages from given sources.


    :param sources: List of sources to read the messages from. If a source is
                    ``'-'``, it is also replaced by :attr:`sys.stdin`.
    :type sources: python:str or ~collections.abc.Iterable


    :returns: A list of messages.
    :rtype: python:tuple

    """
    try:
        return tuple(map(lambda x: str(x).strip(), fileinput.input(sources)))
    except OSError:
        return sources.strip(),


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


def task_idle(ctrl, sock_info):
    """A task to create an idle connection to a remote host.


    :param ctrl: Task execution control class instance.
    :type ctrl: ~loggen.TaskControl

    :param sock_info: Information to be passed for the socket creation.
    :type sock_info: ~python:typing.Any

    """
    ctrl.start.wait()
    try:
        syslog = SysLogHandler(address=sock_info.address,
                               socktype=sock_info.type)
    except ConnectionError:
        log.error("Could not connect host at: {}".format(sock_info.address))

    ctrl.shutdown.wait()


def task_active(ctrl, sock_info, buffer=(), loop=False, delay=0):
    """A task to send syslog messages to a remote host.


    :param ctrl: Task execution control class instance.
    :type ctrl: ~loggen.TaskControl

    :param sock_info: Information to be passed for the socket creation.
    :type sock_info: ~python:typing.Any

    :param buffer: List of messages to send to the host.
    :type buffer: python:~collections.abc.Iterable

    :param loop: Whether the buffer should be sent indefinitely or not.
    :type loop: python:bool

    :param delay: Time to wait before sending the next message.
    :type delay: python:int

    """
    ctrl.start.wait()
    if loop:
        buffer = itertools.cycle(buffer)

    try:
        syslog = Rfc5424SysLogHandler(address=sock_info.address,
                                      socktype=sock_info.type)
    except ConnectionError:
        log.error("Could not connect host at: {}".format(sock_info.address))
        return

    for msg in buffer:
        if ctrl.shutdown.is_set():
            break

        syslog.emit(logging.makeLogRecord({'msg': msg}))
        if delay > 0:
            time.sleep(delay / 1000)

    if not loop:
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
    buff = buffer_generate(opts['file'] or opts['message'])

    for i in range(opts['idle']):
        threading.Thread(target=task_idle,
                         args=(ctrl, info),
                         name='{}-i{}'.format(PROG_NAME, i)).start()

    for i in range(opts['active']):
        threading.Thread(target=task_active,
                         args=(ctrl, info, buff, opts['loop'], opts['wait']),
                         name='{}-a{}'.format(PROG_NAME, i)).start()

    # Time to start the tasks.
    if not opts['loop']:
        with suppress(threading.BrokenBarrierError):
            ctrl.done.wait()
        ctrl.shutdown.set()
