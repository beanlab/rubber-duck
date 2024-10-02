from argparse import ArgumentError

import pandas as pd
from datetime import datetime, timedelta

time_periods = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
df_options = {'feedback', 'usage', 'messages'}


def select_dataframe(desired_df):
    # Choose the dataframe from different options (ie feedback.csv, messages.csv, usage.csv)
    # Load the csv into a pandas dataframe to return
    if desired_df not in df_options:
        raise ArgumentError(desired_df, f"Invalid argument: {desired_df}")
    else:
        return pd.read_csv(f"./sample_metrics/{desired_df}.csv")


def variable_of_interest(df, args):
    #From the dataframe, get the headers and validate the variable of interest
    ind_var = args[1]
    if ind_var in df.columns:
        return args[1]
    else:
        raise ArgumentError(ind_var, f"Invalid argument: '{ind_var}' is not in the df {args[0]}")


def select_timeframe(df, args):
    period = args[2]
    if period in time_periods:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        now = datetime.now()
        one_week_ago = now - timedelta(days=time_periods[args[2]])

        return df[df['timestamp'] >= one_week_ago], period
    elif args[2] in df.columns: ## In the case that they just chose to see the data outside any time period
        return None
    else:
        raise ArgumentError(period, f"Invalid argument: '{period}' is not a valid time period (day, week, month, year)")


def select_pivot(df, ind_var, args):
    # If the period == None
    # exp_var = args[2]
    pass


def trim_df(df, ind_var, period, exp_var):
    # if period != None and exp_var == None
    # We want a chart of week to week, month to month sum/avg of the ind_var

    # if period == None
    # we want to see the ind_var by the sum/avg/etc of the exp_var

    #if period != None and exp_var != None
    #this below part will select only the data that fits in the time period

    # df['timestamp'] = pd.to_datetime(df['timestamp'])
    # now = datetime.now()
    # one_period_ago = now - timedelta(days=period)
    # return df[df['timestamp'] >= one_period_ago]
    pass


def visualize_graph(df_limited, ind_var, exp_var):
    graph = None

    return graph


def main(args):
    #First select the dataframe you're interested in seeing
    df = select_dataframe(args[0])

    #Then select the variable you're interested in from the dataframe
    ind_var = variable_of_interest(df, args)

    #Next choose the time frame you're wanting to see it by
    period = select_timeframe(df, args)

    #(Optionally) choose whatever else you want to see it by
    dep_var = select_pivot(df, ind_var, args)

    #Restrict the dataframe
    df_limited = trim_df(df, period, ind_var, dep_var)

    #Finally visualize the data (and send it to discord?)
    return visualize_graph(df_limited, ind_var, dep_var)

def process_args(args):
    # Maybe be a place to seperate the logic for help, quit, etc
    pass


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
        # arg_string = input("What would you like to see? ")
        arg_string = "feedback cost week server"
        args = arg_string.split(" ")
        if len(args) < 3:
            print("Not enough arguments (df independent_variable time_period")
            continue
        try:
            if arg_string not in image_cache:
                image = main(args)
                image_cache[arg_string] = image
            else:
                image = image_cache[arg_string]
        except ArgumentError as e:
            image_cache[arg_string] = f'invalid argument: {e}'
            print(e)
