"""
Service locator for bot handlers.
Services are set during bot startup (bot.py) and accessed by handlers.
"""

_services = {}


def set_services(user_service, scan_service, report_formatter, redis_client):
    _services["user_service"] = user_service
    _services["scan_service"] = scan_service
    _services["report_formatter"] = report_formatter
    _services["redis_client"] = redis_client


def get_user_service():
    return _services["user_service"]


def get_scan_service():
    return _services["scan_service"]


def get_report_formatter():
    return _services["report_formatter"]


def get_redis_client():
    return _services["redis_client"]
