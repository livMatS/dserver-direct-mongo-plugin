import os

CONFIG_SECRETS_TO_OBFUSCATE = [
    "MONGO_URI",
    "MONGO_DB",
    "MONGO_COLLECTION"
]


class Config(object):
    MONGO_URI = os.environ.get("DSERVER_MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB = os.environ.get("DSERVER_MONGO_DB", "dtool_info")
    MONGO_COLLECTION = os.environ.get("DSERVER_MONGO_COLLECTION", "datasets")

    # This option allows a client to submit direct mongo-syntaxed queries
    # to the underlying mongo database. Externally managed privileges will
    # be enforced as usual by embedding such queries in accompanying logical
    # 'and' clauses, see utils._preprocess_privileges() and
    #  utils._dict_to_mongo_query().
    ALLOW_DIRECT_QUERY = os.environ.get('DSERVER_ALLOW_DIRECT_QUERY',
                                        'True').lower() in ['true', '1', 'y', 'yes', 'on']
    # This option allows a client to submit direct mongo-syntaxed aggregations
    # to the underlying mongo database. As above, externally managed privileges
    # will still apply to the initial '$match' stage of the aggregation
    # pipeline (see utils._dict_to_mongo_aggregation()), but can be easiliy
    # circumvented in subsequent aggregation stages. Further notice that
    # aggregation stages allow write access to the database, thus this option
    # should only be enabled if some privileges are configured a the MongoDB
    # level as well.
    ALLOW_DIRECT_AGGREGATION = os.environ.get('DSERVER_ALLOW_DIRECT_AGGREGATION',
                                              'False').lower() in ['true', '1', 'y', 'yes', 'on']
