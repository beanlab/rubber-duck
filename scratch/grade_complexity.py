import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()


def main(code_file: Path, analysis_file: Path):
    code = code_file.read_text()
    analysis = analysis_file.read_text()

    query = f"""\
    Please grade the following code and complexity analysis.
    Use the provided rubric.
    
    Give only half credit for a rubric item if insufficient details 
    justifying the conclusion are provided. 
    
    Rubric:
    - [10 points] Correct implementation of `mod_exp`
    - [10 points] Correct implementation of `fermat`
    - [10 points] Correct implementation of `miller_rabin`
    - [10 points] Correct analysis of `mod_exp`
    - [10 points] Correct analysis of `fermat`
    - [10 points] Correct analysis of `miller_rabin`
    
    -- Code --
    
    {code}
    
    
    -- Analysis --
    
    {analysis}
    """

    resp = client.chat.completions.create(
        model='o1-preview',
        messages=[
            {'role': 'user', 'content': query}
        ]
    )
    print(resp.choices[0].message.content)


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
