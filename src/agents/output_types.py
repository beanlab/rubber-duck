from pydantic import BaseModel

from enum import Enum
from pydantic import BaseModel, Field
from typing import List

class FeedbackResponseItem(BaseModel):
    met: bool
    citation: str
    comments: str

class FeedbackItem(BaseModel):
    citation: str
    feedback: str


class GradedCodeComplexityItem(BaseModel):
    function_name: str
    student_function_name: str
    feedback: List[FeedbackItem]
    correct: bool


class FunctionWithAnalysis(BaseModel):
    function_name: str
    analysis_type: str
    function_analysis: str
    found: bool


class FunctionToGrade(BaseModel):
    function_name: str
    analysis_type: str


class CodeAnalyzed(BaseModel):
    code_analyzed: str


def get_model(model_name, num_items):
    if model_name == 'GivenFunctionsAnalyses':
        class GivenFunctionsAnalyses(BaseModel):
            functionAnalyses: List[FunctionWithAnalysis] = Field(min_length=num_items,
                                                                 max_length=num_items)

        return GivenFunctionsAnalyses

    elif model_name == 'GradedCodeComplexityItems':
        class GradedCodeComplexityItems(BaseModel):
            items: List[GradedCodeComplexityItem] = Field(min_length=num_items,
                                                          max_length=num_items)

        return GradedCodeComplexityItems

    elif model_name == 'FeedbackResponseItems':
        class FeedbackResponseItems(BaseModel):
            items: List[FeedbackResponseItem] = Field(min_length=num_items,
                                                      max_length=num_items)

        return FeedbackResponseItems


def get_output_type(output_type_name, num_items):
    if output_type_name == "FeedbackResponseItems":
        return get_model("FeedbackResponseItems", num_items)
    elif output_type_name == "FeedbackResponseItem":
        return FeedbackResponseItem
    else:
        raise f"Unsupported output type provided: {output_type_name}"
