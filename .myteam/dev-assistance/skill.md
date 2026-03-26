---
name: Dev Assistance
description: |
  Instructions for how to provide developer assistance when working in the rubber-duck project.
  If you are asked to create a new feature, load this skill.
---

This project provides AI assistants to users through chat platforms like Discord.

The flagship assistant is the "Rubber Duck", a virtual TA for computer science classes.

The prompts for these agents are in `prompts/`.

# Process

1. Call `src` and/or `config` skills depending on feature requirements. 

2. Read relevant `DOCS.md` files before scanning many code files.

    - Use `DOCS.md` as the map of ownership, data flow, and key files, then read source files for implementation details.

4. Ask the user questions, one at a time, to gather the necessary information to implement the feature. 

    - Do not ask for all the information at once. Wait for the user's response after each question before asking the next one.

5. Implement the feature based on the gathered information.

    - Prioritize injection dependencies and modular design to ensure the new feature is maintainable and testable. Follow existing code patterns and best practices observed in the codebase.

6. Review the implementation to ensure it meets the requirements and does not introduce any bugs or issues.

    - Does the implementation meet the requirements?
    - Are there any duplicated code or opportunities for refactoring?
    - Are there any potential edge cases or error handling that needs to be addressed?
    - Implement changes as needed based on the review.

7. Update documentation to reflect the new feature and its implementation details.

    - Load `docs-assistance`
    - README.md, CHANGELOG.md, DOCS.md, and any relevant code comments should be updated to provide brief and clear information about the new feature.

