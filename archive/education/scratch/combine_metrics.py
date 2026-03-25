import os
import pandas as pd

if __name__ == "__main__":
    # Define the directory containing the folders
    base_directory = 'all_metrics'

    # Initialize dictionaries to hold the combined data for each file type
    data = {
        'feedback': pd.DataFrame(),
        'messages': pd.DataFrame(),
        'usage': pd.DataFrame()
    }

    # Loop over each folder in the base directory
    for folder in os.listdir(base_directory):
        folder_path = os.path.join(base_directory, folder)
        if os.path.isdir(folder_path):  # Ensure we're only processing folders
            # Loop over each file type
            for file_type in data.keys():
                file_path = os.path.join(folder_path, f'{file_type}.csv')
                if os.path.exists(file_path):
                    # Read the file and append it to the appropriate DataFrame
                    temp_df = pd.read_csv(file_path)
                    if 'reviewer_role_id' in temp_df.columns:
                        temp_df.drop('reviewer_role_id', axis=1, inplace=True)
                    data[file_type] = pd.concat([data[file_type], temp_df], ignore_index=True)

    # Save each combined DataFrame to a separate CSV file
    for file_type, df in data.items():
        df.to_csv(f'{file_type}_combined.csv', index=False)
        print(f"Saved {file_type}_combined.csv with {len(df)} rows.")
