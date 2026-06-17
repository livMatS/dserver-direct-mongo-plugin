"""Reusable fixtures"""

import random
import string

import pytest

JWT_PUBLIC_KEY = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC8LrEp0Q6l1WPsY32uOPqEjaisQScnzO/XvlhQTzj5w+hFObjiNgIaHRceYh3hZZwsRsHIkCxOY0JgUPeFP9IVXso0VptIjCPRF5yrV/+dF1rtl4eyYj/XOBvSDzbQQwqdjhHffw0TXW0f/yjGGJCYM+tw/9dmj9VilAMNTx1H76uPKUo4M3vLBQLo2tj7z1jlh4Jlw5hKBRcWQWbpWP95p71Db6gSpqReDYbx57BW19APMVketUYsXfXTztM/HWz35J9HDya3ID0Dl+pE22Wo8SZo2+ULKu/4OYVcD8DjF15WwXrcuFDypX132j+LUWOVWxCs5hdMybSDwF3ZhVBH ec2-user@ip-172-31-41-191.eu-west-1.compute.internal"  # NOQA


def random_string(
    size=9,
    prefix="test_",
    chars=string.ascii_uppercase + string.ascii_lowercase + string.digits
):
    return prefix + ''.join(random.choice(chars) for _ in range(size))


@pytest.fixture
def snowwhite_token():
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTYyMTEwMDgzMywianRpIjoiNmE3Yjk5NDYtNzU5My00OGNmLTg2NmUtMWJjZGIzNjYxNTVjIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6InNub3ctd2hpdGUiLCJuYmYiOjE2MjExMDA4MzN9.gXdQpGnHDdOHTMG5OKJwNe8JoJU7JSGYooU5d8AxA_Vs8StKBBRKZJ6C6zS8SovIgcDEYGP12V25ZOF_fa42GuQErKqfwJ_RTLB8nHvfEJule9dl_4z-8-5dZigm3ieiYPpX8MktHq4FQ5vdQ36igWyTO5sK4X4GSvZjG6BRphM52Rb9J2aclO1lxuD_HV_c_rtIXI-SLxH3O6LLts8RdjqLJZBNhAPD4qjAbg_IDi8B0rh_I0R42Ou6J_Sj2s5sL97FEY5Jile0MSvBH7OGmXjlcvYneFpPLnfLwhsYUrzqYB-fdhH9AZVBwzs3jT4HGeL0bO0aBJ9sJ8YRU7sjTg"  # NOQA


@pytest.fixture
def tmp_app_with_users(request):
    """Provide app with users"""
    from flask import current_app
    from dservercore import create_app, sql_db
    from dservercore.utils import (
        register_users,
        register_base_uri,
        register_permissions,
    )

    tmp_mongo_db_name = random_string()

    config = {
        "API_TITLE": 'dserver API',
        "API_VERSION": 'v1',
        "OPENAPI_VERSION": '3.0.2',
        "SECRET_KEY": "secret",
        "FLASK_ENV": "development",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "RETRIEVE_MONGO_URI": "mongodb://localhost:27017/",
        "RETRIEVE_MONGO_DB": tmp_mongo_db_name,
        "RETRIEVE_MONGO_COLLECTION": "datasets",
        "SEARCH_MONGO_URI": "mongodb://localhost:27017/",
        "SEARCH_MONGO_DB": tmp_mongo_db_name,
        "SEARCH_MONGO_COLLECTION": "datasets",
        "MONGO_URI": "mongodb://localhost:27017/",
        "MONGO_DB": tmp_mongo_db_name,
        "MONGO_COLLECTION": "metadata",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_ALGORITHM": "RS256",
        "JWT_PUBLIC_KEY": JWT_PUBLIC_KEY,
        "JWT_TOKEN_LOCATION": "headers",
        "JWT_HEADER_NAME": "Authorization",
        "JWT_HEADER_TYPE": "Bearer",
    }

    app = create_app(config)

    # Ensure the sql database has been put into the context.
    app.app_context().push()

    # Populate the database.
    sql_db.Model.metadata.create_all(sql_db.engine)

    # Register some users.
    register_users([
        dict(username="snow-white", is_admin=True),
        dict(username="grumpy"),
        dict(username="sleepy"),
    ])

    base_uri = "s3://snow-white"
    register_base_uri(base_uri)

    permissions = {
        "users_with_search_permissions": ["grumpy", "sleepy"],
        "users_with_register_permissions": ["grumpy"]
    }
    register_permissions(base_uri, permissions)

    @request.addfinalizer
    def teardown():
        current_app.retrieve.client.drop_database(tmp_mongo_db_name)
        current_app.search.client.drop_database(tmp_mongo_db_name)
        sql_db.session.remove()

    return app.test_client()


