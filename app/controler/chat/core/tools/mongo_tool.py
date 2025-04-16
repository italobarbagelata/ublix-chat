import logging
import json
from langchain.tools import tool
from pymongo import MongoClient
from app.controler.chat.adapters.mongo_adapter import MongoDBTool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
from app.controler.chat.store.persistence import Persist


@tool(parse_docstring=False)
def mongo_db_tool(query: str,  state: Annotated[dict, InjectedState]) -> str:
    """This tool always use query user message to find results into MongoDB Database

    Args:
        query: str: This is a text query message sent by user
        state: dict: Injected state containing project configuration
    """
    project_id = state["project"].id
    database = Persist()
    mongo_integrations = list(database.get_database_integrations_by_project_id(project_id, "mongodb"))

    mongo_integration = mongo_integrations[0] if mongo_integrations else None
    if not mongo_integration:
        return "No MongoDB Integration found"

    # pylint: disable=E1136
    collection_integration = mongo_integration["db_tables"][0]

    db_name = mongo_integration["db_name"]
    db_url = mongo_integration["db_url"]
    collection_name = collection_integration["table_name"]
    schema_description = collection_integration["collection_description"]

    mongodb_tool = MongoDBTool(
        schema_description=schema_description,
        message=query
    )
    query_result = mongodb_tool.execute_chain()

    query_result = query_result.split("###")[1] if "###" in query_result else query_result
    query_result = json.loads(query_result)

    client = MongoClient(host=db_url)
    database = client[db_name]
    collection = database[collection_name]

    try:
        result = list(collection.find(query_result))
    except TypeError:
        result = "Not Solved, Please try again a Correct Question Input"

    return str(result)
