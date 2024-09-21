from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sbn
import json

# class ReportAssistant()


def main():
    print("Howdy rubber duck")
    usage = pd.read_csv("./state/metrics/usage.csv")
    messages = pd.read_csv("./state/metrics/messages.csv")
    feedback = pd.read_csv("./state/metrics/feedback.csv")
    print(usage)

if __name__ == "__main__":
    main()