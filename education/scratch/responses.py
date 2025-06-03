import openai

openai.api_key = "your-api-key"

response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a tutor helping a student understand their knowledge gaps."},
        {"role": "user", "content": "Can you tell if I understand recursion well?"}
    ]
)

# Print full response object for logging
print(response)

# Extract the model's reply
message = response['choices'][0]['message']['content']
print("Assistant:", message)
