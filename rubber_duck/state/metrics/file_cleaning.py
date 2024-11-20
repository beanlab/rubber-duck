import pandas as pd

if __name__ == "__main__":
    # File path
    file_path = "feedback.csv"

    # Read the CSV into a DataFrame
    df = pd.read_csv(file_path)

    # Replace 'na' with 'Na' in the entire DataFrame
    df = df.replace('Na', 'None')

    # Write the modified DataFrame back to the same file
    df.to_csv(file_path, index=False)

    print(f"All instances of 'na' replaced with 'Na' in {file_path}.")
