import logging
from typing import List, Dict, Any, Literal, Optional

from agents.planner import PlannerAgent
from agents.explainer import ExplainerAgent
from agents.examiner import ExaminerAgent
from agents.models import LearningUnit, ExplanationResponse, QuizResponse, MCQQuestion, OpenEndedQuestion, TrueFalseQuestion, FillInTheBlankQuestion
from services.vector_store import VectorStore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class LearnFlowMCPTool:
    def __init__(self):
        # Agents are initialized here, but their provider can be passed at method call if needed
        self.planner_agent: Optional[PlannerAgent] = None
        self.explainer_agent: Optional[ExplainerAgent] = None
        self.examiner_agent: Optional[ExaminerAgent] = None
        self.vector_store = VectorStore() 

    def _get_planner_agent(self, llm_provider: str, model_name: str = None, api_key: str = None) -> PlannerAgent:
        # Pass the vector_store to the PlannerAgent if it needs to add documents
        if self.planner_agent is None or \
           self.planner_agent.provider != llm_provider or \
           self.planner_agent.model_name != model_name or \
           self.planner_agent.api_key != api_key:
            self.planner_agent = PlannerAgent(provider=llm_provider, model_name=model_name, api_key=api_key)
        return self.planner_agent

    def _get_explainer_agent(self, llm_provider: str, model_name: str = None, api_key: str = None) -> ExplainerAgent:
        if self.explainer_agent is None or \
           self.explainer_agent.provider != llm_provider or \
           self.explainer_agent.model_name != model_name or \
           self.explainer_agent.api_key != api_key:
            self.explainer_agent = ExplainerAgent(provider=llm_provider, vector_store=self.vector_store, model_name=model_name, api_key=api_key) # Pass vector_store
        return self.explainer_agent

    def _get_examiner_agent(self, llm_provider: str, model_name: str = None, api_key: str = None) -> ExaminerAgent:
        if self.examiner_agent is None or \
           self.examiner_agent.provider != llm_provider or \
           self.examiner_agent.model_name != model_name or \
           self.examiner_agent.api_key != api_key:
            self.examiner_agent = ExaminerAgent(provider=llm_provider, model_name=model_name, api_key=api_key)
        return self.examiner_agent

    def plan_learning_units(
        self,
        content: str,
        input_type: Literal["PDF", "Text"],
        llm_provider: str,
        model_name: str = None,
        api_key: str = None
    ) -> List[LearningUnit]:
        """
        Generates a list of learning units from the provided content.

        Args:
            content (str): The content to process (raw text or PDF file path).
            input_type (Literal["PDF", "Text"]): The type of the input content.
            llm_provider (str): The LLM provider to use for planning.
            model_name (str, optional): The specific model name to use. Defaults to None.
            api_key (str, optional): The API key to use. Defaults to None.

        Returns:
            List[LearningUnit]: A list of generated learning units.
        """
        logging.info(f"Planning learning units for input_type: {input_type} with provider: {llm_provider}, model: {model_name}")
        planner = self._get_planner_agent(llm_provider, model_name, api_key)
        # The PlannerAgent now handles adding documents to its internal vector_store
        # which is the same instance as self.vector_store due to how it's passed.
        return planner.act(content, input_type)

    def generate_explanation(
        self,
        unit_title: str,
        unit_content: str,
        explanation_style: Literal["Concise", "Detailed"],
        llm_provider: str,
        model_name: str = None,
        api_key: str = None
    ) -> ExplanationResponse:
        """
        Generates an explanation for a given learning unit.

        Args:
            unit_title (str): The title of the learning unit.
            unit_content (str): The raw content of the learning unit.
            explanation_style (Literal["Concise", "Detailed"]): The desired style of explanation.
            llm_provider (str): The LLM provider to use for explanation generation.
            model_name (str, optional): The specific model name to use. Defaults to None.
            api_key (str, optional): The API key to use. Defaults to None.

        Returns:
            ExplanationResponse: The generated explanation.
        """
        logging.info(f"Generating explanation for unit '{unit_title}' with style '{explanation_style}', provider: {llm_provider}, model: {model_name}")
        explainer = self._get_explainer_agent(llm_provider, model_name, api_key)
        return explainer.act(unit_title, unit_content, explanation_style)

    def generate_quiz(
        self,
        unit_title: str,
        unit_content: str,
        llm_provider: str,
        model_name: str = None,
        api_key: str = None,
        difficulty: str = "Medium",
        num_questions: int = 8,
        question_types: List[str] = ["Multiple Choice", "Open-Ended", "True/False", "Fill in the Blank"]
    ) -> QuizResponse:
        """
        Generates a quiz for a given learning unit.

        Args:
            unit_title (str): The title of the learning unit.
            unit_content (str): The raw content of the learning unit.
            llm_provider (str): The LLM provider to use for quiz generation.
            model_name (str, optional): The specific model name to use. Defaults to None.
            api_key (str, optional): The API key to use. Defaults to None.
            difficulty (str): The desired difficulty level of the quiz (e.g., "Easy", "Medium", "Hard").
            num_questions (int): The total number of questions to generate.
            question_types (List[str]): A list of desired question types (e.g., ["MCQ", "Open-Ended"]).

        Returns:
            QuizResponse: The generated quiz.
        """
        logging.info(f"Generating quiz for unit '{unit_title}' with provider: {llm_provider}, model: {model_name}, difficulty: {difficulty}, num_questions: {num_questions}, types: {question_types}")
        examiner = self._get_examiner_agent(llm_provider, model_name, api_key)
        return examiner.act(unit_content, unit_title, difficulty, num_questions, question_types)

    def evaluate_mcq_response(
        self,
        mcq_question: MCQQuestion,
        user_answer_key: str,
        llm_provider: str,
        model_name: str = None,
        api_key: str = None
    ) -> Dict[str, Any]:
        """
        Evaluates a user's response to a multiple-choice question.

        Args:
            mcq_question (MCQQuestion): The MCQ question object.
            user_answer_key (str): The key corresponding to the user's selected answer.
            llm_provider (str): The LLM provider.
            model_name (str, optional): The specific model name to use. Defaults to None.
            api_key (str, optional): The API key to use. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing evaluation results (e.g., is_correct, feedback).
        """
        logging.info(f"Evaluating MCQ response for question: {mcq_question.question} with provider: {llm_provider}, model: {model_name}")
        examiner = self._get_examiner_agent(llm_provider, model_name, api_key)
        return examiner.evaluate_mcq_response(mcq_question, user_answer_key)

    def evaluate_true_false_response(
        self,
        tf_question: TrueFalseQuestion,
        user_answer: bool,
        llm_provider: str,
        model_name: str = None,
        api_key: str = None
    ) -> Dict[str, Any]:
        """
        Evaluates a user's response to a true/false question.

        Args:
            tf_question (TrueFalseQuestion): The True/False question object.
            user_answer (bool): The user's true/false answer.
            llm_provider (str): The LLM provider.
            model_name (str, optional): The specific model name to use. Defaults to None.
            api_key (str, optional): The API key to use. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing evaluation results (e.g., is_correct, feedback).
        """
        logging.info(f"Evaluating True/False response for question: {tf_question.question} with provider: {llm_provider}, model: {model_name}")
        examiner = self._get_examiner_agent(llm_provider, model_name, api_key)
        return examiner.evaluate_true_false_response(tf_question, user_answer)

    def evaluate_fill_in_the_blank_response(
        self,
        fitb_question: FillInTheBlankQuestion,
        user_answer: str,
        llm_provider: str,
        model_name: str = None,
        api_key: str = None
    ) -> Dict[str, Any]:
        """
        Evaluates a user's response to a fill-in-the-blank question.

        Args:
            fitb_question (FillInTheBlankQuestion): The FillInTheBlank question object.
            user_answer (str): The user's answer for the blank.
            llm_provider (str): The LLM provider.
            model_name (str, optional): The specific model name to use. Defaults to None.
            api_key (str, optional): The API key to use. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing evaluation results (e.g., is_correct, feedback).
        """
        logging.info(f"Evaluating Fill in the Blank response for question: {fitb_question.question} with provider: {llm_provider}, model: {model_name}")
        examiner = self._get_examiner_agent(llm_provider, model_name, api_key)
        return examiner.evaluate_fill_in_the_blank_response(fitb_question, user_answer)

    def evaluate_open_ended_response(
        self,
        open_ended_question: OpenEndedQuestion,
        user_answer_text: str,
        llm_provider: str,
        model_name: str = None,
        api_key: str = None
    ) -> Dict[str, Any]:
        """
        Evaluates a user's response to an open-ended question.

        Args:
            open_ended_question (OpenEndedQuestion): The open-ended question object.
            user_answer_text (str): The user's free-form answer.
            llm_provider (str): The LLM provider.
            model_name (str, optional): The specific model name to use. Defaults to None.
            api_key (str, optional): The API key to use. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing evaluation results (e.g., score, feedback, model_answer).
        """
        logging.info(f"Evaluating open-ended response for question: {open_ended_question.question} with provider: {llm_provider}, model: {model_name}")
        examiner = self._get_examiner_agent(llm_provider, model_name, api_key)
        return examiner.evaluate_open_ended_response(open_ended_question, user_answer_text, llm_provider, model_name, api_key)
