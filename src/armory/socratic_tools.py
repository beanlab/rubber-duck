from .tools import register_tool
import re

@register_tool
def mark_checklist_item(
    checklist_markdown: str,
    item_to_mark: str
) -> str:
    """
    Marks off an item in a markdown checklist if the user has proven how they will do that step.
    Args:
        checklist_markdown: The markdown string containing the checklist (with - [ ] or - [x] items).
        item_to_mark: The text of the checklist item to mark as completed.
    Returns:
        The updated markdown checklist with the specified item marked as completed ([x]).
    """
    # Regex to match checklist items
    pattern = re.compile(r"^([ \t\-\*]*)\[ \] (.*)$", re.MULTILINE)
    def replacer(match):
        prefix, item = match.groups()
        if item.strip() == item_to_mark.strip():
            return f"{prefix}[x] {item}"
        return match.group(0)
    updated_checklist = pattern.sub(replacer, checklist_markdown)
    return updated_checklist

