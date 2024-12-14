import io
import sys
from argparse import ArgumentParser, ArgumentError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import PercentFormatter

from metrics import MetricsHandler


def fancy_preproccesing(df):

    return (
        df
        .set_index(pd.DatetimeIndex(pd.to_datetime(df['timestamp'], utc=True)))
        .resample('W') # Resample to weekly frequency
        .agg(
            avg_score=('feedback_score', lambda x: pd.to_numeric(x, errors='coerce').mean()),
            valid_scores_pct=('feedback_score', lambda x: pd.to_numeric(x, errors='coerce').notna().mean() * 100)
        )
        .reset_index()
    )


def feed_fancy_graph(df_feedback, arg_string, show_fig):
    specific_str = arg_string.split()[2]
    df = fancy_preproccesing(df_feedback)

    # Plot the percentage of valid scores each week
    plt.figure(figsize=(10, 6))
    if specific_str == 'percent':
        sns.lineplot(data=df, x='timestamp', y='valid_scores_pct', marker='o', color='orange')
        plt.gca().yaxis.set_major_formatter(PercentFormatter())

    else:
        sns.lineplot(data=df, x='timestamp', y='avg_score', marker='o', color='orange')

    main_string = f"{specific_str.title()}_Recorded_Feedback_Scores_Per_Week"
    plt.title(main_string + ".png")
    plt.xlabel('Week')
    plt.ylabel(f'Valid Scores {specific_str.title()}')
    plt.xticks(rotation=45)
    plt.grid(visible=True, linestyle='--', alpha=0.5)
    plt.tight_layout()

    img_name = f"{main_string}.png"
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    if show_fig:
        plt.show()
    return img_name, buffer


