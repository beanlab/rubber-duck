import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()


def main(code_file: Path):
    code = code_file.read_text()

    query = f"""\
    Please write a markdown report that provides a complexity analysis of the following code. 
    State any assumptions you make. 
    
    Code:
    {code}
    """

    resp = client.chat.completions.create(
        model='o1-preview',
        messages=[
            {'role': 'user', 'content': query}
        ]
    )
    print(resp.choices[0].message.content)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
