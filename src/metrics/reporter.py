import io
import json
import sys
from argparse import ArgumentParser, ArgumentError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import PercentFormatter
from quest import wrap_steps

from ..storage.sql_metrics import SQLMetricsHandler
from ..utils.config_types import ServerConfig
from ..utils.logger import duck_logger


def fancy_preproccesing(df, channels):
    if df == [['No data available']]:
        raise Exception('No data available')

    if isinstance(df, list):
        # Use first row as column names
        columns = df[0]
        df = pd.DataFrame(df[1:], columns=columns)

    duck_logger.debug("Starting fancy preprocessing of feedback data")

    df['channel_name'] = df['parent_channel_id'].map(channels)  # Map parent_channel_id to channel names
    df = df.drop(columns=['parent_channel_id'])
    return (df.set_index(pd.DatetimeIndex(pd.to_datetime(df['timestamp'], utc=True)))
            .groupby('channel_name')
            .resample('W')
            .agg(
        avg_score=('feedback_score', lambda x: pd.to_numeric(x, errors='coerce').mean()),
        valid_scores_pct=('feedback_score', lambda x: pd.to_numeric(x, errors='coerce').notna().mean() * 100)
    )
            .reset_index()
            )


def feed_fancy_graph(channels, df_feedback, arg_string, show_fig) -> tuple[str, io.BytesIO]:
    specific_str = arg_string.split()[2]
    df = fancy_preproccesing(df_feedback, channels)

    # Plot the percentage of valid scores each week
    plt.figure(figsize=(10, 6))
    if specific_str == 'percent':
        sns.lineplot(data=df, x='timestamp', y='valid_scores_pct', marker='o', color='orange', hue='channel_name')
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
    plt.close()
    return img_name, buffer



