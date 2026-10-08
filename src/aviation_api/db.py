# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
from flask import current_app
from .errors import APIError


def database():
    pool = current_app.extensions['postgres_pool']
    if pool is None:
        raise APIError(503, 'database_unavailable', 'Database is unavailable.')
    # Psycopg opens the pool once; imports never start connection threads.
    pool.open()
    return pool.connection()
