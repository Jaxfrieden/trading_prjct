import streamlit as st
import pandas as pd
import datetime
import yfinance as yf

# Function to fetch stock data
def fetch_stock_data(ticker, start_date, end_date, rolling_window):
    start_date_with_buffer = (pd.to_datetime(start_date) - pd.tseries.offsets.BDay(rolling_window+1)).strftime('%Y-%m-%d')
    adjusted_end_date = (pd.to_datetime(end_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    data = yf.download(ticker, start=start_date_with_buffer, end=adjusted_end_date)
    if data.empty:
        st.error("No data found for the specified ticker and date range.")
        st.stop()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
    return data

# Calculate Rolling Avg and Daily Returns
def calculate_rolling_avg_volume(data, start_date, rolling_window):
    data[f'{rolling_window}Day_Avg_Volume'] = data['Volume'].rolling(window=rolling_window, min_periods=rolling_window).mean().shift(1)
    data['Daily_Return'] = data['Close'].pct_change(periods=1) * 100
    data = data[data.index >= pd.to_datetime(start_date)].dropna()
    return data

# Identify Breakout Days
def identify_breakout_days(data, volume_threshold, price_threshold, rolling_window):
    data['Volume_Breakout'] = data['Volume'] > (volume_threshold / 100) * data[f'{rolling_window}Day_Avg_Volume']
    data['Price_Breakout'] = data['Daily_Return'] > price_threshold
    data['Breakout_Day'] = data['Volume_Breakout'] & data['Price_Breakout']
    return data

# Calculate Holding Returns
# def calculate_holding_returns(data, holding_period):
#     breakout_days = data[data['Breakout_Day']].copy()
#     breakout_days['Buy_Price'] = breakout_days['Close']
#     breakout_days['Sell_Price'] = data['Close'].shift(-holding_period).loc[breakout_days.index]
#     breakout_days['Return'] = ((breakout_days['Sell_Price'] - breakout_days['Buy_Price']) / breakout_days['Buy_Price']) * 100
#     return breakout_days
def calculate_holding_returns(data, holding_period):
    breakout_days = data[data['Breakout_Day']].copy()
    breakout_days['Buy_Price'] = breakout_days['Close']
    sell_prices = []

    for breakout_date in breakout_days.index:
        future_dates = data.loc[breakout_date:].iloc[1:holding_period+1]['Close']
        sell_price = future_dates.iloc[-1] if not future_dates.empty else None
        sell_prices.append(sell_price)

    breakout_days['Sell_Price'] = sell_prices
    breakout_days['Return'] = ((breakout_days['Sell_Price'] - breakout_days['Buy_Price']) / breakout_days['Buy_Price']) * 100
    breakout_days = breakout_days.dropna(subset=['Sell_Price'])
    return breakout_days


# Streamlit UI
st.title("Stock Breakout Analysis Tool")

# User Inputs
ticker = st.text_input("Enter stock ticker (e.g., AAPL, NVDA):", "NVDA").upper()

# Restrict end date to today and start date to any past date
today = datetime.date.today()
start_date = st.date_input("Enter start date (any valid past date):", value=today - pd.Timedelta(days=300), max_value=today)
end_date = st.date_input("Enter end date (cannot be in the future):", value=today, min_value=start_date, max_value=today)

volume_threshold = st.number_input(
    "Volume breakout threshold (must be > 100%):",
    min_value=100.1, value=200.0, step=0.1
)

price_threshold = st.number_input(
    "Price breakout threshold (must be > 0%):",
    min_value=0.1, value=2.0, step=0.1
)

holding_period = st.number_input(
    "Holding period in days (must be >= 1):",
    min_value=1, value=10, step=1
)

rolling_window = st.number_input(
    "Rolling window for lookback period (must be > 1):",
    min_value=2, value=20, step=1
)

if st.button("Run Analysis"):
    try:
        # Fetch and process data
        data = fetch_stock_data(ticker, start_date, end_date, rolling_window)
        data = calculate_rolling_avg_volume(data, start_date, rolling_window)
        data = identify_breakout_days(data, volume_threshold, price_threshold, rolling_window)
        results = calculate_holding_returns(data, holding_period)

        # Filter the displayed columns
        displayed_columns = ['Close', 'Volume', f'{rolling_window}Day_Avg_Volume', 'Daily_Return',
                             'Buy_Price', 'Sell_Price', 'Return']
        display_results = results[displayed_columns].dropna()

        # Display Results
        st.subheader("Breakout Days with Returns and Metrics:")
        st.dataframe(display_results)

        # Prepare CSV for download
        csv = display_results.to_csv(index=True).encode('utf-8')
        st.download_button("Download Results as CSV", csv, "breakout_results.csv", "text/csv")
    except Exception as e:
        st.error(f"Error: {e}")
