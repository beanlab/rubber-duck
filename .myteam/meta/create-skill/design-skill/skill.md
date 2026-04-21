---
name: "design-skill"
description: "Load this skill when you have been asked to design, or create a skill for the user."
---

Skill Design Workflow:
1. Assess the codebase you have been asked to work in and assess the following:
  - What function does the repo serve?
  - How does the requested skill fit into the current functions of the repo?
2. Search the web for surface level information relating to the skill:
  - What approaches (if any) exist already to solve the problem the skill seeks to solve?
  - What conventions/style guides exist in the discipline(s) related to the skill that are important to follow?
  - What dependencies/libraries might be needed for the skill to function? In what cases might one of these better than the others?
3. Investigate deeper on any areas that need specific information to be successfully implemented. As examples of the types of questions to ask:
  - What commands or functions specifically need to be used to achieve the desired result?
  - What credentials need to be provided to access the functionality of the tools you have decided to use?
  - What might the user need to provide you with that you are unable to obtain yourself to ensure the skill is completely functional per your design?
4. Structure the skill. This means writing your comprehensive findings to a `<skill-name>-design.md` file. Adhere to the following when writing this file:
  - Frame the file content around high-level architecture the skill will require (e.g. proposed tools, dependencies, and `skill.md` prompt inclusions to make these work)
  - Include all relevant findings of your research in the file (if a research item yielded information that will be incorporated into the skill, include it).
  - The file should provide a user or agent with no context of your research all the information they would need to implement the skill themselves. Be thorough enough that a web search will not be needed.
5. Inform the user that `<skill-name>-design.md` is complete. Wait for the user's approval before continuing.
