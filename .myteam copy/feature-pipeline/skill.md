---
name: Feature Pipeline
description: |
    This skill defines the process to follow for developing new features.
    Load this skill if you are tasked with changing anything in the `src/myteam/` directory.
---

## Feature Pipeline

Carefully follow each of these steps in order. Do not proceed to a later step until the earlier step is finished.
We're not worried about multitasking and efficiency; we care about process and quality.

### Create the git branch

Check the current branch. 
If you are on `main`, remind the user to start a new branch and wait for them to do so before proceeding.

### Understand the feature and update the interface document

The goal of this step is to thoroughly understand the requested feature
and document how the primary interface of the application should be changed.

First read `src/governing_docs/application_interface.md` to understand
the current design and intent of the project.
This document describes what this app should do, how it behaves, etc.
It is the black-box description of the user's experience with the application.

Then seek to understand what the user wants to change. 
Is it a new behavior? Modifying an existing behavior? A bugfix?

Discuss these things with the user. Involve them in the process.

Questions that might be relevant:

- What changes in behavior does the user hope for?
- What behaviors should NOT change?

Once you have a thorough understanding of the user's intent, 
update the `application_interface.md` document to reflect the changes.

Review these changes with the user. Make sure you are both on the same page
before you continue.

When this step is complete, commit your changes before moving on.

### Design the feature

The goal of this step is to understand how the feature will be implemented.
It is NOT to implement that changes. That will come later.

#### Understand the context

Load the `framework-oriented-design` skill. 

Then look through the code. Understand the framework and infrastructure in place that supports the current application.
Notice the intentional design decisions and articulate the reasoning for those decisions.

#### Plan the feature

Now, consider how this feature could be implemented. 

Is the existing framework sufficient to support this new feature?
If not, how should the framework be modified to naturally support the feature?

Implementing a feature has two phases: 1) updating the framework, and 2) sliding the new feature into place.
If the framework is right, the new feature will be simple to implement. 
So, make sure we understand how the framework is going to change to accommodate the feature.

Think through how the framework changes will make the feature implementation simple. 
As necessary, iterate on this process until you have a simple refactor that supports a simple feature implementation. 

If changes to the framework are needed, consider: 

- If there are multiple reasonable strategies, what distinguishes them?
- Are there dependencies that may change? 
- Is there documentation via skills or in the repo that suggests a strategy?
- Does the user have an opinion on which strategy is used?

Be specific. This is the stage of the process where you figure out all the details.
Do not leave any decisions for later. 

Think critically about the changes. Is there a simpler way? 
Simplicity is SO important to maintaining a codebase. Be very skeptical of new complexity.

Think also about consistency. Is there a style or pattern already used in the codebase that could be followed?

Prepare a document named `src/governing_docs/feature_plans/<branch_name>.md`
that describes the specific details and strategies decided on for the feature.

This document should have two main parts:

1) Framework refactor: here describe the feature-neutral refactorings to the existing code that prepare the code for the new feature
   - The existing test suite should not need to change in response to this step
   - If changes are needed because the framework has changed, and thus the testing infrastructure must be modified, that's fine
2) Feature addition: here describe the code needed to introduce the new feature 

Get approval from the user on this document before continuing.

When this step is complete, commit your changes before moving on.

### Refactor the framework

Following the feature plan part 1 guidance, make any necessary changes to the application framework.

The existing tests should all still pass.

Describe to the user the changes that were made and why they were made. 
Explain how these changes will make adding the feature a simple process.

Get approval from the user on these changes before continuing.

When this step is complete, commit your changes before moving on.

### Update the test suite

Load the `testing` skill.

Review the existing tests. Identify changes that need to be made to test suite
to bring it in line with the updated interface document.

Make these changes to the test suite.

Review the changes one more time: do they faithfully capture the new interface design?
Make changes as needed.

Explain to the user how the new tests address the changes made to the interface document.
Get their approval before continuing.

When this step is complete, commit your changes before moving on.

### Implement the feature

Now that the framework has been updated (as necessary) and the tests are in place,
implement the feature.

Follow the guidance in part 2 of the feature document.

Use the existing framework to support the feature. 

The tests should pass. 

Review the changes made with the user. Get their approval before continuing.

When this step is complete, commit your changes before moving on.

### Concluding the feature

Follow the instructions in the `conclusion` subskill to verify everything is ready
for the pull request to be created and merged.

### Notify the user

Notify the user that the feature is ready to push to github and merge.
