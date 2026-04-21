# Spring Cleaning Deep Review Implementation Plan

1. Update spring-cleaning skill workflow
   - Edit `.myteam/spring-cleaning/skill.md` to require deep, multi-agent audit.
   - Specify report path `docs/spring-cleanings/spring-cleaning-<mm-dd>.md`.
   - Require agents to read `docs/application_interface.md` and `production-config.yaml` first.
   - Add explicit steps for report aggregation and one-change-at-a-time cleanup.

2. Create new roles with `myteam new role`
   - `spring-cleaning/project-structure`
   - `spring-cleaning/prompt-evaluator`
   - `spring-cleaning/src-evaluator`

3. Implement role instructions and loaders
   - `project-structure` load script must print full project tree using `print_directory_tree`.
   - All roles must read required files before analysis.
   - All roles must append findings to their section in the shared report file.

4. Deprecate/clarify `spring-cleaning/identify-weak-points`
   - Update role instructions to indicate superseded by new multi-agent workflow.
   - Keep it available for backward compatibility if invoked directly.

5. Verify skill load
   - Run `myteam get skill spring-cleaning` to confirm instructions render correctly.
