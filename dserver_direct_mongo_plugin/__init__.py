try:
    from importlib.metadata import version, PackageNotFoundError
except ModuleNotFoundError:
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    # package is not installed
   pass

import pymongo
import dtoolcore.utils as core_utils
import dservercore.utils as server_utils

from flask import (
    abort,
    jsonify,
    request,
    current_app,
)

from dservercore.utils_auth import (
    jwt_required,
    get_jwt_identity,
)

from flask_smorest import Blueprint
from flask_smorest.pagination import PaginationParameters

from pymongo import MongoClient

from dservercore import ExtensionABC, ValidationError

from dservercore import AuthenticationError
from dservercore.sql_models import DatasetSchema

from .config import Config, CONFIG_SECRETS_TO_OBFUSCATE
from .schemas import QueryDatasetSchema
from .utils import (
    _register_dataset_descriptive_metadata,
    _dict_to_mongo_query,
    _dict_to_mongo_aggregation
)


mongo_bp = Blueprint("mongo", __name__, url_prefix="/mongo")


@mongo_bp.route("/query", methods=["POST"])
@mongo_bp.arguments(QueryDatasetSchema(partial=True))
@mongo_bp.response(200, DatasetSchema(many=True))
@mongo_bp.paginate()
@jwt_required()
def query_datasets(
        query: QueryDatasetSchema, pagination_parameters: PaginationParameters
):
    """Query datasets a user has access to."""
    if not Config.ALLOW_DIRECT_QUERY:
        abort(404)
    username = get_jwt_identity()
    current_app.logger.debug("Received query request '{}' from user '{}'.".format(query, username))
    try:
        datasets = query_datasets_by_user(username, query)
    except AuthenticationError:
        abort(401)
    pagination_parameters.item_count = len(datasets)
    return jsonify(
        datasets[pagination_parameters.first_item: pagination_parameters.last_item + 1]
    )


@mongo_bp.route("/aggregate", methods=["POST"])
@mongo_bp.arguments(QueryDatasetSchema(partial=True))
@mongo_bp.response(200, DatasetSchema(many=True))
@mongo_bp.paginate()
@jwt_required()
def aggregate_datasets(
        query: QueryDatasetSchema, pagination_parameters: PaginationParameters
):
    """Aggregate the datasets a user has access to."""
    if not Config.ALLOW_DIRECT_AGGREGATION:
        abort(404)
    username = get_jwt_identity()
    current_app.logger.debug("Received aggregate request '{}' from user '{}'.".format(query, username))
    try:
        datasets = aggregate_datasets_by_user(username, query)
    except AuthenticationError:
        abort(401)
    pagination_parameters.item_count = len(datasets)
    return jsonify(
        datasets[pagination_parameters.first_item: pagination_parameters.last_item + 1]
    )


def query_datasets_by_user(username, query):
    """Query the datasets the user has access to. Allow raw mongo 'query'.

    See dservercore.utils.search_datasets_by_user docstring.

    :param username: username
    :param query: dictionary specifying query
    :returns: List of dicts if user is valid and has access to datasets.
              Empty list if user is valid but has not got access to any
              datasets.
    :raises: AuthenticationError if user is invalid.
    """

    query = server_utils.preprocess_query_base_uris(username, query)
    # If there are no base URIs at this point it means that the user is not
    # allowed to search for anything.
    if len(query["base_uris"]) == 0:
        return []

    mongo_query = _dict_to_mongo_query(query)
    cx = DirectMongoExtension.collection.find(
        mongo_query,
        {
            "_id": False,
            "readme": False,
            "manifest": False,
            "annotations": False,
        }
    )

    datasets = []
    for ds in cx:
        # Convert datetime object to float timestamp.
        for key in ("created_at", "frozen_at"):
            if key in ds:
                datetime_obj = ds[key]
                ds[key] = core_utils.timestamp(datetime_obj)

        datasets.append(ds)
    return datasets


def aggregate_datasets_by_user(username, query):
    """Aggregate the datasets the user has access to.
    Valid keys for the query are: creator_usernames, base_uris, free_text,
    aggregation. If the query dictionary is empty, all datasets that a user has
    access to are returned.
    :param username: username
    :param query: dictionary specifying query
    :returns: List of dicts if user is valid and has access to datasets.
              Empty list if user is valid but has not got access to any
              datasets.
    :raises: AuthenticationError if user is invalid.
    """
    if not Config.ALLOW_DIRECT_AGGREGATION:
        current_app.logger.warning(
            "Received aggregate request '{}' from user '{}', but direct "
            "aggregations are disabled.".format(query, username))
        return []  # silently reject request

    query = server_utils.preprocess_query_base_uris(username, query)

    # If there are no base URIs at this point it means that the user has not
    # got privileges to search for anything.
    if len(query["base_uris"]) == 0:
        return []
    datasets = []

    mongo_aggregation = _dict_to_mongo_aggregation(query)

    cx = DirectMongoExtension.collection.aggregate(mongo_aggregation)
    # Opposed to search_datasets_by_user, here it is the aggregator's
    # responsibility to project out desired fields and remove non-serializable
    # content. The only modification always applied is removing any '_id' field.
    for ds in cx:
        # Convert datetime object to float timestamp.
        for key in ("created_at", "frozen_at"):
            if key in ds:
                datetime_obj = ds[key]
                ds[key] = core_utils.timestamp(datetime_obj)

        datasets.append(ds)

    return datasets


class DirectMongoExtension(ExtensionABC):
    """Extension for making dtool datasets, in particular content of README, searchable with direct mongo queries."""

    # NOTE: Not very neat using class variables here, but the way the plugin
    # system works now, we need to provide the class-external route above some
    # means of accessing the database that's configured within the init_app
    # method here.
    client = None
    collection = None
    db = None

    def init_app(self, app):
        try:
            self._mongo_uri = app.config["MONGO_URI"]
            DirectMongoExtension.client = MongoClient(self._mongo_uri,
                                      uuidRepresentation='standard')
        except KeyError:
            raise(RuntimeError("Please set the MONGO_URI environment variable"))  # NOQA

        try:
            self._mongo_db = app.config["MONGO_DB"]
            DirectMongoExtension.db = self.client[self._mongo_db]
        except KeyError:
            raise(RuntimeError("Please set the MONGO_DB environment variable"))  # NOQA

        try:
            self._mongo_collection = app.config["MONGO_COLLECTION"]
            DirectMongoExtension.collection = self.db[self._mongo_collection]
        except KeyError:
            raise(RuntimeError("Please set the MONGO_COLLECTION environment variable"))  # NOQA

        # Enable free text searching.
        # According to the Mongo documentation indexes will not be regenerated
        # if they already exist so it should be safe to run the command below
        # every time the class is instanciated.
        # https://www.mongodb.com/docs/manual/reference/method/db.collection.createIndex/#recreating-an-existing-index  # NOQA
        # self.collection.create_index([("$**", pymongo.TEXT)])

    def register_dataset(self, dataset_info):
        try:
            return _register_dataset_descriptive_metadata(self.collection, dataset_info)
        except pymongo.errors.DocumentTooLarge as e:
            raise (ValidationError("Dataset has too much metadata: {}".format(e)))

    def get_config(self):
        """Return initial Config object, available app-instance independent."""
        return Config

    def get_config_secrets_to_obfuscate(self):
        """Return config secrets never to be exposed clear text."""
        return CONFIG_SECRETS_TO_OBFUSCATE

    def get_blueprint(self):
        return mongo_bp