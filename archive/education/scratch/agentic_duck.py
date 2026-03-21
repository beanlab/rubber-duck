class ADuck:
    def __init__(self, genai):
        self._genai = genai

    async def be_helpful(self):
        repeat = True
        while repeat:
            concept = await self._figure_out_concept()
            lesson = await self._prepare_a_lesson(concept)
            repeat = await self._assess_success()

    async def _figure_out_concept(self):
        # how can I help?
        # RAG
        # What questions to follow up
        # get response
        # summarize the concept

        # how can I help?
        # Student response
        while True:
            pass
        # RAG?
        # what questions to follow up
        # student responds
        # is the problem to solve well defined?
        # Yes - return a summary
        # no - what questions...
        pass

    async def _prepare_a_lesson(self, concept):
        # RAG?
        # Given this concept (and material)
        # Design a lesson to teach this concept
        # |
        # V
        # Deliver lesson
        #
        # Add at the end: does that make sense?

        pass
