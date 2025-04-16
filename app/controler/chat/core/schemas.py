from langchain_core.pydantic_v1 import BaseModel, Field


class GradeRelevanceSchema(BaseModel):
    """Binary score for relevance to user question check."""
    binary_score: str = Field(description="Relevance score 'true' or 'false'")


class MongoDBSchema(BaseModel):
    query: str = Field(description="This is a text query message sent by user that need to be used as FIND query into MongoDB")
