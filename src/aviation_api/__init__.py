# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
import atexit
import os
from decimal import Decimal

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from psycopg.rows import namedtuple_row
from psycopg_pool import ConnectionPool
from .errors import register_error_handlers
from .routes import routes


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get('DATABASE_URL'),
        DB_POOL_MIN_SIZE=1, DB_POOL_MAX_SIZE=10, DB_POOL_TIMEOUT=5,
        DB_OPTIONS='-c timezone=UTC -c lock_timeout=5000 -c statement_timeout=10000',
        RATELIMIT_STORAGE_URI=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
        MAX_CONTENT_LENGTH=64 * 1024,
        TICKET_PRICE_FIRST='300.00', TICKET_PRICE_ECONOMY='150.00',
    )
    app.config.from_prefixed_env()
    if config:
        app.config.update(config)
    app.logger.setLevel(app.config.get('LOG_LEVEL', 'INFO'))
    for key in ('TICKET_PRICE_FIRST', 'TICKET_PRICE_ECONOMY'):
        value = Decimal(str(app.config[key]))
        if not value.is_finite() or not 0 <= value <= Decimal('99999.99') or value != value.quantize(Decimal('0.01')):
            raise ValueError(f'{key} must be a nonnegative price with at most two decimal places.')
        app.config[key] = value
    pool = None
    if app.config['DATABASE_URL']:
        pool = ConnectionPool(
            conninfo=app.config['DATABASE_URL'], open=False,
            min_size=app.config['DB_POOL_MIN_SIZE'], max_size=app.config['DB_POOL_MAX_SIZE'],
            timeout=app.config['DB_POOL_TIMEOUT'], check=ConnectionPool.check_connection,
            kwargs={'autocommit': False, 'row_factory': namedtuple_row,
                    'options': app.config['DB_OPTIONS']},
        )
        atexit.register(pool.close)
    app.extensions['postgres_pool'] = pool
    Limiter(get_remote_address, app=app, default_limits=['200 per day', '50 per hour'],
            storage_uri=app.config['RATELIMIT_STORAGE_URI'])

    register_error_handlers(app)
    app.register_blueprint(routes)
    return app
