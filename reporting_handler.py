import pandas as pd

from argparse import ArgumentError

class csvHandler():
    def __init__(self):
        self.path = "state/metrics/"
        self.df_options = {'feedback', 'usage', 'messages'}

    def select_dataframe(self, desired_df):
        """Load the dataframe based on user input."""
        if desired_df not in self.df_options:
            raise ArgumentError(None, f"Invalid dataframe: {desired_df}")
        return pd.read_csv(f"{self.path}{desired_df}.csv")