class Reporter:
    time_periods = {'day': 1, 'd': 1, 'week': 7, 'w': 7, 'month': 30, 'm': 30, 'year': 365, 'y': 365}
    trend_period = {1: "W", 7: "M", 30: "Y"}

    guilds = {
        1058490579799003187: 'BeanLab',
        927616651409649675: 'CS 110',
        1008806488384483338: 'CS 111',
        747510855536738336: 'CS 235',
        748656649287368704: 'CS 260',
        1128355484039123065: 'CS 312',
    }

    pricing = {
        'gpt-4': [0.03, 0.06],
        'gpt-4o': [0.0025, 0.01],
        'gpt-4-1106-preview': [0.01, 0.03],
        'gpt-4-0125-preview': [0.01, 0.03],
        'gpt-4o-mini': [.000150, .0006],
        'gpt-4-turbo': [0.01, 0.03],
        'gpt-4-turbo-preview': [0.01, 0.03],
        'gpt-3.5-turbo-1106': [0.001, 0.002],
        'gpt-3.5-turbo': [0.001, 0.003]
    }

    # key: what to type after '!report' to display the graph
    # tuple[0]: string required to run the code
    # tuple[1]: description of the graph
    pre_baked = {
        'ftrend percent': (None, "What percent of threads are scored over time?"),
        'ftrend average': (None, "How has the feedback score changed over time?"),
        'f1': ('!report -df feedback -iv feedback_score -p year -ev guild_id -per',
               "What percent of threads are scored by class over the past year?"),
        'f2': ('!report -df feedback -iv feedback_score -p year -ev guild_id -avg',
               "What is the average feedback score by class over the past year?"),
        'u1': ('!report -df usage -iv thread_id -ev hour_of_day -p year -c',
               "What time are threads being opened over the past year?"),
        'u2': ('!report -df usage -iv cost -ev hour_of_day -p year -avg',
               "How expensive is the average thread based on the time of day over the past year?"),
        'u3': ('!report -df usage -iv cost -p year -ev thread_id -avg',
               "What does the distribution of thread cost look like over the past year?"),
        'u4': ('!report -df usage -iv cost -p year -ev guild_id -avg',
               "How expensive is the average thread based on the class over the past year?"),
        'u5': ('!report -df usage -iv thread_id -ev hour_of_day -ev2 guild_id -p year -c',
               "How many threads being opened per class during what time over the past year?")
    }

    def __init__(self, metricsHandler, show_fig=False):
        self.metricsHandler = metricsHandler
        self.show_fig = show_fig

    def select_dataframe(self, desired_df):
        if desired_df == 'feedback':
            data = self.metricsHandler.get_feedback()
        elif desired_df == 'usage':
            data = self.metricsHandler.get_usage()
        elif desired_df == 'messages':
            data = self.metricsHandler.get_message()
        else:
            raise ArgumentError(None, f"Invalid dataframe: {desired_df}")
        return data

    def compute_cost(self, row):
        ip, op = self.pricing.get(row.get('engine', 'gpt-4'), (0, 0))
        return row['input_tokens'] / 1000 * ip + row['output_tokens'] / 1000 * op

    def preprocessing(self, df, args):
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        if args.period:
            now = datetime.now(ZoneInfo('US/Mountain'))
            if args.ind_var == 'timestamp':
                cutoff = self.trend_period[self.time_periods[args.period]]
            else:
                cutoff = now - timedelta(days=self.time_periods[args.period])

            df = df[df['timestamp'] >= cutoff]

        if args.dataframe == 'usage':
            df['cost'] = df.apply(self.compute_cost, axis=1)
            df["hour_of_day"] = df['timestamp'].dt.hour % 24

        if args.exp_var == 'guild_id' or args.exp_var_2:
            df['guild_name'] = df['guild_id'].map(self.guilds)
            df = df.drop(columns=['guild_id'])
            if args.exp_var == 'guild_id':
                args.exp_var = 'guild_name'
            else:
                args.exp_var_2 = 'guild_name'

        # df = df.dropna(subset=[args.ind_var])
        return df

    def catch_known_issues(self, df, args):
        if args.ind_var not in df.columns:
            raise ArgumentError(None, f"Invalid independent variable: {args.ind_var}")

        if args.exp_var and args.exp_var not in df.columns:
            raise ArgumentError(None, f"Invalid explanatory variable: {args.exp_var}")

        if args.period and args.period not in self.time_periods:
            raise ArgumentError(None, f"Invalid time period: {args.period}")

    def prepare_df(self, df, args):
        df = self.preprocessing(df, args)

        self.catch_known_issues(df, args)

        if args.exp_var_2:
            if pd.api.types.is_numeric_dtype(df[args.ind_var]):
                if args.average:
                    df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].mean().reset_index()
                elif args.count:
                    df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].nunique().reset_index()
                elif args.percent:
                    df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].apply(
                        lambda x: x.notna().mean() * 100).reset_index()
                else:
                    df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].sum().reset_index()
            else:
                df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].count().reset_index()

        elif args.exp_var:
            try:
                df[args.ind_var] = pd.to_numeric(df[args.ind_var])
                if args.average:
                    df_grouped = df.groupby(args.exp_var)[args.ind_var].mean().reset_index()
                elif args.count:
                    df_grouped = df.groupby(args.exp_var)[args.ind_var].nunique().reset_index()
                elif args.percent:
                    df_grouped = df.groupby(args.exp_var)[args.ind_var].apply(
                        lambda x: x.notna().mean() * 100).reset_index()
                else:
                    df_grouped = df.groupby(args.exp_var)[args.ind_var].sum().reset_index()
            except ValueError as e:
                df_grouped = df.groupby(args.exp_var)[args.ind_var].count().reset_index()
        else:
            df_grouped = df[args.ind_var].reset_index()

        return df_grouped

    def prettify_graph(self, df, args):
        if args.log:
            plt.yscale('log')

        if args.percent:
            plt.gca().yaxis.set_major_formatter(PercentFormatter())

        # Final df edits
        x_axis = args.exp_var if args.exp_var else 'index'
        df[x_axis] = df[x_axis].astype(str)
        if args.exp_var != 'timestamp' and args.exp_var != 'hour_of_day':
            df.sort_values(args.ind_var, ascending=True, inplace=True)

        # Plotting
        if args.exp_var_2:
            sns.barplot(data=df, x=x_axis, y=args.ind_var, hue=args.exp_var_2)
        else:
            sns.barplot(data=df, x=x_axis, y=args.ind_var, color='b')

        # Labeling
        title = (f"Average " if args.average else "") + (f"Number of " if args.count else "") + (
            f"Percent of " if args.percent else "") + f"{args.ind_var} by {x_axis}" + (
                    f" over the past {args.period}" if args.period else "") + (f" (log scale)" if args.log else "")
        plt.title(title)
        plt.xlabel(x_axis)
        plt.ylabel(args.ind_var)
        plt.tight_layout()

    def make_graph(self, df, args):
        if len(df) == 0:
            raise Exception("The dataframe is empty")

        self.prettify_graph(df, args)

        if self.show_fig:
            plt.show()

        graph_name = f"{args.ind_var}_{args.exp_var or 'index'}_{args.period or 'all'}.png"
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)

        return graph_name, buffer

    def parse_args(self, arg_string):
        """Parse command-line arguments using argparse."""
        args = arg_string.split()
        if args[1] in self.pre_baked:
            args = self.pre_baked[args[1]][0].split()
        sys.argv = args

        parser = ArgumentParser(description="Visualize data from selected metrics.")
        parser.add_argument("-df", "--dataframe", required=True, help="Choose the dataframe.")
        parser.add_argument("-iv", "--ind_var", required=True, help="Independent variable to analyze.")
        parser.add_argument("-p", "--period", choices=self.time_periods.keys(), help="Time period to filter data.")
        parser.add_argument("-ev", "--exp_var", help="Explanatory variable to pivot by.")
        parser.add_argument("-ev2", "--exp_var_2", help="Additional explanatory variable to pivot by.")
        parser.add_argument("-ln", "--log", action="store_true", help="Enable logarithmic scale for the y-axis.")
        parser.add_argument("-avg", "--average", action="store_true", help="Averages, not sums, the ind_var")
        parser.add_argument("-c", "--count", action="store_true", help="Counts, not sums, the ind_var")
        parser.add_argument("-per", "--percent", action="store_true", help="Percent, not sums, the ind_var")
        return parser.parse_args()

    def arg_to_string(self, args):
        components = [args.dataframe, args.ind_var]
        if args.percent:
            components.append("percent")
        if args.count:
            components.append("count")
        components += [attr for attr in [args.exp_var, args.exp_var_2, args.period] if attr]
        if args.log:
            components.append("log_scale")
        return "-".join(components)

    def help_menu(self):
        lines = ["Type '!report', followed by any of the following commands to see the metrics for it:"]
        lines.extend(f"'{key}': {item[1]}" for key, item in self.pre_baked.items())
        return "\n\n".join(lines)

    def get_report(self, arg_string):
        if arg_string == '!report help' or arg_string == '!report h':
            return self.help_menu(), None

        if arg_string == '!report ftrend percent' or arg_string == '!report ftrend average':
            return feed_fancy_graph(self.metricsHandler.get_feedback(), arg_string, self.show_fig)

        args = self.parse_args(arg_string)

        df = self.select_dataframe(args.dataframe)

        df_limited = self.prepare_df(df, args)

        graph_name, graph = self.make_graph(df_limited, args)

        return graph_name, graph


if __name__ == '__main__':
    from pathlib import Path

    metricsHandler = MetricsHandler(Path('./state/metrics'))
    reporter = Reporter(metricsHandler, True)

    for key in reporter.pre_baked:
        sys_string = '!report ' + key
        img_name, image = reporter.get_report(sys_string)

    # # Doing only one graph (for debugging mostly)
    # sys_string = 'feedback average'
    #
    # if sys_string not in reporter.image_cache:
    #     arg_string, image_path = reporter.get_report(sys_string)
    #     reporter.image_cache[sys_string] = image_path
    # else:
    #     image_path = reporter.image_cache[sys_string]
