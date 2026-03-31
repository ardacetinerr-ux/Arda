from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app)  # Allow all origins

YF_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
}

@app.route('/')
def proxy():
    tickers_param = request.args.get('tickers', '').upper().strip()
    ticker_param  = request.args.get('ticker', '').upper().strip()
    req_type      = request.args.get('type', 'spark')

    # === BATCH: ?tickers=AAPL,MSFT — uses Spark API (no auth needed) ===
    if tickers_param:
        symbols = [s.strip() for s in tickers_param.split(',') if s.strip()]
        # Split into batches of 20 (Yahoo limit)
        all_results = []
        for i in range(0, len(symbols), 20):
            batch = ','.join(symbols[i:i+20])
            try:
                url = f'https://query1.finance.yahoo.com/v7/finance/spark?symbols={batch}&range=1d&interval=1d'
                r = requests.get(url, headers=YF_HEADERS, timeout=10)
                if r.ok:
                    data = r.json()
                    spark_results = data.get('spark', {}).get('result') or []
                    for item in spark_results:
                        meta = (item.get('response') or [{}])[0].get('meta', {})
                        price = meta.get('regularMarketPrice')
                        prev  = meta.get('chartPreviousClose')
                        chg   = round((price - prev) / prev * 100, 2) if price and prev else None
                        all_results.append({
                            'symbol':                     item.get('symbol'),
                            'regularMarketPrice':         price,
                            'regularMarketChangePercent': chg,
                            # Spark doesn't have fundamentals — return None for all
                            'trailingPE': None, 'forwardPE': None, 'pegRatio': None,
                            'priceToSalesTrailing12Months': None, 'priceToBook': None,
                            'enterpriseValue': None, 'marketCap': None,
                            'operatingMargins': None, 'freeCashflow': None,
                            'totalRevenue': None, 'revenueGrowth': None,
                            'totalDebt': None, 'totalCash': None,
                            'ebitda': None, 'currentRatio': None, 'epsForward': None,
                        })
            except Exception as e:
                for s in symbols[i:i+20]:
                    all_results.append({'symbol': s, 'error': str(e)})
        return jsonify({'quoteResponse': {'result': all_results, 'error': None}})

    # === SINGLE: ?ticker=AAPL&type=gainers ===
    if req_type == 'gainers':
        try:
            url = 'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=day_gainers&count=15'
            r = requests.get(url, headers=YF_HEADERS, timeout=10)
            quotes = r.json().get('finance',{}).get('result',[{}])[0].get('quotes',[]) if r.ok else []
            return jsonify({'quotes': quotes})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    if req_type == 'losers':
        try:
            url = 'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=day_losers&count=15'
            r = requests.get(url, headers=YF_HEADERS, timeout=10)
            quotes = r.json().get('finance',{}).get('result',[{}])[0].get('quotes',[]) if r.ok else []
            return jsonify({'quotes': quotes})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # === SINGLE: ?ticker=AAPL&type=all (quoteSummary for Stock Analyzer) ===
    if ticker_param:
        if req_type == 'quote':
            try:
                url = f'https://query2.finance.yahoo.com/v8/finance/chart/{ticker_param}?interval=1d&range=1d'
                r = requests.get(url, headers=YF_HEADERS, timeout=10)
                if r.ok:
                    meta = r.json()['chart']['result'][0]['meta']
                    return jsonify({'quoteResponse': {'result': [{
                        'symbol': ticker_param,
                        'regularMarketPrice': meta.get('regularMarketPrice'),
                        'chartPreviousClose': meta.get('chartPreviousClose'),
                        'longName': meta.get('longName',''),
                    }], 'error': None}})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        # type=all — try yfinance for full data
        try:
            import yfinance as yf
            t = yf.Ticker(ticker_param)
            info = t.info
            fi = t.fast_info
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not price:
                try: price = fi.last_price
                except: pass
            return jsonify({'quoteSummary': {'result': [{
                'financialData': {
                    'currentPrice':           {'raw': price},
                    'targetMeanPrice':         {'raw': info.get('targetMeanPrice')},
                    'targetHighPrice':         {'raw': info.get('targetHighPrice')},
                    'targetLowPrice':          {'raw': info.get('targetLowPrice')},
                    'recommendationMean':      {'raw': info.get('recommendationMean')},
                    'recommendationKey':       info.get('recommendationKey'),
                    'numberOfAnalystOpinions': {'raw': info.get('numberOfAnalystOpinions')},
                    'operatingMargins':        {'raw': info.get('operatingMargins')},
                    'freeCashflow':            {'raw': info.get('freeCashflow')},
                    'revenueGrowth':           {'raw': info.get('revenueGrowth')},
                    'totalRevenue':            {'raw': info.get('totalRevenue')},
                    'totalDebt':               {'raw': info.get('totalDebt')},
                    'totalCash':               {'raw': info.get('totalCash')},
                    'ebitda':                  {'raw': info.get('ebitda')},
                    'currentRatio':            {'raw': info.get('currentRatio')},
                },
                'defaultKeyStatistics': {
                    'forwardPE':           {'raw': info.get('forwardPE')},
                    'pegRatio':            {'raw': info.get('trailingPegRatio') or info.get('pegRatio')},
                    'shortPercentOfFloat': {'raw': info.get('shortPercentOfFloat')},
                    'shortRatio':          {'raw': info.get('shortRatio')},
                    'enterpriseValue':     {'raw': info.get('enterpriseValue')},
                    '52WeekChange':        {'raw': info.get('52WeekChange')},
                },
                'incomeStatementHistory': {'incomeStatementHistory': []}
            }], 'error': None}})
        except Exception as e:
            # Fallback to chart endpoint
            try:
                url = f'https://query2.finance.yahoo.com/v8/finance/chart/{ticker_param}?interval=1d&range=1d'
                r = requests.get(url, headers=YF_HEADERS, timeout=10)
                if r.ok:
                    meta = r.json()['chart']['result'][0]['meta']
                    return jsonify({'quoteSummary': {'result': [{
                        'financialData': {'currentPrice': {'raw': meta.get('regularMarketPrice')}},
                        'defaultKeyStatistics': {},
                        'incomeStatementHistory': {'incomeStatementHistory': []}
                    }], 'error': None}})
            except: pass
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Missing ticker or tickers param'}), 400

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 3737))
    app.run(host='0.0.0.0', port=port)
