Trading Strategy:
- buys market open momentum

General Action Taken:
- Console based ticker input
- Grabs last one minute, pre-market candle and stores close of candle, using realtime bar data
- A buy order is triggered if current tick price is greater than the previous close
- Custom bracket orders for selling if tick price experiences a loss of momentum

Notes:
- More bug fixing is needed, but main logic is there
