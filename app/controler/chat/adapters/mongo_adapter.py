import os

import app.controler.chat.core.prompt_templates as pt

from langchain_openai import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from langchain_core.messages import AIMessage
from app.resources.constants import OPENAI_API_KEY

class MongoDBTool:

    def __init__(
        self,
        schema_description: str,
        message: str
    ) -> None:
        self.__schema_description = schema_description
        self.__message = message
        self.__llm = ChatOpenAI(api_key=OPENAI_API_KEY,
                                temperature=0.0,
                                model="gpt-4-0125-preview")
        self.__chain = self._create_dynamic_chain()

    def _create_dynamic_chain(self) -> str:
        """Create a Dynamic Prompt"""
        MONGODB_SYSTEM_PROMPT = "\n\n".join(
            [
                pt.COLLECTION_SCHEMA,
                "{schema_description}",
                pt.QUERY_SELECTORS_OPERATORS,
                pt.FEW_SHOT_QUERY,
                pt.INIT_TO_USE_TOOL
            ]
        )
        messages = [
            SystemMessagePromptTemplate.from_template(MONGODB_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template("Question: {input}"),
            AIMessage(pt.MONGODB_FUNCTIONS_SUFFIX)
        ]
        prompt = ChatPromptTemplate.from_messages(messages=messages)
        chain = prompt | self.__llm

        return chain

    def execute_chain(self):
        """Execute the chain built previously"""
        result = self.__chain.invoke(
            {
                "input": self.__message,
                "schema_description": self.__schema_description
            }
        )
        return result.content