@pytest.fixture
def tmp_app_with_data(request):
    """Provide app with users"""
    from flask import current_app
    from dservercore import create_app, sql_db
    from dservercore.utils import (
        register_users,
        register_base_uri,
        register_dataset,
        register_permissions,
    )

    tmp_mongo_db_name = random_string()

    config = {
        "API_TITLE": 'dserver API',
        "API_VERSION": 'v1',
        "OPENAPI_VERSION": '3.0.2',
        "SECRET_KEY": "secret",
        "FLASK_ENV": "development",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "RETRIEVE_MONGO_URI": "mongodb://localhost:27017/",
        "RETRIEVE_MONGO_DB": tmp_mongo_db_name,
        "RETRIEVE_MONGO_COLLECTION": "datasets",
        "SEARCH_MONGO_URI": "mongodb://localhost:27017/",
        "SEARCH_MONGO_DB": tmp_mongo_db_name,
        "SEARCH_MONGO_COLLECTION": "datasets",
        "MONGO_URI": "mongodb://localhost:27017/",
        "MONGO_DB": tmp_mongo_db_name,
        "MONGO_COLLECTION": "metadata",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_ALGORITHM": "RS256",
        "JWT_PUBLIC_KEY": JWT_PUBLIC_KEY,
        "JWT_TOKEN_LOCATION": "headers",
        "JWT_HEADER_NAME": "Authorization",
        "JWT_HEADER_TYPE": "Bearer",
    }

    app = create_app(config)

    # Ensure the sql database has been put into the context.
    app.app_context().push()

    # Populate the database.
    sql_db.Model.metadata.create_all(sql_db.engine)

    # Register some users.
    register_users([
        dict(username="snow-white", is_admin=True),
        dict(username="grumpy"),
        dict(username="sleepy"),
    ])

    username = "grumpy"

    # Add base URIs and update permissions
    for base_uri in ["s3://snow-white", "s3://mr-men"]:
        register_base_uri(base_uri)
        permissions = {
            "users_with_search_permissions": [username],
            "users_with_register_permissions": [username]
        }
        register_permissions(base_uri, permissions)

    # Add some data to the database.
    for base_uri in ["s3://snow-white", "s3://mr-men"]:
        uuid = "af6727bf-29c7-43dd-b42f-a5d7ede28337"
        uri = "{}/{}".format(base_uri, uuid)
        dataset_info = {
            "base_uri": base_uri,
            "type": "dataset",
            "uuid": uuid,
            "uri": uri,
            "name": "bad-apples",
            "readme": '"descripton": "apples from queen"',
            "manifest": {
                "dtoolcore_version": "3.7.0",
                "hash_function": "md5sum_hexdigest",
                "items": {
                    "e4cc3a7dc281c3d89ed4553293c4b4b110dc9bf3": {
                        "hash": "d89117c9da2cc34586e183017cb14851",
                        "relpath": "U00096.3.rev.1.bt2",
                        "size_in_bytes": 5741810,
                        "utc_timestamp": 1536832115.0
                    }
                }
            },
            "creator_username": "queen",
            "frozen_at": 1536238185.881941,
            "annotations": {"type": "fruit"},
            "tags": ["evil", "fruit"],
        }
        register_dataset(dataset_info)

    base_uri = "s3://snow-white"
    uuid = "a2218059-5bd0-4690-b090-062faf08e046"
    uri = "{}/{}".format(base_uri, uuid)
    dataset_info = {
        "base_uri": base_uri,
        "type": "dataset",
        "uuid": uuid,
        "uri": uri,
        "name": "oranges",
        "readme": '"descripton": "oranges from queen"',
        "manifest": {
            "dtoolcore_version": "3.7.0",
            "hash_function": "md5sum_hexdigest",
            "items": {}
        },
        "creator_username": "queen",
        "frozen_at": 1536238185.881941,
        "annotations": {"type": "fruit", "only_here": "crazystuff"},
        "tags": ["good", "fruit"],
    }
    register_dataset(dataset_info)

    @request.addfinalizer
    def teardown():
        current_app.retrieve.client.drop_database(tmp_mongo_db_name)
        current_app.search.client.drop_database(tmp_mongo_db_name)
        sql_db.session.remove()

    return app.test_client()


@pytest.fixture
def tmp_app_with_data_and_relaxed_security(request, tmp_app_with_data):
    from dserver_direct_mongo_plugin.config import Config
    Config.ALLOW_DIRECT_QUERY = True
    Config.ALLOW_DIRECT_AGGREGATION = True
    return tmp_app_with_data
