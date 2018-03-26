import logging

import time
from influxdb import InfluxDBClient

from influxdb_logging import InfluxHandler, BufferingInfluxHandler, AsyncInfluxHandler


def test_simple_message():
    InfluxDBClient().drop_database('test_influx_handler')

    influx_handler = InfluxHandler(database='test_influx_handler')
    logging.getLogger().setLevel(logging.DEBUG)

    influx_logger = logging.getLogger('influxdb_logging.tests.simple_message')
    for handler in influx_logger.handlers:
        influx_logger.removeHandler(handler)
    influx_logger.addHandler(influx_handler)

    influx_logger.debug('Debug message')
    influx_logger.info('Info message')
    influx_logger.warning('Warning message')
    influx_logger.error('Error message')

    try:
        raise Exception("This is an exception")
    except:
        influx_logger.exception('Exception message')

    time.sleep(2.5)

    res = influx_handler.get_client().query(
        'SELECT * FROM "influxdb_logging:tests:simple_message"'
    )
    assert len(list(res.get_points())) == 5


def test_buffered_handler():
    InfluxDBClient().drop_database('test_influx_handler')

    influx_handler = BufferingInfluxHandler(database='test_influx_handler', flush_interval=2)
    logging.getLogger().setLevel(logging.DEBUG)

    influx_logger = logging.getLogger('influxdb_logging.tests.buffered_handler')
    for handler in influx_logger.handlers:
        influx_logger.removeHandler(handler)
    influx_logger.addHandler(influx_handler)

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')

    time.sleep(2.5)

    res = influx_handler.get_client().query(
        'SELECT * FROM "influxdb_logging:tests:buffered_handler"'
    )
    assert len(list(res.get_points())) == 32

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')

    time.sleep(2.5)

    res = influx_handler.get_client().query(
        'SELECT * FROM "influxdb_logging:tests:buffered_handler"'
    )
    assert len(list(res.get_points())) == 64

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')

    time.sleep(2.5)

    res = influx_handler.get_client().query(
        'SELECT * FROM "influxdb_logging:tests:buffered_handler"'
    )
    assert len(list(res.get_points())) == 96


def test_async_handler():
    InfluxDBClient().drop_database('udp')
    influx_handler = AsyncInfluxHandler(database='udp', use_udp=True, udp_port=8092)
    logging.getLogger().setLevel(logging.DEBUG)

    influx_logger = logging.getLogger('influxdb_logging.tests.async_handler')
    for handler in influx_logger.handlers:
        influx_logger.removeHandler(handler)
    influx_logger.addHandler(influx_handler)

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')

    time.sleep(2.5)

    res = influx_handler.get_client().query(
        'SELECT * FROM influxdb_logging'
    )
    assert len(list(res.get_points())) == 32

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')

    time.sleep(2.5)

    res = influx_handler.get_client().query(
        'SELECT * FROM "influxdb_logging:tests:async_handler"'
    )
    assert len(list(res.get_points())) == 64

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')

    time.sleep(2.5)
    
    res = influx_handler.get_client().query(
        'SELECT * FROM "influxdb_logging:tests:async_handler"'
    )
    assert len(list(res.get_points())) == 96



