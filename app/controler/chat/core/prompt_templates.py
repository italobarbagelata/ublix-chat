from typing import ClassVar
from langchain.prompts import PromptTemplate
import datetime
import pytz

# TODO: pedirle a ivan un prompt default
DEFAULT_PROMPT = f"Hola, soy un asistente virtual. ¿En qué puedo ayudarte? {{information}}"

# Zona horaria para Chile (Santiago)
TIMEZONE = pytz.timezone('America/Santiago')

# ===================================
INIT_TO_USE_TOOL = """Once you got the correct Query, ALWAYS pass this query to the correct TOOL and execute or run the tool. 
You have access to the following tools:
    mongodb_query_executor: Execute a MongoDB query against the collection and get back the result..
                            If the query is not correct, an error message will be returned.
                            If an error is returned, rewrite the query, check the query, and try again until to get a correct result."""


COLLECTION_SCHEMA = """You have access to the following Collection Schema Description. Pay attention to use it as Context. DO NOT ADD ANY OTHER CONTEXT, ONLY USE THE COLLECTION SCHEMA SHARED:"""


MONGODB_FUNCTIONS_SUFFIX = """I should look at the collections schema description to see what I can query based on the input question.
    In addition, I need to use query operators and/or projection operators
"""


QUERY_SELECTORS_OPERATORS = """
    Do not create a query aggregation pipeline, just create a query using query selectors and/or projection operators.
    To create a query, you need to use some Query Selectors listed below:
        Comparison:
            $eq, $gt, $gte, $in, $lt, $lte, $ne, $nin
        Logical:
            $and, $not, $nor, $or
        Element:
            $exists, $type
        Evaluation:
            $expr, $jsonSchema, $mod, $regex, $text, $where
        Array:
            $all, $elemMatch, $meta, $slice
    
    You need to be smart to combine and ALWAYS CREATE A QUERY using Query Selectors and/or Projection Operators."""


FEW_SHOT_QUERY = """
    You need to follow the next Response Example Formats, which is between ### and is using Query Selectors for better query:
    This is a query to use into find method of mongoDB Compass in the following format `###query###` or `query`, where query is a JSON format as follows:
    
    --- INIT EXAMPLE ---
    example 1: ###{{ "name":{{ "$eq": "Alice Smith"}}}}###
    example 2: ###{{ "age": {{ "$gt": 20 }}}}###
    example 3: ###{{ "$and": [{{ "age": {{ "$gt": 20 }}}}, {{ "age": {{ "$lt": 30 }}}}]}}###
    example 4: ###{{ "$and": [{{ "name": "Declan Ward" }}, {{ "age": {{ "$gt": 23 }} }}]}}###
    --- END EXAMPLE ---"""


COLLECTION_SCHEMA_DESCRIPTION = """
    You are an agent designed to interact with a MongoDB Compass Database.
    So you are an expert building queries and use it into method FIND. (Do not create query aggregation pipelines)
    Given an input question, then create a syntactically correct MongoDB query object then use it into a tool shared, to execute the query.
    If you get an error while executing a query, rewrite the query and try again.
    
    Pay attention and use this collection schema description: 
"""


FIND_METHOD_CONTEXT = """
    You are an expert in mongoDB CRUD.
    In this case, only you have access to Read Operation of CRUD, I mean only use FIND method.
    This is how you can use FIND method:
        db.collection.find( <query>, <projection>)
        where parameters mean:
            <query>: Specifies selection filter using query operators. 
                    To return all documents in a collection, omit this parameter or pass an empty document ({}).
            <projection>: Specifies the fields to return in the documents that match the query filter. 
                          To return all 5 fields in the matching documents, omit this parameter.
"""

# ===================================

def get_date_range() -> list:
    """
    Generate a list of dates from today to 14 days ahead (inclusive)
    Returns:
        list: List of dates as strings in YYYY-MM-DD format
    """
    today = datetime.datetime.now(TIMEZONE).date()
    date_range = [(today + datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(15)]
    return date_range
