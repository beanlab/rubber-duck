import pandas as pd
import matplotlib.pyplot as plt

from argparse import ArgumentParser, ArgumentError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

time_periods = {'day': 1, 'd': 1, 'week': 7, 'w': 7, 'month': 30, 'm': 30, 'year': 365, 'y': 365}
df_options = {'feedback', 'usage', 'messages'}


def select_dataframe(desired_df):
    """Load the dataframe based on user input."""
    if desired_df not in df_options:
        raise ArgumentError(None, f"Invalid dataframe: {desired_df}")
    return pd.read_csv(f"./sample_metrics/{desired_df}.csv")


def select_pivot(df, ind_var, period, args):
    if period is None:
        exp_var = args[2]
        if exp_var in df.columns:
            if exp_var != ind_var:
                return exp_var
            else:
                raise ArgumentError(exp_var, f"Invalid argument: cannot pivot '{exp_var}' by itself")
        else:
            raise ArgumentError(exp_var,f"Invalid argument: '{exp_var}' is not a variable of the df {args[0]}")
    else:
        if len(args) < 4:
            return None #We'll later use the period as the exp_var in this case
        else:
            exp_var = args[3]
            if exp_var not in df.columns:
                raise ArgumentError(exp_var, f"Invalid argument: '{exp_var}' is not a variable of the df {args[0]}")
            return exp_var


def trim_df(df, period, ind_var, exp_var):
    """Filter and pivot the dataframe based on user inputs."""
    if period:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        now = datetime.now(ZoneInfo('US/Mountain'))
        cutoff = now - timedelta(days=time_periods[period])
        df = df[df['timestamp'] >= cutoff]

    if exp_var:
        if isinstance(df[ind_var], int) or isinstance(df[ind_var], float):
            df_grouped = df.groupby(exp_var)[ind_var].sum().reset_index()
        else:
            df_grouped = df.groupby(exp_var)[ind_var].count().reset_index()
    else:
        df_grouped = df[ind_var].reset_index()

    return df_grouped


def visualize_graph(df, ind_var, exp_var, period):
    if len(df) == 0:
        raise Exception("The dataframe is empty")

    x_axis = exp_var if exp_var else 'Index'
    df[x_axis] = df[x_axis].astype(str)
    df.sort_values(ind_var, ascending=True, inplace=True)

    plt.bar(df[x_axis], df[ind_var])
    title = f"{ind_var} by {x_axis}" + (f" over the past {period}" if period else "")
    plt.title(title)
    plt.xlabel(x_axis)
    plt.ylabel(ind_var)
    plt.tight_layout()
    plt.show()

    path = f"graphs/{ind_var}_{exp_var or 'index'}_{period or 'all'}.png"
    plt.savefig(path)
    return path

def parse_args():
    """Parse command-line arguments using argparse."""
    parser = ArgumentParser(description="Visualize data from selected metrics.")
    parser.add_argument("-df", "--dataframe", required=True, choices=df_options, help="Choose the dataframe.")
    parser.add_argument("-iv", "--ind_var", required=True, help="Independent variable to analyze.")
    parser.add_argument("-p", "--period", choices=time_periods.keys(), help="Time period to filter data.")
    parser.add_argument("-ev", "--exp_var", help="Explanatory variable to pivot by.")
    parser.add_argument("-ev2", "--exp_var_2", help="Additional explanatory variable to pivot by.")
    return parser.parse_args()


def arg_to_string(args):
    string = args.dataframe + "-" + args.ind_var
    if args.exp_var:
        string += "-" + args.exp_var
    if args.exp_var_2:
        string += "-" + args.exp_var_2
    if args.period:
        string += "-" + args.period
    return string

def main(args):
    #First select the dataframe you're interested in seeing
    df = select_dataframe(args.dataframe)

    if args.ind_var not in df.columns:
        raise ArgumentError(None, f"Invalid independent variable: {args.ind_var}")

    if args.exp_var and args.exp_var not in df.columns:
        raise ArgumentError(None, f"Invalid explanatory variable: {args.exp_var}")

    if args.period and args.period not in time_periods:
        raise ArgumentError(None, f"Invalid time period: {args.period}")

    df_limited = trim_df(df, args.period, args.ind_var, args.exp_var)

    return visualize_graph(df_limited, args.ind_var, args.exp_var, args.period)

if __name__ == '__main__':
    """
    Dr. Bean said an initial approach to the metrics would be to make flags that would specify the data desired.
    So, for example:
    >>> !report cost week server
    *Spit out an image that shows the last week's cost per server
    
    Additionally, there would be some sort of help menu
    >>> !report help
    *show the available list of flags and the order they'd need to be processed
    """
    arg_string = None
    image_cache = {}
    while arg_string != 'quit':
        # args = "-df usage -iv output_tokens -p month -ev guild_id"
        args = parse_args()
        arg_string = arg_to_string(args)
        try:
            if arg_string not in image_cache:
                # TODO: get an actual metrics handler that will take care of finding the files
                image_path = main(args)
                image_cache[arg_string] = image_path
            else:
                image = image_cache[arg_string]
        except ArgumentError as e:
            image_cache[args] = f'invalid argument: {e}'
            print(e)

        except StopIteration as e:
            print(f"Error: {e}")
            break

        except Exception as e:
            print(f"An error occurred: {e}")
            break
