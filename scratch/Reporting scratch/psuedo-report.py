from argparse import ArgumentError

import pandas as pd


def select_dataframe(desired_df):
    # Choose the dataframe from different options (ie feedback.csv, messages.csv, usage.csv)
    # Load the csv into a pandas dataframe to return
    df_options = {'feedback', 'usage', 'messages'}

    if desired_df not in df_options:
        raise ArgumentError(f"Invalid argument: {desired_df}")
    else:
        return pd.read_csv(f"./sample_metrics/{desired_df}.csv")


def variable_of_interest(df, args):
    #From the dataframe, get the headers and validate the variable of interest
    if args[1] in df.columns:
        return args[1]
    else:
        raise ArgumentError(f"Invalid argument: '{args[1]}' is not in the df {args[0]}")


def select_timeframe(df):
    pass


def select_pivot(df, ind_var):
    pass


def trim_df(df, ind_var, period, exp_var):
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
    period = select_timeframe(df)

    #(Optionally) choose whatever else you want to see it by
    exp_var = select_pivot(df, ind_var)

    #Restrict the dataframe
    df_limited = trim_df(df, ind_var, period, exp_var)

    #Finally visualize the data (and send it to discord?)
    return visualize_graph(df_limited, ind_var, exp_var)


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
    while arg_string is not 'quit':
        # arg_string = input("What would you like to see? ")
        arg_string = "feedback cost week server"
        args = arg_string.split(" ")
        try:
            if arg_string not in image_cache:
                image = main(args)
                image_cache[arg_string] = image
            else:
                image = image_cache[arg_string]
        except ArgumentError as e:
            image_cache[arg_string] = f'invalid argument: {e}'
            print(e)
