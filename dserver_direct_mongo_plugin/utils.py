"""Utility functions."""

import logging
import yaml

from flask import current_app

from dservercore.date_utils import (
    extract_created_at_as_datetime,
    extract_frozen_at_as_datetime,
)

from .config import Config

logger = logging.getLogger(__name__)


VALID_MONGO_QUERY_KEYS = (
    "free_text",
    "creator_usernames",
    "base_uris",
    "uuids",
    "tags",
)

MONGO_QUERY_LIST_KEYS = (
    "creator_usernames",
    "base_uris",
    "uuids",
    "tags",
)


class NoDatesSafeLoader(yaml.SafeLoader):
    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        """
        Remove implicit resolvers for a particular tag

        Takes care not to modify resolvers in super classes.

        We want to load datetimes as strings, not dates, because we
        go on to serialise as json which doesn't have the advanced types
        of yaml, and leads to incompatibilities down the track.
        """
        if 'yaml_implicit_resolvers' not in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [(tag, regexp)
                                                         for tag, regexp in mappings
                                                         if tag != tag_to_remove]


NoDatesSafeLoader.remove_implicit_resolver('tag:yaml.org,2002:timestamp')


def config_to_dict(username):
    return Config.to_dict()


def _sanitise(query_dict):
    for key in list(query_dict.keys()):
        if key not in VALID_MONGO_QUERY_KEYS:
            del query_dict[key]
    for lk in MONGO_QUERY_LIST_KEYS:
        if lk in query_dict:
            if len(query_dict[lk]) == 0:
                del query_dict[lk]


def _deal_with_possible_or_statment(a_list, key):
    if len(a_list) == 1:
        return {key: a_list[0]}
    else:
        return {"$or": [{key: v} for v in a_list]}


def _deal_with_possible_and_statement(a_list, key):
    if len(a_list) == 1:
        return {key: a_list[0]}
    else:
        return {key: {"$all": a_list}}


def _dict_to_mongo(query_dict):
    _sanitise(query_dict)

    sub_queries = []
    if "free_text" in query_dict:
        sub_queries.append({"$text": {"$search": query_dict["free_text"]}})
    if "creator_usernames" in query_dict:
        sub_queries.append(
            _deal_with_possible_or_statment(
                query_dict["creator_usernames"], "creator_username"
            )
        )
    if "base_uris" in query_dict:
        sub_queries.append(
            _deal_with_possible_or_statment(query_dict["base_uris"], "base_uri")  # NOQA
        )
    if "uuids" in query_dict:
        sub_queries.append(_deal_with_possible_or_statment(query_dict["uuids"], "uuid"))  # NOQA
    if "tags" in query_dict:
        sub_queries.append(
            _deal_with_possible_and_statement(query_dict["tags"], "tags")
        )

    if len(sub_queries) == 0:
        return {}
    elif len(sub_queries) == 1:
        return sub_queries[0]
    else:
        return {"$and": [q for q in sub_queries]}


def _dict_to_mongo_query(query_dict):
    """Construct mongo query as usual, but allow embedding a raw mongo query.

    Treat query_dict as in search_utils._dict_to_mongo_query, but
    additionally embed raw mongo query if key 'query' exists."""

    if "query" in query_dict and isinstance(query_dict["query"], dict):
        raw_mongo = query_dict["query"]
        del query_dict["query"]
    else:
        raw_mongo = {}

    mongo_query = _dict_to_mongo(query_dict)

    if len(raw_mongo) > 0 and len(mongo_query) == 0:
        mongo_query = raw_mongo
    elif len(raw_mongo) > 0 and len(mongo_query) == 1 and "$and" in mongo_query:
        mongo_query["$and"].append(raw_mongo)
    elif len(raw_mongo) > 0:
        mongo_query = {"$and": [mongo_query, raw_mongo]}

    logger.debug("Constructed mongo query: {}".format(mongo_query))
    return mongo_query


def _dict_to_mongo_aggregation(query_dict):
    """Construct mongo query as usual and prepend to aggregation pipeline."""
    if "aggregation" in query_dict and isinstance(query_dict["aggregation"], list):
        aggregation_tail = query_dict["aggregation"]
        del query_dict["aggregation"]
    else:
        aggregation_tail = []

    # unset any _id field, as type ObjectId usually not serializable
    aggregation_tail.append({'$unset': '_id'})

    match_stage = _dict_to_mongo(query_dict)
    if len(match_stage) > 0:
        aggregation_head = [{'$match': match_stage}]
    else:
        aggregation_head = []

    aggregation = [*aggregation_head, *aggregation_tail]
    current_app.logger.debug("Constructed mongo aggregation: {}".format(aggregation))
    return aggregation


def _register_dataset_descriptive_metadata(collection, dataset_info):
    """Register dataset info in the collection. Try to parse README.

    If the "uuid" and "uri" are the same as another record in
    the mongodb collection a new record is not created, and
    the UUID is returned.

    Returns UUID of dataset otherwise.
    """

    # Make a copy to ensure that the original data strucutre does not
    # get mangled by the datetime replacements.
    dataset_info = dataset_info.copy()

    frozen_at = extract_frozen_at_as_datetime(dataset_info)
    created_at = extract_created_at_as_datetime(dataset_info)

    dataset_info["frozen_at"] = frozen_at
    dataset_info["created_at"] = created_at

    # try to parse content of README as yaml to make searchable
    try:
        readme_info = yaml.load(
            dataset_info["readme"],
            Loader=NoDatesSafeLoader
        )
    except Exception as exc:
        current_app.logger.warning("Failed to parse content of readme as YAML for dataset %s:", dataset_info["uri"])
        current_app.logger.warning(exc)
        readme_info = {}

    dataset_info["readme"] = readme_info

    query = {"uuid": dataset_info["uuid"], "uri": dataset_info["uri"]}

    # If a record with the same UUID and URI exists return the uuid
    # without adding a duplicate record.
    exists = collection.find_one(query)

    if exists is None:
        collection.insert_one(dataset_info)
    else:
        collection.find_one_and_replace(query, dataset_info)

    # The MongoDB client dynamically updates the dataset_info dict
    # with and '_id' key. Remove it.
    if "_id" in dataset_info:
        del dataset_info["_id"]

    return dataset_info["uuid"]
