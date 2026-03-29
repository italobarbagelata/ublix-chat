import pandas as pd
from bson import ObjectId
import os
import logging
from datetime import datetime
from typing import List
from app.database import SyncDatabase
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from .PromptTemplates import (
    PREFIX_DATA_PROVIDED,
    PREFIX_TASK_NEW_FEATURES,
    PREFIX_TASK_FILL_CELLS,
    TEMPLATE_BUILD_NEW_FEATURES_FAQ,
    TEMPLATE_BUILD_NEW_FEATURE_GEN_INFO,
    TEMPLATE_FILL_CELLS,
    TEMPLATE_RAW_DATA
)
from .constants import (
    STATUS_INTERNAL_SERVER_ERROR, 
    STATUS_OK,
    DATASOURCES_COLLECTION
)

# Database configuration
_db = SyncDatabase()

REQUIERED_COLUMNS_FAQ = {'title', 'keywords', 'label', 'description', 'question', 'answer', 'metadata'}
REQUIERED_COLUMNS_GENERAL_INFO = {'title', 'keywords', 'description', 'content', 'metadata'}

class TextHandler:
    
    def __init__(self,
                df: pd.DataFrame,
                project_id: str,
                file_name: str,
                source_file_type: str,
                datasource_id: str) -> None:
        self.df = df
        self.project_id = project_id
        self.file_name = file_name
        self.source_file_type = source_file_type
        self.datasource_id = datasource_id
        self.parser = StructuredOutputParser.from_response_schemas(response_schemas= self._select_response_schema())
        self.llm = ChatOpenAI(temperature=0, 
                              model=os.getenv("MODEL_CHATBOT_SMALL"),
                              api_key=os.getenv("OPENAI_API_KEY"))
        self.current_cols = {col.strip().lower() for col in self.df.columns}
        self.different_cols_faq = REQUIERED_COLUMNS_FAQ.symmetric_difference(self.current_cols)
        self.different_cols_gen_info = REQUIERED_COLUMNS_GENERAL_INFO.symmetric_difference(self.current_cols)
    
    
    def _select_response_schema(self) -> list:
        if self.source_file_type == "faq":
            return self._define_response_schema_for_faq_file()
        elif self.source_file_type == 'general_info':
            return self._define_response_schema_for_gen_info_file()
        else:
            return []
        
    
    def _define_response_schema_for_faq_file(self):
        """This is the JSON schema for LLM response output for FAQ"""
        
        response_schema = [
            ResponseSchema( name="title",
                            description="A brief title for the context or topic.",
                            type="string"),
            ResponseSchema( name="keywords",
                            description="Relevant keywords that summarize the content or focus.",
                            type="List[string]"),
            ResponseSchema( name="label",
                            description="A label or category that the data belongs to.",
                            type="string"),
            ResponseSchema( name="description",
                            description="A more detailed description or context.",
                            type="string"),
            ResponseSchema( name="question",
                            description="Question",
                            type="string"),
            ResponseSchema( name="answer",
                            description="Answer",
                            type="string"),
            ResponseSchema( name="metadata",
                            description="Any additional information like datetime.",
                            type="List[string]")
        ]
        return response_schema
    
    
    def _define_response_schema_for_gen_info_file(self):
        """This is the JSON schema for LLM response output for GENERAL INFO"""
        
        response_schema = [
            ResponseSchema( name="title",
                            description="A brief title for the context or topic.",
                            type="string"),
            ResponseSchema( name="keywords",
                            description="Relevant keywords that summarize the content or focus.",
                            type="List[string]"),
            ResponseSchema( name="label",
                            description="A label or category that the data belongs to.",
                            type="string"),
            ResponseSchema( name="description",
                            description="A more detailed description or context.",
                            type="string"),
            ResponseSchema( name="content",
                            description="original Content",
                            type="string"),
            ResponseSchema( name="metadata",
                            description="Any additional information like datetime.",
                            type="List[string]")
        ]
        return response_schema
    
    
    def _build_new_features_with_llm_faq(self, 
                                        raw_obj: str) -> dict:
        """This function add new features to raw_obj data for FAQ"""
        template = "\n".join(
                    [   
                        PREFIX_DATA_PROVIDED,
                        f"""'Category', {", ".join(self.current_cols)}.""",
                        PREFIX_TASK_NEW_FEATURES,
                        f"""{", ".join(self.different_cols_faq)} data.""",
                        TEMPLATE_BUILD_NEW_FEATURES_FAQ,
                        TEMPLATE_RAW_DATA
                    ]
                )
        prompt = PromptTemplate(
            template= template,
            input_variables=["raw_obj", "date"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )
        chain= prompt | self.llm | self.parser
        result_json = chain.invoke({"raw_obj": raw_obj,
                                    "date":str(datetime.now())})
        return result_json
    
    
    def _build_new_features_with_llm_gen_info(self, 
                                            raw_obj: str) -> dict:
        """This function add new features to raw_obj data for GENERAL_INFO"""
        template = "\n".join(
                    [   
                        PREFIX_DATA_PROVIDED,
                        f"""'Category', {", ".join(self.current_cols)}.""",
                        PREFIX_TASK_NEW_FEATURES,
                        f"""{", ".join(self.different_cols_gen_info)} data.""",
                        TEMPLATE_BUILD_NEW_FEATURE_GEN_INFO,
                        TEMPLATE_RAW_DATA
                    ]
                )
        prompt = PromptTemplate(
            template= template,
            input_variables=["raw_obj", "date"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )
        chain= prompt | self.llm | self.parser
        result_json = chain.invoke({"raw_obj": raw_obj,
                                    "date":str(datetime.now())})
        return result_json
    
    
    def _fill_empty_cells_with_llm(self, 
                                   raw_obj: str) -> dict:
        """Use LLM to fill empty cells dynamicly"""
        template = "\n".join(
                    [   
                        PREFIX_DATA_PROVIDED,
                        f"""'Category', {", ".join(self.current_cols)}.""",
                        PREFIX_TASK_FILL_CELLS,
                        f"""'Category', {", ".join(self.current_cols)} data""",
                        TEMPLATE_FILL_CELLS,
                        TEMPLATE_RAW_DATA
                    ]
                )
        prompt = PromptTemplate(
            template= template,
            input_variables=["raw_obj", "date"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )
        chain= prompt | self.llm | self.parser
        result_json = chain.invoke({"raw_obj": raw_obj,
                                    "date":str(datetime.now())})
        return result_json
    
    
    def _rebuild_empty_df(self, 
                        df_empty_raws: pd.DataFrame) -> pd.DataFrame:
        """Iterate over all raws and Fill empty cells with LLMs answer"""
        
        list_dict = list()
        for index in range(len(df_empty_raws)):
            raw_obj= df_empty_raws.iloc[index].to_dict()
            raw_obj["category"]= self.file_name
            raw_obj = str(raw_obj)
            raw_extra_features = self._fill_empty_cells_with_llm(raw_obj)
            list_dict.append(raw_extra_features)

        return pd.DataFrame(list_dict, 
                            index= df_empty_raws.index)
    
    
    def _save_data_into_mongodb(self, 
                              result: List[dict]):
        """Save data into database"""
        logging.info("Saving Data into database....")
        
        # Prepare the data according to the table structure
        datasource_data = {
            "project_id": self.project_id,
            "name": self.file_name,
            "type": self.source_file_type,
            "status": "active",
            "configuration": {
                "datasource_id": self.datasource_id,
                "source_file_type": self.source_file_type,
                "file_name": self.file_name
            },
            "metadata": {
                "documents": [
                    {
                        "title": doc.get("title", ""),
                        "keywords": doc.get("keywords", ""),
                        "label": doc.get("label", ""),
                        "description": doc.get("description", ""),
                        "question": doc.get("question", ""),
                        "answer": doc.get("answer", ""),
                        "metadata": doc.get("metadata", "") + [f"\nNombre del archivo: {self.file_name}"],
                        "content": doc.get("content", "")
                    }
                    for doc in result
                ]
            }
        }
        
        try:
            # Update existing record instead of creating a new one
            data = _db.table(DATASOURCES_COLLECTION)\
                .update(datasource_data)\
                .eq('datasource_id', self.datasource_id)\
                .execute()
                
            if not data:
                logging.error(f"No record found to update for datasource_id: {self.datasource_id}")
                return (f"Error: No record found to update", STATUS_INTERNAL_SERVER_ERROR)
                
            return (f"Data updated in {DATASOURCES_COLLECTION} table successfully", STATUS_OK)
        except Exception as e:
            logging.error(f"Error saving data to database: {str(e)}")
            return (f"Error saving data: {str(e)}", STATUS_INTERNAL_SERVER_ERROR)
        
    
    def _process_basic_template_file(self)-> List[dict]:
        """Process template file wich contain all columns filled with data and in correcto format"""
        if not self.df.empty:
            empty_raws = (self.df.isnull().any(axis=1) | (self.df == '').any(axis=1))
            if any(empty_raws):
                # First fill empty cells then Re-build Data Structure
                df_copy_original= self.df.copy()
                df_empty_raws = self.df.loc[empty_raws]
                df_copy_original.loc[empty_raws] = self._rebuild_empty_df(df_empty_raws = df_empty_raws)
                df_copy_original["content"] = ("question: " + df_copy_original["question"] + "\n"+
                                            "answer: " + df_copy_original["answer"] + "\n"+
                                            "description: "+ df_copy_original["description"])
                final_records = df_copy_original.to_dict(orient= 'records')
            else:
                # Process Completed and Filled Data required as Template
                if self.source_file_type == "faq":
                    self.df["content"] = ("question: " + self.df["question"] + "\n"+
                                        "answer: " + self.df["answer"] + "\n"+
                                        "description: "+ self.df["description"])
                    final_records = self.df.to_dict(orient='records')
                elif self.source_file_type == "general_info":
                    self.df["label"] = self.file_name
                    self.df["question"] = ''
                    self.df["answer"] = ''
                    final_records = self.df.to_dict(orient='records')
                else:
                    final_records = []
            
            return final_records
        else:
            return ("Data Source is Empty, check it again...", STATUS_INTERNAL_SERVER_ERROR)
    
       
    def _process_faq_file(self) -> List[dict]:
        """Process Dataframe raw by raw adding new features for each raw FAQ"""
        list_df = list()
        for index in range(len(self.df)):
            raw_obj= self.df.iloc[index].to_dict()
            raw_obj["category"]= self.file_name
            raw_obj = str(raw_obj)
            raw_extra_features = self._build_new_features_with_llm_faq(raw_obj)
            raw_extra_features["content"] = ("question: " + raw_extra_features.get("question", "") + "\n"
                                            "answer: "+ raw_extra_features.get("answer", "") + "\n"
                                            "description: "+ raw_extra_features.get("description", ""))
            list_df.append(raw_extra_features)
        return list_df
    
    
    def _process_general_info_file(self) -> List[dict]:
        """Process Dataframe raw by raw adding new features for each raw GENERAL INFO"""
        list_df = list()
        for index in range(len(self.df)):
            raw_obj= self.df.iloc[index].to_dict()
            raw_obj["category"]= self.file_name
            raw_obj = str(raw_obj)
            raw_extra_features = self._build_new_features_with_llm_gen_info(raw_obj)
            raw_extra_features["question"] = ""
            raw_extra_features["answer"] = ""
            list_df.append(raw_extra_features)
        return list_df
    
    
    def process_dataframe(self) -> List[dict]:
        """Process Dataframe for Diferente Cases Provided"""
        
        if self.source_file_type == "faq":
            if (not self.different_cols_faq):
                result= self._process_basic_template_file()
            else:
                result= self._process_faq_file()
        
        elif self.source_file_type == 'general_info':
            if (not self.different_cols_gen_info):
                result= self._process_basic_template_file()
            else:
                result= self._process_general_info_file()
        
        else:
            return (f"Unsupported source_file_type {self.source_file_type}", STATUS_INTERNAL_SERVER_ERROR)
        
        self._save_data_into_mongodb(result= result)
        return result