"""
This resource is used to interact with the MongoDB database.
"""
import os
import logging
from pymongo import MongoClient

class Cosmos(object):
    DATABASE = None

    @staticmethod
    def initialize():
        mongo_str = os.getenv('MONGO_STR')
        database = os.getenv('DATABASE_NAME')
        logging.info('INIT: Cosmos')
        client = MongoClient(mongo_str)
        Cosmos.DATABASE = client[database]
        logging.info('INIT: Cosmos OK!')

    @staticmethod
    def findAll(collection):
        return Cosmos.DATABASE[collection].find()

    @staticmethod
    def find(collection, query, config=None):
        return Cosmos.DATABASE[collection].find(query, config)

    @staticmethod
    def aggregate(collection, pipeline):
        return Cosmos.DATABASE[collection].aggregate(pipeline)

    @staticmethod
    def findOne(collection, query, config=None):
        if config:
            return Cosmos.DATABASE[collection].find_one(query, config)
        else:
            return Cosmos.DATABASE[collection].find_one(query)

    @staticmethod
    def insertMany(collection, documents):
        return Cosmos.DATABASE[collection].insert_many(documents)

    @staticmethod
    def insertOne(collection, json_creator):
        return Cosmos.DATABASE[collection].insert_one(json_creator)

    @staticmethod
    def deleteOne(collection, filter_criteria,):
        return Cosmos.DATABASE[collection].delete_one(filter_criteria)

    @staticmethod
    def deleteMany(collection, filter_criteria):
        return Cosmos.DATABASE[collection].delete_many(filter_criteria)

    @staticmethod
    def updateOne(collection, filter_criteria, json_updater):
        return Cosmos.DATABASE[collection].update_one(filter_criteria, json_updater)

    @staticmethod
    def updateOneFilters(collection, filter_criteria, json_updater, array_filters=None):
        return Cosmos.DATABASE[collection].update_one(filter_criteria, json_updater, array_filters=array_filters)

    @staticmethod
    def set(collection, id, doc):
        return Cosmos.DATABASE[collection].update_one({'_id': id}, {'$set': doc}, upsert=True)

    @staticmethod
    def doc_exist(collection, id):
        return bool(Cosmos.DATABASE[collection].find_one({'user_id': id}))

    @staticmethod
    def exist(collection, query):
        return bool(Cosmos.DATABASE[collection].find_one(query))

    @staticmethod
    def stream(collection, field, value_field):
        query = Cosmos.DATABASE[collection].find({field: value_field})
        logging.info(query)
        data = [doc for doc in query]
        return data[0] if data else None

    @staticmethod
    def set_field(collection, filter_criteria, doc):
        return Cosmos.DATABASE[collection].update_one(filter_criteria, {'$set': doc}, upsert=True)

    @staticmethod
    def add_to_set(collection, filter_criteria, field, value):
        return Cosmos.DATABASE[collection].update_one(filter_criteria, {'$addToSet': {field: value}})

    @staticmethod
    def remove_from_set(collection, filter_criteria, field, value):
        return Cosmos.DATABASE[collection].update_one(filter_criteria, {'$pull': {field: value}})

    @staticmethod
    def delete_from_set(collection, filter_criteria, field):
        return Cosmos.DATABASE[collection].update_one(filter_criteria, {'$unset': {field: 1}})

    @staticmethod
    def check_database(url_string, database):
        client = MongoClient(url_string)
        Cosmos.DATABASE = client[database]
        return Cosmos.DATABASE
