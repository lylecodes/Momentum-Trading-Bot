import ibapi
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import *
from datetime import datetime, timedelta
import math
import threading
import numpy as np
import pandas as pd
import time
import pytz

orderId = 1

class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    # Error handler
    def error(self, reqId, errorCode, errorString):
        print("Error: ", reqId, " ", errorCode, " ", errorString)

    def nextValidId(self, nextorderId):
        global orderId
        orderId = nextorderId

    # Get Tick Data
    def tickByTickAllLast(self, reqId, tickType, time, price, size,
                          tickAtrribLast, exchange, specialConditions):
        super().tickByTickAllLast(reqId, tickType, time, price, size, tickAtrribLast,
                                  exchange, specialConditions)
        try:
            bot.tick_data_handler(reqId, price, time)
        except Exception as e:
            print(e)

    # Get Historical Data
    def historicalData(self, reqId, bar):
        try:
            bot.on_bar_update(reqId,bar,False)
        except Exception as e:
            print(e)

    # End Historical Data
    def historicalDataEnd(self, reqId, start, end):
        print("HistoricalDataEnd. ReqId:", reqId, "from", start, "to", end)
        print("=================================================================================")

    def historicalDataUpdate(self, reqId, bar):
        try:
            bot.on_bar_update(reqId, bar, True)
        except Exception as e:
            print(e)

    # Get Position Data
    def position(self, account, contract, position, avgCost):
        super().position(account, contract, position, avgCost)
        print("Position:", position, "||", "Avg Cost:", avgCost, "||", "Ticker:", contract.symbol)
        print("=================================================================================")

class Bar:
    open = 0
    low = 0
    high = 0
    close = 0
    volume = 0
    date = datetime.now()
    def __init__(self):
        self.open = 0
        self.low = 0
        self.high = 0
        self.close = 0
        self.volume = 0
        self.date = datetime.now()

