from marshmallow import Schema
from marshmallow.fields import List, Dict, String, UUID


class QueryDatasetSchema(Schema):
    creator_usernames = List(String)
    base_uris = List(String)
    uuids = List(UUID)
    tags = List(String)
    aggregation = List(Dict)
    query = Dict()
