"""cTrader errors and how the bot should treat them.

The server reports a problem in one of four ways (all from the official message definitions):
- ProtoErrorRes (payloadType 50): proxy-level error (e.g. the message is not supported);
- ProtoOAErrorRes (2142): the usual error reply to a request;
- ProtoOAOrderErrorEvent (2132): an order request (new / amend / close) failed;
- ProtoOAExecutionEvent (2126) with executionType ORDER_REJECTED and an errorCode.
Each carries an errorCode string: a name from ProtoErrorCode or ProtoOAErrorCode.
"""

from __future__ import annotations

# errorCode -> (category, retryable). Categories are the broker-neutral codes the adapter raises.
_MAP: dict[str, tuple[str, bool]] = {
    # authorisation
    "CH_CLIENT_AUTH_FAILURE": ("auth_failed", False),
    "CH_CLIENT_NOT_AUTHENTICATED": ("auth_failed", False),
    "CH_ACCESS_TOKEN_INVALID": ("auth_failed", False),
    "OA_AUTH_TOKEN_EXPIRED": ("auth_failed", False),
    "ACCOUNT_NOT_AUTHORIZED": ("auth_failed", False),
    "CH_OA_CLIENT_NOT_FOUND": ("auth_failed", False),
    "CH_CTID_TRADER_ACCOUNT_NOT_FOUND": ("auth_failed", False),
    "RET_NO_SUCH_LOGIN": ("auth_failed", False),
    "RET_ACCOUNT_DISABLED": ("auth_failed", False),
    "CHANNEL_IS_BLOCKED": ("auth_failed", False),
    "ALREADY_LOGGED_IN": ("already_authorized", False),
    "CH_CLIENT_ALREADY_AUTHENTICATED": ("already_authorized", False),
    # temporary
    "REQUEST_FREQUENCY_EXCEEDED": ("rate_limited", True),
    "BLOCKED_PAYLOAD_TYPE": ("rate_limited", True),
    "SERVER_IS_UNDER_MAINTENANCE": ("unavailable", True),
    "CH_SERVER_NOT_REACHABLE": ("unavailable", True),
    "CANT_ROUTE_REQUEST": ("unavailable", True),
    "TIMEOUT_ERROR": ("unavailable", True),
    "CONNECTIONS_LIMIT_EXCEEDED": ("unavailable", True),
    "CONCURRENT_MODIFICATION": ("busy", True),
    "POSITION_LOCKED": ("busy", True),
    "PENDING_EXECUTION": ("busy", True),
    # not found
    "POSITION_NOT_FOUND": ("not_found", False),
    "POSITION_NOT_OPEN": ("not_found", False),
    "ORDER_NOT_FOUND": ("not_found", False),
    "ENTITY_NOT_FOUND": ("not_found", False),
    "SYMBOL_NOT_FOUND": ("not_found", False),
    "UNKNOWN_SYMBOL": ("not_found", False),
    # order refused
    "TRADING_BAD_STOPS": ("stop_too_close", False),
    "PROTECTION_IS_TOO_CLOSE_TO_MARKET": ("stop_too_close", False),
    "TRADING_BAD_VOLUME": ("bad_volume", False),
    "MARKET_CLOSED": ("rejected", False),
    "SYMBOL_HAS_HOLIDAY": ("rejected", False),
    "TRADING_DISABLED": ("rejected", False),
    "TRADING_NOT_ALLOWED": ("rejected", False),
    "NOT_ENOUGH_MONEY": ("rejected", False),
    "NO_QUOTES": ("rejected", True),
    "MAX_EXPOSURE_REACHED": ("rejected", False),
    "TOO_MANY_POSITIONS": ("rejected", False),
    "SHORT_SELLING_NOT_ALLOWED": ("rejected", False),
    "TRADING_BAD_PRICES": ("rejected", False),
    "WORSE_GSL_NOT_ALLOWED": ("rejected", False),
    # request problems
    "INVALID_REQUEST": ("invalid_request", False),
    "UNSUPPORTED_MESSAGE": ("invalid_request", False),
    "INCORRECT_BOUNDARIES": ("invalid_request", False),
    "FRAME_TOO_LONG": ("invalid_request", False),
}


def classify(error_code: str) -> tuple[str, bool]:
    """errorCode -> (category, retryable). Unknown codes are 'rejected', not retryable."""
    return _MAP.get(error_code, ("rejected", False))


class CTraderError(Exception):
    """An error reply from cTrader. code is the server's errorCode (e.g. CH_CLIENT_AUTH_FAILURE)."""

    def __init__(self, code: str, description: str = "", *, retry_after: float | None = None,
                 maintenance_end: float | None = None):
        self.code = code
        self.description = description
        self.category, self.retryable = classify(code)
        self.retry_after = retry_after
        self.maintenance_end = maintenance_end
        super().__init__(f"{code}: {description}" if description else code)


class CTraderDisconnected(ConnectionError):
    """The connection dropped (or never opened) before the reply arrived."""


class CTraderTimeout(TimeoutError):
    """No reply within the time limit. The request may or may not have been carried out."""
