import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from agents.models import LearningUnit, ExplanationResponse, QuizResponse
import json
import os

# Define a directory for session files
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True) 

class SessionState(BaseModel):
    units: List[LearningUnit] = []
    current_unit_index: Optional[int] = None
    provider: str = "openai"

    def clear_units(self):
        self.units = []
        self.current_unit_index = None
        logging.info("SessionState: Cleared all units and reset current_unit_index.")

    def add_units(self, units_data: List[LearningUnit]):
        existing_titles = {unit.title for unit in self.units}
        new_unique_units = []
        for unit in units_data:
            if unit.title not in existing_titles:
                new_unique_units.append(unit)
                existing_titles.add(unit.title)
        self.units.extend(new_unique_units)
        logging.info(f"SessionState: Added {len(new_unique_units)} new units. Total units: {len(self.units)}")

    def set_current_unit(self, index: int):
        if 0 <= index < len(self.units):
            self.current_unit_index = index
            logging.info(f"SessionState.set_current_unit: Set self.current_unit_index to {self.current_unit_index} for unit '{self.units[index].title}'")
            if self.units[index].status == "not_started":
                self.units[index].status = "in_progress"
        else:
            self.current_unit_index = None
            logging.warning(f"SessionState.set_current_unit: Invalid index {index}. current_unit_index set to None.")

    def get_current_unit(self) -> Optional[LearningUnit]:
        if self.current_unit_index is not None and 0 <= self.current_unit_index < len(self.units):
            return self.units[self.current_unit_index]
        return None
    
    def get_current_unit_dropdown_value(self) -> Optional[str]:
        current_unit = self.get_current_unit()
        if current_unit and self.current_unit_index is not None:
            return f"{self.current_unit_index + 1}. {current_unit.title}"
        return None

    def update_unit_explanation(self, unit_index: int, explanation_markdown: str):
        if 0 <= unit_index < len(self.units):
            if hasattr(self.units[unit_index], 'explanation'):
                self.units[unit_index].explanation = explanation_markdown
            if self.units[unit_index].status == "not_started":
                self.units[unit_index].status = "in_progress"

    def update_unit_explanation_data(self, unit_index: int, explanation_data: ExplanationResponse):
        if 0 <= unit_index < len(self.units):
            logging.info(f"SessionState: Storing full explanation_data for unit index {unit_index}, title '{self.units[unit_index].title}'")
            self.units[unit_index].explanation_data = explanation_data
            if hasattr(self.units[unit_index], 'explanation'):
                self.units[unit_index].explanation = explanation_data.markdown
            
            if self.units[unit_index].status == "not_started":
                self.units[unit_index].status = "in_progress"
        else:
            logging.warning(f"SessionState.update_unit_explanation_data: Invalid unit_index: {unit_index}")

    def update_unit_quiz(self, unit_index: int, quiz_results: Dict):
        if 0 <= unit_index < len(self.units):
             if hasattr(self.units[unit_index], 'quiz_results'):
                self.units[unit_index].quiz_results = quiz_results
             if self.units[unit_index].status == "in_progress":
                self.units[unit_index].status = "completed"

    def _check_quiz_completion_status(self, unit: LearningUnit) -> bool:
        """Checks if all generated questions for a unit have been answered."""
        if not unit.quiz_data:
            return False

        all_answered = True

        # Check MCQs
        if unit.quiz_data.mcqs:
            if not all(q.user_answer is not None for q in unit.quiz_data.mcqs):
                all_answered = False
        
        # Check Open-Ended Questions
        if unit.quiz_data.open_ended:
            if not all(q.user_answer is not None for q in unit.quiz_data.open_ended):
                all_answered = False
        
        # Check True/False Questions
        if unit.quiz_data.true_false:
            if not all(q.user_answer is not None for q in unit.quiz_data.true_false):
                all_answered = False
        
        # Check Fill in the Blank Questions
        if unit.quiz_data.fill_in_the_blank:
            if not all(q.user_answer is not None for q in unit.quiz_data.fill_in_the_blank):
                all_answered = False
        
        return all_answered

    def update_unit_quiz_data(self, unit_index: int, quiz_data: QuizResponse):
        if 0 <= unit_index < len(self.units):
            logging.info(f"SessionState: Storing full quiz_data for unit index {unit_index}, title '{self.units[unit_index].title}'")
            self.units[unit_index].quiz_data = quiz_data
            
            # Check if the quiz is fully completed and update unit status
            if self._check_quiz_completion_status(self.units[unit_index]):
                self.units[unit_index].status = "completed"
                logging.info(f"Unit '{self.units[unit_index].title}' marked as 'completed' as all quiz questions are answered.")
            elif self.units[unit_index].status == "not_started":
                self.units[unit_index].status = "in_progress"
        else:
            logging.warning(f"SessionState.update_unit_quiz_data: Invalid unit_index: {unit_index}")

    def get_progress_summary(self) -> Dict:
        total = len(self.units)
        completed = sum(1 for unit in self.units if unit.status == "completed")
        in_progress = sum(1 for unit in self.units if unit.status == "in_progress")
        not_started = total - completed - in_progress
        return {
            "total_units": total,
            "completed_units": completed,
            "in_progress_units": in_progress,
            "not_started_units": not_started
        }

    def get_average_quiz_score(self) -> float:
        """Calculates the average quiz score across all units with completed quizzes, considering all question types."""
        total_correct_questions = 0
        total_possible_questions = 0

        for unit in self.units:
            if unit.quiz_data:
                # Count MCQs
                if unit.quiz_data.mcqs:
                    total_correct_questions += sum(1 for q in unit.quiz_data.mcqs if q.is_correct)
                    total_possible_questions += len(unit.quiz_data.mcqs)
                
                # Count True/False
                if unit.quiz_data.true_false:
                    total_correct_questions += sum(1 for q in unit.quiz_data.true_false if q.is_correct)
                    total_possible_questions += len(unit.quiz_data.true_false)
                
                # Count Fill in the Blank
                if unit.quiz_data.fill_in_the_blank:
                    total_correct_questions += sum(1 for q in unit.quiz_data.fill_in_the_blank if q.is_correct)
                    total_possible_questions += len(unit.quiz_data.fill_in_the_blank)
                
                # Count Open-Ended (score >= 5/10 is considered correct)
                if unit.quiz_data.open_ended:
                    total_correct_questions += sum(1 for q in unit.quiz_data.open_ended if q.score is not None and q.score >= 5)
                    total_possible_questions += len(unit.quiz_data.open_ended)
        
        return (total_correct_questions / total_possible_questions) * 100 if total_possible_questions > 0 else 0.0

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'SessionState':
        return cls.model_validate_json(json_str)

    def save_session(self, session_name: str) -> str:
        """Saves the current session state to a JSON file."""
        filepath = os.path.join(SESSION_DIR, f"{session_name}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.to_json())
            logging.info(f"Session saved to {filepath}")
            return f"会话“{session_name}”已成功保存！"
        except Exception as e:
            logging.error(f"Error saving session '{session_name}' to {filepath}: {e}", exc_info=True)
            return f"保存会话时出错：{str(e)}"

    @classmethod
    def load_session(cls, session_name: str) -> 'SessionState':
        """Loads a session state from a JSON file."""
        filepath = os.path.join(SESSION_DIR, f"{session_name}.json")
        if not os.path.exists(filepath):
            logging.warning(f"Session file not found: {filepath}")
            raise FileNotFoundError(f"未找到会话“{session_name}”。")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                json_str = f.read()
            session_state = cls.from_json(json_str)
            logging.info(f"Session '{session_name}' loaded from {filepath}")
            return session_state
        except Exception as e:
            logging.error(f"Error loading session '{session_name}' from {filepath}: {e}", exc_info=True)
            raise RuntimeError(f"Error loading session: {str(e)}")

def get_unit_status_emoji(unit: LearningUnit) -> str:
    if unit.status == "completed":
        return "✅"
    elif unit.status == "in_progress":
        return "🕑"
    else:
        return "📘"

def get_units_for_dropdown(session: SessionState) -> List[str]:
    if not session or not session.units:
        return ["No units available"]
    return [f"{i+1}. {unit.title}" for i, unit in enumerate(session.units)]

def list_saved_sessions() -> List[str]:
    """Lists all available saved session names (without .json extension)."""
    try:
        session_files = [f for f in os.listdir(SESSION_DIR) if f.endswith(".json")]
        return sorted([os.path.splitext(f)[0] for f in session_files])
    except Exception as e:
        logging.error(f"Error listing saved sessions: {e}", exc_info=True)
        return []
