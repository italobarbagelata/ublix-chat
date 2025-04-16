from bson import ObjectId
import os
import logging
from datetime import datetime
from typing import List
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from .PromptTemplates import (
    PREFIX_DATA_PROVIDED,
    PREFIX_TASK_NEW_FEATURES,
    TEMPLATE_BUILD_NEW_FEATURE_GEN_INFO,
    TEMPLATE_RAW_DATA,
)
from app.resources.constants import DATASOURCES_COLLECTION, STATUS_OK
from app.resources.postgresql import SupabaseDatabase


REQUIERED_COLUMNS_GENERAL_INFO = {
    "title",
    "keywords",
    "description",
    "content",
    "metadata",
}
COLUMNS_PDF_FIXED = {"content"}


class PdfHandler:

    def __init__(
        self,
        chunks: List[str],
        project_id: str,
        file_name: str,
        source_file_type: str,
        datasource_id: ObjectId,
    ) -> None:
        self.chunks = chunks
        self.project_id = project_id
        self.file_name = file_name
        self.source_file_type = source_file_type
        self.datasource_id = datasource_id
        self.parser = StructuredOutputParser.from_response_schemas(
            response_schemas=self._define_response_schema_for_gen_info_file()
        )
        self.llm = ChatOpenAI(
            temperature=0,
            model=os.getenv("MODEL_CHATBOT_SMALL"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.different_cols_gen_info = (
            REQUIERED_COLUMNS_GENERAL_INFO.symmetric_difference(COLUMNS_PDF_FIXED)
        )
        self.db = SupabaseDatabase()

    def _define_response_schema_for_gen_info_file(self):
        """This is the JSON schema for LLM response output for GENERAL INFO"""

        response_schema = [
            ResponseSchema(
                name="title",
                description="A brief title for the context or topic.",
                type="string",
            ),
            ResponseSchema(
                name="keywords",
                description="Relevant keywords that summarize the content or focus.",
                type="List[string]",
            ),
            ResponseSchema(
                name="label",
                description="A label or category that the data belongs to.",
                type="string",
            ),
            ResponseSchema(
                name="description",
                description="A more detailed description or context.",
                type="string",
            ),
            ResponseSchema(
                name="content", description="original Content", type="string"
            ),
            ResponseSchema(
                name="metadata",
                description="Any additional information like datetime",
                type="List[string]",
            ),
        ]
        return response_schema

    def _build_new_features_with_llm_gen_info(self, raw_obj: str) -> dict:
        """This function add new features to raw_obj data for GENERAL_INFO"""
        template = "\n".join(
            [
                PREFIX_DATA_PROVIDED,
                f"""'Category', {", ".join(COLUMNS_PDF_FIXED)}.""",
                PREFIX_TASK_NEW_FEATURES,
                f"""{", ".join(self.different_cols_gen_info)} data.""",
                TEMPLATE_BUILD_NEW_FEATURE_GEN_INFO,
                TEMPLATE_RAW_DATA,
            ]
        )
        prompt = PromptTemplate(
            template=template,
            input_variables=["raw_obj", "date"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )
        chain = prompt | self.llm | self.parser
        result_json = chain.invoke({"raw_obj": raw_obj, "date": str(datetime.now())})
        logging.info(f"Generated JSON: {result_json}")
        return result_json

    def _process_general_info_file(self) -> List[dict]:
        """Process Dataframe raw by raw adding new features for each raw GENERAL INFO"""

        list_chunk = [
            {
                **self._build_new_features_with_llm_gen_info(
                    str({"content": chunk, "category": self.file_name})
                ),
                "question": "",
                "answer": "",
            }
            for chunk in self.chunks
        ]
        return list_chunk

    def process_pdf_texts(self):
        """Process PDF texts and return the results without saving to database"""
        result = self._process_general_info_file()
        return result
