from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

@app.route('/')
def proxy():
    # Batch mode: ?tickers=AAPL,MSFT
    tickers_param = request.args.get('tickers', '').upper().strip()
    ticker_param  = request.args.get('ticker', '').upper().strip()
    req_type      = request.args.get('type', 'all')

    if tickers_param:
        symbols = [s.strip() for s in tickers_param.split(',') if s.strip()]
        results = []
        for sym in symbols:
            try:
                info = yf.Ticker(sym).info
                results.append({
                    'symbol': sym,
                    'regularMarketPrice':         info.get('currentPrice') or info.get('regularMarketPrice'),
                    'regularMarketChangePercent': info.get('regularMarketChangePercent'),
                    'trailingPE':                 info.get('trailingPE'),
                    'forwardPE':                  info.get('forwardPE'),
                    'pegRatio':                   info.get('trailingPegRatio') or info.get('pegRatio'),
                    'priceToSalesTrailing12Months': info.get('priceToSalesTrailing12Months'),
                    'priceToBook':                info.get('priceToBook'),
                    'enterpriseValue':            info.get('enterpriseValue'),
                    'marketCap':                  info.get('marketCap'),
                    'operatingMargins':           info.get('operatingMargins'),
                    'freeCashflow':               info.get('freeCashflow'),
                    'totalRevenue':               info.get('totalRevenue'),
                    'revenueGrowth':              info.get('revenueGrowth'),
                    'totalDebt':                  info.get('totalDebt'),
                    'totalCash':                  info.get('totalCash'),
                    'ebitda':                     info.get('ebitda'),
                    'currentRatio':               info.get('currentRatio'),
                    'longName':                   info.get('longName'),
                    'sector':                     info.get('sector'),
                })
            except Exception as e:
                results.append({'symbol': sym, 'error': str(e)})
        return jsonify({'quoteResponse': {'result': results, 'error': None}})

    if ticker_param:
        try:
            t = yf.Ticker(ticker_param)
            info = t.info

            if req_type == 'quote':
                return jsonify({'quoteResponse': {'result': [{
                    'symbol':                     ticker_param,
                    'regularMarketPrice':         info.get('currentPrice') or info.get('regularMarketPrice'),
                    'regularMarketChangePercent': info.get('regularMarketChangePercent'),
                    'trailingPE':                 info.get('trailingPE'),
                    'forwardPE':                  info.get('forwardPE'),
                    'marketCap':                  info.get('marketCap'),
                    'longName':                   info.get('longName'),
                    'sector':                     info.get('sector'),
                }], 'error': None}})

            elif req_type == 'timeseries':
                hist = t.financials  # annual income statement
                cashflow = t.cashflow
                balance = t.balance_sheet
                rows = []
                for col in hist.columns:
                    ts = int(col.timestamp()) if hasattr(col, 'timestamp') else 0
                    row = {'endDate': {'raw': ts, 'fmt': str(col)[:10]},
                           'totalRevenue': {'raw': _safe(hist, 'Total Revenue', col)},
                           'grossProfit':  {'raw': _safe(hist, 'Gross Profit', col)},
                           'netIncome':    {'raw': _safe(hist, 'Net Income', col)},
                           'ebitda':       {'raw': _safe(hist, 'EBITDA', col)},
                           'dilutedEPS':   {'raw': info.get('trailingEps')},
                           'freeCashFlow': {'raw': _safe(cashflow, 'Free Cash Flow', col)},
                           'totalDebt':    {'raw': _safe(balance, 'Total Debt', col)},
                           'cash':         {'raw': _safe(balance, 'Cash And Cash Equivalents', col)},
                    }
                    rows.append(row)
                return jsonify({'timeseries': rows})

            else:  # type=all - quoteSummary equivalent
                fast_info = t.fast_info
                return jsonify({'quoteSummary': {'result': [{
                    'financialData': {
                        'currentPrice':           {'raw': info.get('currentPrice') or info.get('regularMarketPrice')},
                        'targetHighPrice':         {'raw': info.get('targetHighPrice')},
                        'targetLowPrice':          {'raw': info.get('targetLowPrice')},
                        'targetMeanPrice':         {'raw': info.get('targetMeanPrice')},
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
                        'forwardPE':               {'raw': info.get('forwardPE')},
                        'pegRatio':                {'raw': info.get('trailingPegRatio') or info.get('pegRatio')},
                        'shortPercentOfFloat':     {'raw': info.get('shortPercentOfFloat')},
                        'shortRatio':              {'raw': info.get('shortRatio')},
                        'floatShares':             {'raw': info.get('floatShares')},
                        '52WeekChange':            {'raw': info.get('52WeekChange')},
                        'enterpriseValue':         {'raw': info.get('enterpriseValue')},
                    },
                    'incomeStatementHistory': {
                        'incomeStatementHistory': []
                    }
                }], 'error': None}})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Missing ticker'}), 400

def _safe(df, row, col):
    try:
        v = df.loc[row, col]
        return None if (v != v) else float(v)  # NaN check
    except:
        return None

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 3737))
    app.run(host='0.0.0.0', port=port)
