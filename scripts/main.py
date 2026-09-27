# %%
from pathlib import Path
import polars as pl
import numpy as np
import pandas as pd
from plotnine import ggplot, aes, geom_segment, geom_point, labs, theme_minimal,facet_wrap,scale_color_manual,theme, element_rect, element_line
"""
LEADING QUESTION: What is the monetary difference caused by the by-hand input FX rates instead of autmatic pull?
"""

#read in data
DATA_DIR = Path.cwd().parent / "data" if "file" not in locals() else Path(__file__).resolve().parent.parent / "data"
transactions_df = pd.read_csv(DATA_DIR / "raw" / "transactions_q3_2024.csv")
nbp_rates_df = pd.read_csv(DATA_DIR / "raw" / "nbp_rates_q3_2024.csv")
# %%
#eye check
print('---NBP RATES---:')
print(nbp_rates_df.head())
print(nbp_rates_df.tail())

print('---TRANSACTIONS---:')
print(transactions_df.head())
print(transactions_df.tail())

# %%
#quantitive check
print('---NBP RATES---: ')
print('Num of rows: ', nbp_rates_df.shape[0])
print('Num of columns: ', nbp_rates_df.shape[1])
print('Nulls: ', nbp_rates_df.isna().sum())
print('DataType: ', nbp_rates_df.dtypes)

print('---TRANSACTIONS---: ')
print('Num of rows: ', transactions_df.shape[0])
print('Num of columns: ', transactions_df.shape[1])
print('Nulls: ', transactions_df.isna().sum())
print('DataType: ', transactions_df.dtypes)

#Worth noting: no nulls overall, dates as strings, everything else seems to be as expected

# %%
#convet dates to datetime
nbp_rates_df['effective_date'] = pd.to_datetime(nbp_rates_df['effective_date'])
transactions_df['booking_date'] = pd.to_datetime(transactions_df['booking_date'])

nbp_rates_df.sort_values(by='effective_date',inplace=True)
transactions_df.sort_values(by='booking_date',inplace=True)
#Extract columns of interest (declutter the data)
transcations_decluttered_df = transactions_df[['transaction_id', 'booking_date','currency', 'amount_foreign', 'budget_rate_pln']].assign(total_amount_pln=transactions_df['amount_foreign'] * transactions_df['budget_rate_pln'])
transcations_decluttered_df = pd.merge_asof(transactions_df,nbp_rates_df,left_on='booking_date',right_on='effective_date',by='currency',direction='backward')

transcations_decluttered_df['budget_total_pln'] = transcations_decluttered_df['amount_foreign']*transcations_decluttered_df['budget_rate_pln']
transcations_decluttered_df['actual_nbp_total_pln'] = transcations_decluttered_df['amount_foreign']*transcations_decluttered_df['nbp_mid_rate']
transcations_decluttered_df['unit_exchange_difference'] = transcations_decluttered_df['budget_rate_pln']-transcations_decluttered_df['nbp_mid_rate']
transcations_decluttered_df['total_exchange_difference'] = transcations_decluttered_df['unit_exchange_difference']*transcations_decluttered_df['amount_foreign']
transcations_decluttered_df['total_absolute_difference'] = abs(transcations_decluttered_df['unit_exchange_difference']*transcations_decluttered_df['amount_foreign'])
print(transcations_decluttered_df)
total_difference = transcations_decluttered_df['total_exchange_difference'].sum()
print(total_difference)
transcations_decluttered_df.to_csv(DATA_DIR / 'clean' / 'transactions_matched.csv')
#Performed sampled comparison to see if the results were properly matched, checked number of rows to see if anythings missing
# %%
#Calculate the mean absolute deviation

transcations_decluttered_df['MAD'] = transcations_decluttered_df['total_absolute_difference'].mean()
transcations_decluttered_df['average_percent_of_transactions'] = ((transcations_decluttered_df['MAD'].div(transcations_decluttered_df['budget_total_pln'])).mul(100)).mean()
print(transcations_decluttered_df['MAD'])
print(transcations_decluttered_df['average_percent_of_transactions'])

# %% 
#creating the plot
#ordering the currencies so that gbp (the one that's worth most) is at the top
transcations_decluttered_df['currency'] = pd.Categorical(
    transcations_decluttered_df['currency'],
    categories=['GBP', 'EUR', 'USD'],
    ordered=True
)
p = (
    ggplot(transcations_decluttered_df) 
    + aes(x='booking_date') 
    # Dumbbell connector line
    + geom_segment(
        aes(xend='booking_date', y='budget_rate_pln', yend='nbp_mid_rate'),
        color='gray',
        size=1
    )
    # Points with mapped color labels 
    + geom_point(aes(y='budget_rate_pln', color='"Budget Rate"'), size=3)
    + geom_point(aes(y='nbp_mid_rate', color='"NBP Mid Rate"'), size=3)
    
    #Separate each currency into its own panel with custom Y-axis limits
    + facet_wrap('~currency', scales='free_y', ncol=1)
    
    # Set explicit legend colors matching your scheme
    + scale_color_manual(values={'Budget Rate': '#d95f02', 'NBP Mid Rate': '#1b9e77'})
    
    + labs(
        title='FX Rate Variance: Manual Budget Rate vs Official NBP Rate',
        x='Transaction Date',
        y='Exchange Rate (PLN)',
        color='Rate Source'
    )
    + theme_minimal()
    + theme(
        panel_border=element_rect(color='#d0d0d0', fill=None, size=1),
        axis_line=element_line(color='#888888', size=0.5),
        panel_grid_minor=element_line(color='#f5f5f5')
    )
)
p.save(DATA_DIR.parent / "outputs" / "fx_variance_dumbbell.png", width=10, height=6, dpi=300)