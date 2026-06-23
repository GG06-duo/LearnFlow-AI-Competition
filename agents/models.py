from pydantic import BaseModel
from typing import List, Dict, Optional, Any

# Explainer Agent Models
class VisualAid(BaseModel):
    type: str  # e.g., "image", "chart", "diagram"
    path: str
    caption: Optional[str] = None

class CodeExample(BaseModel):
    language: str
    code: str
    description: Optional[str] = None

class ExplanationResponse(BaseModel):
    markdown: str
    visual_aids: List[VisualAid] = []
    code_examples: List[CodeExample] = []

# Examiner Agent Models
class MCQOption(BaseModel):
    key: str # A, B, C, D
    value: str

class MCQQuestion(BaseModel):
    id: str
    question: str
    options: Dict[str, str] # Use Dict[str, str] for options mapping
    correct_answer: str
    explanation: str
    user_answer: Optional[str] = None # To store user's selected option key
    is_correct: Optional[bool] = None # To store if the user's answer was correct

class OpenEndedQuestion(BaseModel):
    id: str
    question: str
    model_answer: str
    keywords: Optional[List[str]] = None
    user_answer: Optional[str] = None # To store user's text answer
    score: Optional[float] = None # To store the score for open-ended questions
    feedback: Optional[str] = None # To store feedback for open-ended questions

class TrueFalseQuestion(BaseModel):
    id: str
    question: str
    correct_answer: bool # True or False
    explanation: str
    user_answer: Optional[bool] = None
    is_correct: Optional[bool] = None

class FillInTheBlankQuestion(BaseModel):
    id: str
    question: str # e.g., "The capital of France is ______."
    correct_answer: str # The word(s) that fill the blank
    explanation: str
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None

class QuizResponse(BaseModel):
    mcqs: List[MCQQuestion] = []
    open_ended: List[OpenEndedQuestion] = []
    true_false: List[TrueFalseQuestion] = []
    fill_in_the_blank: List[FillInTheBlankQuestion] = []
    unit_title: str

# Planner Agent Models
class LearningUnit(BaseModel):
    title: str
    content_raw: str
    summary: str
    status: str = "not_started" # Add status for consistency with SessionState
    explanation: Optional[str] = None # Add explanation field
    explanation_data: Optional['ExplanationResponse'] = None # ADDED
    quiz_results: Optional[Dict] = None # Add quiz_results field
    quiz_data: Optional[QuizResponse] = None
    metadata: Dict[str, Any] = {} # New field to store LlamaIndex node metadata, explicitly typed

class PlannerResponse(BaseModel):
    units: List[LearningUnit]
