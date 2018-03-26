import logging
import queue
import sys
import threading
import traceback
from queue import Queue

from influxdb import InfluxDBClient

PY3 = sys.version_info[0] == 3
WAN_CHUNK, LAN_CHUNK = 1420, 8154

if PY3:
    data, text = bytes, str
else:
    data, text = str, unicode

# skip_list is used to filter additional fields in a log message.
# It contains all attributes listed in
# http://docs.python.org/library/logging.html#logrecord-attributes
# plus exc_text, which is only found in the logging module source,
# and id, which is prohibited by the GELF format.

SKIP_ATTRIBUTES = [
    'args', 'asctime', 'created', 'exc_text', 'filename',
    'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
    'msecs', 'message', 'msg', 'name', 'pathname', 'process',
    'processName', 'stack_info', 'relativeCreated', 'thread', 'threadName'
]

STACKTRACE_ATTRIBUTE = 'exc_info'

DEFAULT_TAGS = {
    'filename': 'source.fileName',
    'funcName': 'source.methodName',
    'levelname': 'level',
    'lineno': 'source.lineNumber',
    'thread': 'threadId',
    'threadName': 'threadName',
    'processName': 'processName'
}

DEFAULT_FIELDS = {
    'message': 'message',
    'msg': 'message'
}


class InfluxHandler(logging.Handler):
    """InfluxDB logging handler

    :param database: The database you want log entries to go into.
    :param measurement: Replace measurement with specified value. If not specified,
        record.name will be passed as `logger` parameter.
    :param lazy_init: Enable lazy initialization. Defaults to False.
    :param include_fields: Include additional fields. Defaults to {}.
    :param include_tags: Include additional tags. Defaults to {}.
    :param extra_fields: Add extra fields if found. Defaults to True.
    :param extra_tags: Add extra tags if found. Defaults to True.
    :param include_stacktrace: Add stacktraces. Defaults to True.
    :param exclude_tags: Exclude list of tag names. Defaults to [].
    :param exclude_fields: Exclude list of field names. Defaults to [].
    :param **influxdb_opts: InfluxDB client options
    """

    def __init__(self,
                 database: str,
                 measurement: str = None,
                 retention_policy: str = None,
                 backpop: bool = True,
                 lazy_init: bool = False,
                 include_tags: dict = {},
                 include_fields: dict = {},
                 exclude_tags: list = [],
                 exclude_fields: list = [],
                 extra_tags: bool = True,
                 extra_fields: bool = True,
                 include_stacktrace: bool = True,
                 **influxdb_opts
                 ):
        super().__init__()

        self._measurement = measurement
        self._client = InfluxDBClient(database=database, **influxdb_opts)
        self._backpop = backpop
        self._retention_policy = retention_policy

        # extend tags to include
        self._include_tags = DEFAULT_TAGS
        self._include_tags.update(include_tags)

        # extend fields to include
        self._include_fields = DEFAULT_FIELDS
        self._include_fields.update(include_fields)

        self._extra_tags = extra_tags
        self._extra_fields = extra_fields
        self._include_stacktrace = include_stacktrace

        self._exclude_tags = exclude_tags
        self._exclude_fields = exclude_fields

        if lazy_init is False:
            if database not in {x['name'] for x in self._client.get_list_database()}:
                self._client.create_database(database)

    def get_client(self):
        return self._client

    def emit(self, record):
        """
        Emit a record.

        Send the record to the Web server as line protocol
        """
        self._client.write_points(self._get_point(record), retention_policy=self._retention_policy)

    def _convert_to_point(self, key, value, fields={}, tags={}):
        if value is None:
            return
        elif isinstance(value, dict):
            for k in value.items():
                if key:
                    self._convert_to_point(key + '.' + k, value[k], fields, tags)
                else:
                    self._convert_to_point(k, value[k], fields, tags)
        elif isinstance(value, list):
            self._convert_to_point(key, ' '.join(value), fields, tags)
        else:
            if key in self._include_tags:
                if key not in self._exclude_tags:
                    tags[self._include_tags.get(key)] = value
            elif key in self._include_fields:
                if key not in self._exclude_fields:
                    fields[self._include_fields.get(key)] = value
            elif key == STACKTRACE_ATTRIBUTE and self._include_stacktrace:
                if isinstance(value, tuple):
                    # exc_info is defined as a tuple
                    tags['thrown.type'] = value[0].__name__
                    fields['thrown.message'] = str(value[1])
                    fields['thrown.stackTrace'] = ''.join(traceback.format_exception(*value))
            elif key in SKIP_ATTRIBUTES:
                return
            else:
                if isinstance(value, int) or isinstance(value, float) or isinstance(value, bool):
                    if self._extra_fields and key not in self._exclude_fields:
                        fields[key] = value
                else:
                    if self._extra_tags and key not in self._exclude_tags:
                        tags[key] = value

    def _get_point(self, record):
        fields = {}
        tags = {}

        for record_name, record_value in record.__dict__.items():
            # ignore methods
            if record_name.startswith('_'):
                continue

            self._convert_to_point(record_name, record_value, fields, tags)

        if self._measurement:
            ret = [{
                "measurement": self._measurement,
                "tags": tags,
                "fields": fields,
                "time": int(record.created * 10 ** 9)  # nanoseconds
            }]
        elif not self._backpop:
            ret = [{
                "measurement": record.name.replace(".", ":") or 'root',
                "tags": tags,
                "fields": fields,
                "time": int(record.created * 10 ** 9)  # nanoseconds
            }]
        else:
            ret = []
            names = record.name.split('.')
            rname = names[0] or 'root'
            ret.append({
                "measurement": rname,
                "tags": tags,
                "fields": fields,
                "time": int(record.created * 10 ** 9)  # nanoseconds
            })
            for sub in names[1:]:
                rname = f"{rname}:{sub}"
                ret.append({
                    "measurement": rname,
                    "tags": tags,
                    "fields": fields,
                    "time": int(record.created * 10 ** 9)  # nanoseconds
                })

        return ret


class AsyncInfluxHandler(InfluxHandler):
    """InfluxDB Asynchronous logging handler

    :param kwargs: Pass these args to the InfluxHandler
    """

    _sentinel = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._queue: Queue = Queue()
        self._thread: threading.Thread = threading.Thread(target=self._monitor)
        self._thread.daemon = True
        self._thread.start()

    def _monitor(self):
        q = self._queue

        has_task_done = hasattr(q, 'task_done')
        while True:
            try:
                record = self._dequeue(True)
                if record is self._sentinel:
                    break

                # write record
                super().emit(record)

                if has_task_done:
                    q.task_done()
            except queue.Empty:
                break

    def _enqueue_sentinel(self):
        self._queue.put_nowait(self._sentinel)

    def _enqueue(self, record):
        self._queue.put_nowait(record)

    def _dequeue(self, block):
        return self._queue.get(block)

    def emit(self, record):
        self._enqueue(record)

    def stop(self):
        self._enqueue_sentinel()
        self._thread.join()
        self._thread = None
