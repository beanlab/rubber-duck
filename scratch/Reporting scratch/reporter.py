import pandas as pd
import matplotlib.pyplot as plt
from reporting_handler import csvHandler

from argparse import ArgumentParser, ArgumentError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

time_periods = {'day': 1, 'd': 1, 'week': 7, 'w': 7, 'month': 30, 'm': 30, 'year': 365, 'y': 365}

csvHandler = csvHandler()

def select_dataframe(desired_df):
    return csvHandler.select_dataframe(desired_df)

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


def edit_df(df, args):
    """Filter and pivot the dataframe based on user inputs."""
    if args.period:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        now = datetime.now(ZoneInfo('US/Mountain'))
        cutoff = now - timedelta(days=time_periods[args.period])
        df = df[df['timestamp'] >= cutoff]

    if args.exp_var:
        if isinstance(df[args.ind_var], int) or isinstance(df[args.ind_var], float):
            df_grouped = df.groupby(args.exp_var)[args.ind_var].sum().reset_index()
        else:
            df_grouped = df.groupby(args.exp_var)[args.ind_var].count().reset_index()
    else:
        df_grouped = df[args.ind_var].reset_index()

    return df_grouped


def visualize_graph(df, args):
    if len(df) == 0:
        raise Exception("The dataframe is empty")

    if args.log:
        plt.yscale('log')

    x_axis = args.exp_var if args.exp_var else 'Index'
    df[x_axis] = df[x_axis].astype(str)
    df.sort_values(args.ind_var, ascending=True, inplace=True)

    plt.bar(df[x_axis], df[args.ind_var])
    title = f"{args.ind_var} by {x_axis}" + (f" over the past {args.period}" if args.period else "") + (f"(log scale)" if args.log else "")
    plt.title(title)
    plt.xlabel(x_axis)
    plt.ylabel(args.ind_var)
    plt.tight_layout()
    plt.show()

    path = f"graphs/{args.ind_var}_{args.exp_var or 'index'}_{args.period or 'all'}.png"
    plt.savefig(path)
    return path

def parse_args():
    """Parse command-line arguments using argparse."""
    parser = ArgumentParser(description="Visualize data from selected metrics.")
    parser.add_argument("-df", "--dataframe", required=True, choices=csvHandler.df_options, help="Choose the dataframe.")
    parser.add_argument("-iv", "--ind_var", required=True, help="Independent variable to analyze.")
    parser.add_argument("-p", "--period", choices=time_periods.keys(), help="Time period to filter data.")
    parser.add_argument("-ev", "--exp_var", help="Explanatory variable to pivot by.")
    parser.add_argument("-ev2", "--exp_var_2", help="Additional explanatory variable to pivot by.")
    parser.add_argument("-ln", "--log", action="store_true", help="Enable logarithmic scale for the y-axis.")
    return parser.parse_args()


def arg_to_string(args):
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

def main(args):
    #First select the dataframe you're interested in seeing
    df = select_dataframe(args.dataframe)

    if args.ind_var not in df.columns:
        raise ArgumentError(None, f"Invalid independent variable: {args.ind_var}")

    if args.exp_var and args.exp_var not in df.columns:
        raise ArgumentError(None, f"Invalid explanatory variable: {args.exp_var}")

    if args.period and args.period not in time_periods:
        raise ArgumentError(None, f"Invalid time period: {args.period}")

    df_limited = edit_df(df, args)

    return visualize_graph(df_limited, args)

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
    iters = 0
    while iters < 1:
        iters += 1
        # args = "-df usage -iv output_tokens -p month -ev guild_id"
        args = parse_args()
        arg_string = arg_to_string(args)
        try:
            if arg_string not in image_cache:
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
