from argparse import ArgumentError

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

time_periods = {'day': 1, 'd': 1, 'week': 7, 'w': 7, 'month': 30, 'm': 30, 'year': 365, 'y': 365}
df_options = {'feedback', 'usage', 'messages'}


def select_dataframe(desired_df):
    # Choose the dataframe from different options (ie feedback.csv, messages.csv, usage.csv)
    # Load the csv into a pandas dataframe to return
    # TODO: get an actual metrics handler that will take care of finding the files
    if desired_df not in df_options:
        raise ArgumentError(desired_df, f"Invalid dataframe argument: {desired_df}")
    else:
        return pd.read_csv(f"./sample_metrics/{desired_df}.csv")


def variable_of_interest(df, args):
    #From the dataframe, get the headers and validate the variable of interest
    ind_var = args[1]
    if ind_var in df.columns:
        return ind_var
    else:
        raise ArgumentError(ind_var, f"Invalid argument: '{ind_var}' is not in the df {args[0]}")


def select_timeframe(df, args):
    period = args[2]
    if period in time_periods:
        return period
    elif args[2] in df.columns: ## In case they just chose to see the data outside any time period
        return None
    else:
        raise ArgumentError(period, f"Invalid argument: '{period}' is not a valid time period (day, week, month, year)")


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
    # Valid options: df ind_var period, df ind_var exp_var, df ind_var period exp_var

    if period and exp_var is None:
        # We want a chart/table of a sum/avg of the ind_var
        df_summary = df
        pass


    if period is None:
        # we want to see the ind_var by the sum/avg/etc of the exp_var
        pass

    elif exp_var is None:
        # we want to see the ind_var by the sum/avg/etc over the smaller time period (ie. summary of the month by weekly data, weekly by daily, etc).
        pass


    elif period is not None and exp_var is not None:
        #Select only the data within the proper time period
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        now = datetime.now(ZoneInfo('US/Mountain'))
        one_period_ago = now - timedelta(days=time_periods[period])
        df_period_fitted = df[df['timestamp'] >= one_period_ago]

        #Pivot the data by the exp_var
        return df_period_fitted
    #this below part will select only the data that fits in the time period
    return None


def visualize_graph(df_limited, ind_var, exp_var, period):
    graph = None
    if len(df_limited) == 0:
        raise Exception("The dataframe is empty")

    final_df = df_limited.groupby([exp_var])[ind_var].sum().reset_index()

    print(final_df)
    #Stop iteration error with the below code
    sns.barplot(
        data=final_df,
        x=exp_var,
        y=ind_var
    )

    title_string = f'{ind_var} by {exp_var}'
    title_string += f' over the past {period}' if period is not None else ''
    plt.title(title_string)

    plt.show()

    return graph


def main(args):
    #First select the dataframe you're interested in seeing
    df = select_dataframe(args[0])

    #Then select the variable you're interested in from the dataframe
    ind_var = variable_of_interest(df, args)

    #Next choose the time frame you're wanting to see it by
    period = select_timeframe(df, args)

    #(Optionally) choose whatever else you want to see it by (the explanatory variable)
    exp_var = select_pivot(df, ind_var, period, args)

    #Restrict the dataframe
    df_limited = trim_df(df, period, ind_var, exp_var)

    #Finally visualize the data (and send it to discord?)
    return visualize_graph(df_limited, ind_var, exp_var, period)

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
        arg_string = "usage output_tokens month guild_id"
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

        except StopIteration as e:
            print(f"Error: {e}")
            break

        except Exception as e:
            print(f"An error occurred: {e}")
            break
