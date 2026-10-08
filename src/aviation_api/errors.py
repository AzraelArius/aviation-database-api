# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
import psycopg
from flask import current_app, jsonify
from psycopg_pool import PoolTimeout
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def api_error(error):
        return jsonify(error={'code': error.code, 'message': error.message}), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = jsonify(error={'code': error.name.lower().replace(' ', '_'),
                                  'message': error.description})
        response.status_code = error.code
        for key, value in error.get_headers():
            if key.lower() not in ('content-type', 'content-length'):
                response.headers.add(key, value)
        return response

    @app.errorhandler(psycopg.Error)
    @app.errorhandler(PoolTimeout)
    def db_error(error):
        current_app.logger.warning('Database request failed (%s, SQLSTATE=%s)',
                           type(error).__name__, getattr(error, 'sqlstate', None))
        if isinstance(error, (psycopg.IntegrityError, psycopg.errors.SerializationFailure,
                              psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable)):
            return api_error(APIError(409, 'database_conflict', 'Request conflicts with current database state; retry after checking availability.'))
        return api_error(APIError(503, 'database_unavailable', 'Database is unavailable; try again later.'))

    @app.errorhandler(Exception)
    def unexpected_error(error):
        current_app.logger.error('Unexpected request failure (%s)', type(error).__name__)
        return api_error(APIError(500, 'internal_error', 'Request could not be completed.'))
