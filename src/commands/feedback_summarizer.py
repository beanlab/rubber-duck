from openai import OpenAI


class FeedbackSummarizer:
    def __init__(self, openai_key):
        self.client = OpenAI(api_key=openai_key)

    def summarize(self, feedback_text: str, max_tokens: int = 300) -> str:
        if not feedback_text.strip():
            return "No feedback provided."

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Updated to current available model
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that summarizes user feedback clearly and concisely. Create a one paragraph summary of the feedback provided."
                    },
                    {
                        "role": "user",
                        "content": feedback_text
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.5
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise RuntimeError(f"Failed to generate summary: {e}")

