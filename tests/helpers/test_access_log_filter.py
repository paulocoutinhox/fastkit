import logging

from helpers.access_log_filter import AccessLogFilter


def test_access_logs_keep_the_route_without_its_one_time_credentials():
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:12345", "GET", "/account/social/google/callback?code=one-time-secret&state=browser-state", "1.1", 303), None)

    assert AccessLogFilter().filter(record)
    assert record.getMessage() == '127.0.0.1:12345 - "GET /account/social/google/callback HTTP/1.1" 303'


def test_an_access_log_without_a_query_keeps_its_existing_fields():
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:12345", "POST", "/api/auth/email/confirm", "1.1", 200), None)
    expected = record.getMessage()

    assert AccessLogFilter().filter(record)
    assert record.getMessage() == expected
