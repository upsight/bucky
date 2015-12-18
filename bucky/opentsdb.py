# -*- coding: utf-8 -
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
#
# Copyright 2011 Cloudant, Inc.

import six
import sys
import time
import socket
import struct
import logging

import bucky.client as client
import bucky.names as names


if six.PY3:
    xrange = range


log = logging.getLogger(__name__)


class DebugSocket(object):
    def sendall(self, data):
        sys.stdout.write(data)


class Client(client.Client):
    def __init__(self, cfg, pipe):
        super(Client, self).__init__(pipe)
        self.debug = cfg.debug
        self.ip = cfg.opentsdb_ip
        self.port = cfg.opentsdb_port
        self.max_reconnects = cfg.opentsdb_max_reconnects
        self.reconnect_delay = cfg.opentsdb_reconnect_delay
        self.backoff_factor = cfg.opentsdb_backoff_factor
        self.backoff_max = cfg.opentsdb_backoff_max
        self.tags = ' '.join(cfg.opentsdb_tags)
        if self.max_reconnects <= 0:
            self.max_reconnects = sys.maxint
        self.connect()

    def connect(self):
        if self.debug:
            log.debug("Connected the debug socket.")
            self.sock = DebugSocket()
            return
        reconnect_delay = self.reconnect_delay
        for i in xrange(self.max_reconnects):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.sock.connect((self.ip, self.port))
                log.info("Connected to OpenTSDB at %s:%s", self.ip, self.port)
                return
            except socket.error as e:
                if i >= self.max_reconnects:
                    raise
                log.error("Failed to connect to %s:%s: %s", self.ip, self.port, e)
                if reconnect_delay > 0:
                    time.sleep(reconnect_delay)
                    if self.backoff_factor:
                        reconnect_delay *= self.backoff_factor
                        if self.backoff_max:
                            reconnect_delay = min(reconnect_delay, self.backoff_max)
        raise socket.error("Failed to connect to %s:%s after %s attempts", self.ip, self.port, self.max_reconnects)

    def reconnect(self):
        self.close()
        self.connect()

    def close(self):
        try:
            self.sock.close()
        except:
            pass

    def send(self, host, name, value, mtime):
        stat = names.statname(host, name)
        mesg = "put %s %s %s %s\n" % (stat, mtime, value, self.tags)
        for i in xrange(self.max_reconnects):
            try:
                self.sock.sendall(mesg)
                return
            except socket.error as err:
                log.error("Failed to send data to OpenTSDB server: %s", err)
                try:
                    self.reconnect()
                except socket.error as err:
                    log.error("Failed reconnect to OpenTSDB server: %s", err)
        log.error("Dropping message %s", mesg)

