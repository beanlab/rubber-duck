from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sbn
import json


class ReportAssistant():
    def __init__(self):
        self.usage = pd.read_csv("./state/metrics/usage.csv")
        # self.messages = pd.read_csv("./state/metrics/messages.csv")
        self.feedback = pd.read_csv("./state/metrics/feedback.csv")

    def read_df(self, df: pd.DataFrame, n=10):
        print(df.head(n))
        return df

    def view_graph(self, df: pd.DataFrame, type = 'bar chart'):
        pass


def get_df(assistant: ReportAssistant):
    while True:
        df_request = input("Which data do you want to view from? Usage, messages, or feedback?\n").lower()
        match df_request:
            case 'usage' | 'u':
                return assistant.usage
            case 'feedback' | 'f':
                return assistant.feedback
            case 'q':
                print("See you next time!")
                return None
            case _:
                print(f"Sorry, '{df_request}' is not an option.")



def main(assistant: ReportAssistant):
    print("Seems like you'd like to do some data analytics!")
    df = get_df(assistant)
    assistant.read_df(df)

    print("Hope that was helpful!")

if __name__ == "__main__":
    main(ReportAssistant())