## Change Workflow

When asked to update the application design:

1. Determine whether the requested change affects the user interface or
   the operations interface.
2. If it affects neither, do not update the application design docs.
   The change is likely an implementation detail.
3. Find the smallest existing document that owns the affected behavior
   or interface.
4. Update that document.
5. If needed, update parent index documents so the information remains
   discoverable.
6. If no existing document is a good fit, create a new document in the
   most appropriate location.
7. If the document structure has become confusing or too large,
   delegate refactoring before making substantial additions.

Prefer extending an existing coherent document over creating a new one.
Prefer creating a new document over forcing unrelated topics into the
same file.
