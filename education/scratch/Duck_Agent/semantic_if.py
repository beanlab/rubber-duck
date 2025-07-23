import os
import numpy as np
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text, model="text-embedding-3-small"):
    response = client.embeddings.create(
        model=model,
        input=text
    )
    return response.data[0].embedding

def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2, axis=-1))

def semantic_if(input_text, possibilities, threshold=0.1):
    input_embedding = get_embedding(input_text)

    scored = []
    for possibility in possibilities:
        embedding = get_embedding(possibility)
        similarity = cosine_similarity(input_embedding, embedding)
        if similarity >= threshold:
            print(f"Similarity between '{input_text}' and '{possibility}': {similarity:.4f}")
            scored.append((similarity, possibility))

    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]

def main():
    input_text = ("City of Smart People")
    possibilities = ["New York City", "Salt Lake City", "Los Angeles", "Phoenix", "Detroit", "China"]

    result = semantic_if(input_text, possibilities)
    if result:
        print(f"Most similar possibility: {result}")
    else:
        print("No similar possibility found.")

if __name__ == "__main__":
    main()
