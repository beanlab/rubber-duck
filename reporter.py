import sys
import pandas as pd
import matplotlib.pyplot as plt

from metrics import MetricsHandler
from argparse import ArgumentParser, ArgumentError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

class csvHandler():
    def __init__(self):
        self.path = "state/metrics/"
        self.df_options = {'feedback', 'usage', 'messages'}

    def select_dataframe(self, desired_df):
        """Load the dataframe based on user input."""
        if desired_df not in self.df_options:
            raise ArgumentError(None, f"Invalid dataframe: {desired_df}")
        return pd.read_csv(f"{self.path}{desired_df}.csv")

class Reporter():
    image_cache = {}

    time_periods = {'day': 1, 'd': 1, 'week': 7, 'w': 7, 'month': 30, 'm': 30, 'year': 365, 'y': 365}

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

    csvHandler = csvHandler()

    def __init__(self, metricsHandler):
        self.metricsHandler = metricsHandler


    def select_dataframe(self, desired_df):
        return self.csvHandler.select_dataframe(desired_df)


    def compute_cost(self, row):
        ip, op = self.pricing.get(row.get('engine', 'gpt-4'), (0,0))
        return row['input_tokens'] / 1000 * ip + row['output_tokens'] / 1000 * op


    def preprocessing(self, df, args):
        if args.dataframe == 'usage':
            df['cost'] = df.apply(self.compute_cost, axis=1)
        return df


    def edit_df(self, df, args):
        """Filter and pivot the dataframe based on user inputs."""
        if args.period:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            now = datetime.now(ZoneInfo('US/Mountain'))
            cutoff = now - timedelta(days=self.time_periods[args.period])
            df = df[df['timestamp'] >= cutoff]

        # df = df.dropna(subset=[args.ind_var])

        if args.exp_var:
            if isinstance(df[args.ind_var], int) or isinstance(df[args.ind_var], float):
                if args.avg:
                    df_grouped = df.groupby(args.exp_var)[args.ind_var].average().reset_index()
                else:
                    df_grouped = df.groupby(args.exp_var)[args.ind_var].sum().reset_index()
            else:
                df_grouped = df.groupby(args.exp_var)[args.ind_var].count().reset_index()
        else:
            df_grouped = df[args.ind_var].reset_index()

        df_pretty = self.prettify_df(df_grouped, args)

        return df_pretty

    ## Not sure the best way to do this, it could turn into a long function of a bunch of if statements if it continues like this
    def prettify_df(self, df, args):
        if args.exp_var == 'guild_id':
            df['guild_name'] = df['guild_id'].map(self.guilds)
            df = df.drop(columns=['guild_id'])#.rename(columns={'guild_name': 'guild_name'})
            args.exp_var = 'guild_name'
        return df


    def visualize_graph(self, df, args):
        if len(df) == 0:
            raise Exception("The dataframe is empty")

        if args.log:
            plt.yscale('log')

        x_axis = args.exp_var if args.exp_var else 'Index'
        df[x_axis] = df[x_axis].astype(str)
        df.sort_values(args.ind_var, ascending=True, inplace=True)

        plt.bar(df[x_axis], df[args.ind_var])
        title = f"{args.ind_var} by {x_axis}" + (f" over the past {args.period}" if args.period else "") + (f" (log scale)" if args.log else "")
        plt.title(title)
        plt.xlabel(x_axis)
        plt.ylabel(args.ind_var)
        plt.tight_layout()

        path = f"./state/graphs/{args.ind_var}_{args.exp_var or 'index'}_{args.period or 'all'}.png"
        plt.savefig(path)


        plt.show()
        return path


    def parse_args(self):
        """Parse command-line arguments using argparse."""
        parser = ArgumentParser(description="Visualize data from selected metrics.")
        parser.add_argument("-df", "--dataframe", required=True, choices=self.csvHandler.df_options, help="Choose the dataframe.")
        parser.add_argument("-iv", "--ind_var", required=True, help="Independent variable to analyze.")
        parser.add_argument("-p", "--period", choices=self.time_periods.keys(), help="Time period to filter data.")
        parser.add_argument("-ev", "--exp_var", help="Explanatory variable to pivot by.")
        parser.add_argument("-ev2", "--exp_var_2", help="Additional explanatory variable to pivot by.")
        parser.add_argument("-ln", "--log", action="store_true", help="Enable logarithmic scale for the y-axis.")
        parser.add_argument("-avg", "--average", action="store_true", help="Averages, not sums, the ind_var")
        return parser.parse_args()


    def arg_to_string(self, args):
        string = args.dataframe + "-" + args.ind_var
        if args.exp_var:
            string += "-" + args.exp_var
        if args.exp_var_2:
            string += "-" + args.exp_var_2
        if args.period:
            string += "-" + args.period
        if args.log:
            string += "-log_scale"
        return string


    def get_report(self, args):
        #First select the dataframe you're interested in seeing
        df = self.select_dataframe(args.dataframe)

        df = self.preprocessing(df, args)

        if args.ind_var not in df.columns:
            raise ArgumentError(None, f"Invalid independent variable: {args.ind_var}")

        if args.exp_var and args.exp_var not in df.columns:
            raise ArgumentError(None, f"Invalid explanatory variable: {args.exp_var}")

        if args.period and args.period not in self.time_periods:
            raise ArgumentError(None, f"Invalid time period: {args.period}")

        df_limited = self.edit_df(df, args)

        return self.visualize_graph(df_limited, args)


if __name__ == '__main__':
    """
    Dr. Bean said an initial approach to the metrics would be to make flags that would specify the data desired.
    So, for example:
    >>> !report -df usage -ind_var cost -p week -exp_var server
    *Spit out an image that shows the last week's cost per server*
    
    Preferably there are some pre-baked reports that should just be accessible with certain key words. IE:
    >>> !report report 1
    *Spit out an image that shows the last week's cost per server*
    
    Additionally, there should be some sort of help menu?
    >>> !report help
    *show the available list of flags and the order they'd need to be processed*
    """
    reporter = Reporter(None)

    sys.argv = ['main.py', '-df', 'feedback', '-iv', 'feedback_score', '-p', 'year', '-ev', 'guild_id', '-ln']
    # sys.argv = ['main.py', '-df', 'usage', '-iv', 'cost', '-ev', 'guild_id', '-ln']
    # sys.argv = ['main.py', '-df', 'usage', '-iv', 'output_tokens', '-p', 'month', '-ev', 'guild_id', '-ln']
    args = reporter.parse_args()
    arg_string = reporter.arg_to_string(args)

    try:
        if arg_string not in reporter.image_cache:
            image_path = reporter.get_report(args)
            reporter.image_cache[arg_string] = image_path
        else:
            image = reporter.image_cache[arg_string]

    except Exception as e:
        print(f"An error occurred: {e}")
