from .tools import register_tool
import re
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger

class SocraticTools:
    def __init__(self):
        pass

    def mark_checklist_item_logic(self, checklist_markdown: str, item_to_mark: str) -> str:
        """Helper function to mark off a checklist item."""
        pattern = re.compile(r"^([ \t\-\*]*)\[ \] (.*)$", re.MULTILINE)
        def replacer(match):
            prefix, item = match.groups()
            if item.strip() == item_to_mark.strip():
                return f"{prefix}[x] {item}"
            return match.group(0)
        return pattern.sub(replacer, checklist_markdown)

    def check_state_logic(self, checklist_markdown: str) -> bool:
        """Helper function to check if all items are marked."""
        pattern = re.compile(r"^[ \t\-\*]*\[ \] .*$", re.MULTILINE)
        return not pattern.search(checklist_markdown)

    @register_tool
    def mark_checklist_item(self, item_to_mark: str, context: DuckContext) -> str:
        """
        Marks off an item in the checklist if the user has proven how they will do that step.
        Args:
            item_to_mark: The exact text of the checklist item to mark as completed.
            context: The conversation context containing the checklist.
        Returns:
            The updated markdown checklist with the specified item marked as completed ([x]).
        """
        if context.checklist_markdown is None:
            duck_logger.debug("No checklist available to mark item.")
            return "No checklist available"
        updated = self.mark_checklist_item_logic(context.checklist_markdown, item_to_mark)
        context.checklist_markdown = updated
        duck_logger.debug(f"Marked item '{item_to_mark}' in checklist.")
        return updated

    @register_tool
    def check_state(self, context: DuckContext) -> bool:
        """
        Checks if all items in the checklist are marked as completed.
        Args:
            context: The conversation context containing the checklist.
        Returns:
            True if all checklist items are marked as completed ([x]), False otherwise.
        """
        if context.checklist_markdown is None:
            duck_logger.debug("No checklist available to check state.")
            return False
        duck_logger.debug("Checking state of checklist.")
        return self.check_state_logic(context.checklist_markdown)

    @register_tool
    def get_unmarked_items(self, context: DuckContext) -> str:
        """
        Returns a list of unmarked checklist items to help identify what can be marked off.
        Args:
            context: The conversation context containing the checklist.
        Returns:
            A string listing all unmarked items.
        """
        if context.checklist_markdown is None:
            duck_logger.debug("No checklist available to get unmarked items.")
            return "No checklist available"
        
        pattern = re.compile(r"^[ \t\-\*]*\[ \] (.+)$", re.MULTILINE)
        unmarked = pattern.findall(context.checklist_markdown)
        if not unmarked:
            duck_logger.debug("All items are marked off in the checklist.")
            return "All items are marked off!"
        duck_logger.debug(f"Found unmarked items: {unmarked}")
        return "Unmarked items: " + ", ".join(unmarked)

