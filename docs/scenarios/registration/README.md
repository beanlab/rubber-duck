# Registration Scenarios

Registration scenarios describe Discord-thread registration behavior for
users who need verified access.

The shared registration context is:

- a user has started a registration conversation thread
- the conversation validates a Net ID
- the user is verified through an email challenge
- successful registration may update the user's Discord nickname and role
- failed registration must not complete the nickname and role-assignment flow

## Scenarios

- [Registration verifies and registers users](registration_verifies_and_registers_users.md)