class Reporter:
    time_periods = {'day': 1, 'd': 1, 'week': 7, 'w': 7, 'month': 30, 'm': 30, 'year': 365, 'y': 365}
    trend_period = {1: "W", 7: "M", 30: "Y"}

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
        # 'all': (None, 'All the following charts.'),
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

    def __init__(self, SQLMetricsHandler, server_config:ServerConfig, show_fig=False):
        self.SQLMetricsHandler = SQLMetricsHandler
        wrap_steps(self.SQLMetricsHandler, ["record_message", "record_usage", "record_feedback"])

        self.show_fig = show_fig
        self._reporting_config = self._make_reporting_config(server_config)
        # Create a flat mapping of channel IDs to channel names
        self._channels = {}
        for server_channels in self._reporting_config.values():
            self._channels.update({int(channel_id): channel_name for channel_id, channel_name in server_channels.items()})

    def _make_reporting_config(self, server_config:ServerConfig) -> dict:
        """This function converts the server_config into a dictionary that maps server names to their channels."""
        reporting_config = {}
        for server in server_config.values():
            server_name = server['server_name']
            channel_dict = {}
            for channel in server['channels']:
                channel_id = channel['channel_id']
                channel_name = channel['channel_name']
                channel_dict[channel_id] = channel_name
            reporting_config[server_name] = channel_dict
        return reporting_config

    def select_dataframe(self, desired_df):
        if desired_df == 'feedback':
            data = self.SQLMetricsHandler.get_feedback()
        elif desired_df == 'usage':
            data = self.SQLMetricsHandler.get_usage()
        elif desired_df == 'messages':
            data = self.SQLMetricsHandler.get_message()
        else:
            raise ArgumentError(None, f"Invalid dataframe: {desired_df}")
        
        # Convert list to DataFrame if necessary
        if isinstance(data, list):
            # Use first row as column names
            columns = data[0]
            data = pd.DataFrame(data[1:], columns=columns)
        return data

    def compute_cost(self, row):
        ip, op = self.pricing.get(row.get('engine', 'gpt-4'), (0, 0))
        return row['input_tokens'] / 1000 * ip + row['output_tokens'] / 1000 * op

    def preprocessing(self, df, args):
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df["hour_of_day"] = (df[
                                     'timestamp'].dt.hour - 7) % 24  # TODO: adjust both the timestamp and hour_of_day by the right time

        if args.period:
            now = datetime.now(ZoneInfo('US/Mountain'))
            if args.ind_var == 'timestamp':
                cutoff = self.trend_period[self.time_periods[args.period]]
            else:
                cutoff = now - timedelta(days=self.time_periods[args.period])

                df = df[df['timestamp'] >= cutoff]

        if args.dataframe == 'usage':
            df['cost'] = df.apply(self.compute_cost, axis=1)

        if args.exp_var == 'guild_id' or args.exp_var_2 == 'guild_id':
            duck_logger.debug(f"Available channel_ids in data: {df['parent_channel_id'].unique()}")
            duck_logger.debug(f"Available channel mappings: {self._channels}")
            df['channel_name'] = df['parent_channel_id'].map(self._channels)
            duck_logger.debug(f"Channel names after mapping: {df['channel_name'].unique()}")
            df = df.drop(columns=['guild_id'])
            if args.exp_var == 'guild_id':
                args.exp_var = 'channel_name'
            else:
                args.exp_var_2 = 'channel_name'

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
            if not pd.api.types.is_numeric_dtype(df[args.ind_var]):
                df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].count().reset_index()
            elif args.average:
                df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].mean().reset_index()
            elif args.count:
                df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].nunique().reset_index()
            elif args.percent:
                df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].apply(
                    lambda x: x.notna().mean() * 100).reset_index()
            else:
                df_grouped = df.groupby([args.exp_var, args.exp_var_2])[args.ind_var].sum().reset_index()

        elif args.exp_var:
            try:
                df[args.ind_var] = pd.to_numeric(df[args.ind_var], errors='coerce')
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
                duck_logger.error(f"Error converting {args.ind_var} to numeric: {e}")
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
        self.prettify_graph(df, args)

        # Get the current figure
        fig = plt.gcf()
        
        # Ensure the plot is rendered
        fig.canvas.draw()
        
        # Save to buffer
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        
        # Show the plot if requested
        if self.show_fig:
            plt.show()
        
        plt.close()
        return f"{args.ind_var}_{args.exp_var or 'index'}_{args.period or 'all'}.png", buffer

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

    def get_all_prebaked(self):
        imgs = []
        titles = []
        for key in self.pre_baked:
            if len(imgs) == 10:  # Discord's limit of number of images you can send at once
                break
            if key != 'all':
                sys_string = '!report ' + key
                title, image = self.get_report(sys_string)
                imgs.append(image)
                titles.append(title)
        return imgs, titles

    def get_report(self, arg_string) -> tuple[str, io.BytesIO]:
        try:
            # if arg_string == '!report all': #TODO: get working
            #     return self.get_all_prebaked()
            if arg_string == '!report help' or arg_string == '!report h':
                return self.help_menu(), None

            if arg_string == '!report ftrend percent' or arg_string == '!report ftrend average':
                return feed_fancy_graph(self._channels, self.SQLMetricsHandler.get_feedback(), arg_string, self.show_fig)

            args = self.parse_args(arg_string)

            df = self.select_dataframe(args.dataframe)
            df_limited = self.prepare_df(df, args)
            
            if len(df_limited) == 0:
                return "No data available for this plot.", None

            return self.make_graph(df_limited, args)

        except Exception as e:
            # Ensure any matplotlib figures are closed
            plt.close('all')
            raise  # Re-raise the exception to be handled by the caller


    def interactive_report(self):
        # Interactive report selection loop
        print("\nAvailable reports:")
        for key, (_, description) in self.pre_baked.items():
            print(f"  {key}: {description}")
        print("\nType 'help' to see this menu again")
        print("Type 'exit' to quit")
        while True:
            command = input("\nEnter report command (or 'help'/'exit'): ").strip()
            
            if command.lower() == 'exit':
                break
            elif command.lower() == 'help':
                print("\nAvailable reports:")
                for key, (_, description) in self.pre_baked.items():
                    print(f"  {key}: {description}")
                continue
            
            # Check if it's a pre-baked command
            if command in self.pre_baked:
                command = self.pre_baked[command][0]  # Get the actual command string
                if command is None:  # Handle special cases like ftrend
                    command = f"!report {command}"
            else:
                print(f"Unknown command: {command}")
                print("Type 'help' to see available commands")
                continue
            
            # Add !report prefix if not present
            if not command.startswith('!report'):
                command = f"!report {command}"
            
            print(f"Running command: {command}")  # Debug print
            self.get_report(command)



if __name__ == '__main__':
    from pathlib import Path
    import argparse
    from src.storage.sql_connection import create_sql_session

    # Load environment variables from .env file
    project_root = Path(__file__).parent.parent.parent
    env_files = list(project_root.glob('*env'))
    if env_files:
        load_dotenv(env_files[0])  # Load the first env file found
    else:
        print("Warning: No .env file found in project root")

    parser = argparse.ArgumentParser(description='Run reporter with specified config')
    parser.add_argument('--config', type=str, help='Path to config.json file')
    args = parser.parse_args()

    this_file = Path(__file__)
    project_root = this_file.parent.parent.parent  # Go up three levels to reach project root

    # Use provided config path or fall back to default
    config_path = Path(args.config) if args.config else project_root / 'config.json'
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path}")

    config = json.loads(config_path.read_text())
    
    # Create SQL session and initialize handler
    db_name = os.getenv('DB_NAME')  # Get DB_NAME from env
    metrics_db_path = project_root / db_name
    session = create_sql_session({'db_type': 'sqlite', 'database': str(metrics_db_path)})
    SQLMetricsHandler = SQLMetricsHandler(session)
    
    reporter = Reporter(SQLMetricsHandler, config['reporting'], show_fig=True)

    reporter.interactive_report()
