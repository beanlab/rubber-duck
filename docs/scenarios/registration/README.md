# Registration Scenarios

Registration scenarios describe Discord-thread registration workflows
for ducks configured with `duck_type` set to `registration`.

The shared registration context is:

- a user has started a registration conversation thread
- the workflow validates a Net ID
- the workflow verifies the user through an email challenge
- successful registration may update the user's Discord nickname and role
- failed registration must not complete the nickname and role-assignment flow

## Scenarios

- [Completes email-verified registration](completes_email_verified_registration.md)
- [Rejects invalid registration attempts](rejects_invalid_registration_attempts.md)
- [Reports registration permission failures](reports_registration_permission_failures.md)
