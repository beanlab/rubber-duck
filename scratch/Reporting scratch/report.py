from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sbn
import json


class ReportAssistant():
    def __init__(self):
        self.usage = pd.read_csv("../../sample_metrics/usage.csv")
        self.messages = pd.read_csv("../../sample_metrics/messages.csv")
        self.feedback = pd.read_csv("../../sample_metrics/feedback.csv")
        self.current_df = None

    def read_df(self, df: pd.DataFrame, n=10):
        print(df.head(n))
        return df

    def view_graph(self, df: pd.DataFrame, type = 'bar chart'):
        df = df[["user_id", "output_tokens"]]
        if type == "bar chart":
            print(f'You chose a bar chart to view {self.current_df}')
            print(f"{df.groupby(['user_id']).output_tokens.sum().reset_index()}")
            sbn.barplot(
                data=df.groupby(['user_id']).output_tokens.sum().reset_index(),
                x='user_id',
                y='output_tokens',
            )


def get_df(assistant: ReportAssistant):
    while True:
        df_request = input("Which data do you want to view from? Usage, messages, or feedback?\n").lower()
        match df_request:
            case 'usage' | 'u':
                assistant.current_df = 'usage'
                return assistant.read_df(assistant.usage)
            case 'feedback' | 'f':
                assistant.current_df = 'feedback'
                return assistant.read_df(assistant.feedback)
            case 'q':
                print("See you next time!")
                return None
            case _:
                print(f"Sorry, '{df_request}' is not an option.")



def main(assistant: ReportAssistant):
    print("Seems like you'd like to do some data analytics!")
    df = get_df(assistant)
    assistant.view_graph(df)

    print("Hope that was helpful!")

if __name__ == "__main__":
    main(ReportAssistant())