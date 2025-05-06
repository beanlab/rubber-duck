from workflows.basic_prompt_workflow import HaveConversation


class SocraticWorkflow:
    def __init__(self, have_conversation: HaveConversation):
        self._have_conversation = have_conversation