class Bot:
    ib = None
    ticker = ""
    currentBar = Bar()
    barSize = 1
    reqId = 1
    global orderId
    action = False
    watchPrice = False
    manualHigh = False
    bars = []
    lastBar = Bar()
    highestPrice = 0
    orderCount = 0
    counter = 0

    hours = 14
    minutes = 52
    initialBarTime = datetime.now().astimezone(pytz.timezone("America/New_York"))
    targetBarTime = (datetime.now().astimezone(pytz.timezone("America/New_York"))
                            ).replace(hour=hours,minute=minutes,second=0,microsecond=0).strftime("%Y%m%d %H:%M:%S")
    actionBarTime = (datetime.now().astimezone(pytz.timezone("America/New_York"))
                            ).replace(hour=hours,minute=minutes+1,second=0,microsecond=0).strftime("%Y%m%d %H:%M:%S")

    def __init__(self):
        self.ib = IBApi()
        self.ib.connect("127.0.0.1", 7496, 0)
        ib_thread = threading.Thread(target=self.run_loop, daemon=True)
        ib_thread.start()
        time.sleep(1)

        self.ticker = input("Enter ticker symbol : ")
        self.manualHigh = input("Enter high: ")
        self.action = True

        currentBar = Bar()

        contract = Contract()
        contract.symbol = self.ticker.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        contract.primaryExchange = "ISLAND"

        self.ib.reqHistoricalData(1, contract, "", "120 S", "1 min", "TRADES", 1, 1, True, []) # Requests historical data

        self.ib.reqTickByTickData(2, contract, "Last", 1, True)

        self.ib.reqPositions()

        if (self.orderCount == 3):
            time.sleep(1)
            quit()

        # Scan criteria:
        # volume to float ratio; if volume has 3x its float, etc its likely to run at open

        # For some reason it sets a limit order way lower. fix orders and see if it works maybe
        # Above could have to do with premarket since thats the only time it happens
        

    def on_bar_update(self, reqId, bar, realtime):
        global orderId

        contract = Contract()
        contract.symbol = self.ticker.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        contract.primaryExchange = "ISLAND"
        
        if (realtime == False):
            self.bars.append(bar)
        else:
            barTime = datetime.strptime(bar.date,"%Y%m%d %H:%M:%S").astimezone(pytz.timezone("America/New_York"))
            minutes_diff = (barTime-self.initialBarTime).total_seconds() / 60.0
            self.currentBar.date = barTime
            
            #On Bar Close
            if (minutes_diff > 0 and math.floor(minutes_diff) % self.barSize == 0 and self.orderCount < 1):
                self.initialBarTime = barTime
                self.lastBar = self.bars[len(self.bars)-1]
                self.action = True

                print("TARGET HIGH:", self.lastBar.high)
                
                # Bar closed append
            self.currentBar.close = bar.close
            self.bars.append(self.currentBar)
            self.currentBar = Bar()
            self.currentBar.open = bar.open

        # Build realtime bar
        if (self.currentBar.open == 0):
            self.currentBar.open = bar.open
        if (self.currentBar.high == 0 or bar.high > self.currentBar.high):
            self.currentBar.high = bar.high
        if (self.currentBar.low == 0 or bar.low < self.currentBar.low):
            self.currentBar.low = bar.low

    def tick_data_handler(self, reqId, price, time):
        global orderId

        # Check criteria (formerly self.lastBar.high)
        if (price > self.manualHigh and price > 0 and self.action and self.orderCount < 1):
            self.watchPrice = True
            print("ACTION PRICE:", price)

            bracket = self.bracket_order(orderId, "BUY", 100, self.lastBar.high)

            contract = Contract()
            contract.symbol = self.ticker.upper()
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"

            for o in bracket:
                o.ocaGroup = "OCA_" + str(orderId)
                self.ib.placeOrder(o.orderId, contract, o)
            orderId += 1

        if (self.watchPrice):
            while self.counter < 1:
                print("WATCHING")
                self.counter += 1
            # Scans for highest tick price
            if (price > self.highestPrice):
                self.highestPrice = price

            # Checks if current price is x amount below highest price
            if (price < (self.highestPrice - 0.02) and self.highestPrice != 0 and self.orderCount < 2):
                order = self.sell_order(orderId, "SELL", 50)

                print("SOLD 1/2")
                print("Price:", price)
                print("Highest Price:", self.highestPrice)
                

                contract = Contract()
                contract.symbol = self.ticker.upper()
                contract.secType = "STK"
                contract.exchange = "SMART"
                contract.currency = "USD"

                self.ib.placeOrder(order.orderId, contract, order)
                orderId += 1

            if (price < (self.highestPrice - 0.03) and self.highestPrice != 0 and self.orderCount < 3):
                order = self.sell_order(orderId, "SELL", 50)

                print("SOLD 2/2")
                print("Price:", price)
                print("Highest Price:", self.highestPrice)
                

                contract = Contract()
                contract.symbol = self.ticker.upper()
                contract.secType = "STK"
                contract.exchange = "SMART"
                contract.currency = "USD"

                self.ib.placeOrder(order.orderId, contract, order)
                orderId += 1

    def run_loop(self):
        self.ib.run()

    def bracket_order(self, parentOrderId, action, quantity, price):
        print("BOUGHT: ", price)
        self.orderCount += 1

        contract = Contract()
        contract.symbol = self.ticker.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        contract.primaryExch = "ISLAND"

        parent = Order()
        parent.action = action
        parent.orderId = parentOrderId
        parent.orderType = "LMT"
        parent.lmtPrice = round((price + .01), 2)
        parent.discretionaryAmt = .03
        parent.totalQuantity = quantity

        bracketOrder = [parent]
        return bracketOrder

    def sell_order(self, sellOrderId, action, quantity):
        self.orderCount += 1

        contract = Contract()
        contract.symbol = self.ticker.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        contract.primaryExch = "ISLAND"

        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.orderId = sellOrderId
        order.totalQuantity = quantity

        return order

bot = Bot()