const https = require('https');
const http = require('http');
const url = require('url');

const PORT = process.env.PORT || 3737;

let savedCookie = '';
let savedCrumb  = '';

function getYahooCrumb(callback) {
  if (savedCrumb) return callback(null, savedCrumb);

  const req = https.request({
    hostname: 'fc.yahoo.com', path: '/', method: 'GET',
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
  }, (res) => {
    savedCookie = (res.headers['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
    res.resume();
    const req2 = https.request({
      hostname: 'query2.finance.yahoo.com', path: '/v1/test/getcrumb', method: 'GET',
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Cookie': savedCookie }
    }, (res2) => {
      let crumb = '';
      res2.on('data', d => crumb += d);
      res2.on('end', () => { savedCrumb = crumb.trim(); callback(null, savedCrumb); });
    });
    req2.on('error', callback); req2.end();
  });
  req.on('error', callback); req.end();
}

function yahooGet(hostname, path, callback) {
  const opts = {
    hostname, path, method: 'GET',
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', Accept: 'application/json', Cookie: savedCookie }
  };
  const req = https.request(opts, (res) => {
    let data = ''; res.on('data', c => data += c); res.on('end', () => callback(null, res.statusCode, data));
  });
  req.on('error', callback); req.end();
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Content-Type', 'application/json');
  if (req.method === 'OPTIONS') { res.writeHead(200); res.end(); return; }

  const parsed = url.parse(req.url, true);

  const batchParam = (parsed.query.tickers || '').toUpperCase().replace(/[^A-Z0-9.,\-]/g, '');
  if (batchParam) {
    getYahooCrumb((err, crumb) => {
      if (err || !crumb) { res.writeHead(500); res.end(JSON.stringify({ error: 'Crumb failed' })); return; }
      yahooGet('query1.finance.yahoo.com',
        `/v7/finance/quote?symbols=${encodeURIComponent(batchParam)}&fields=regularMarketPrice,regularMarketChangePercent,trailingPE,forwardPE,epsForward,marketCap,priceToSalesTrailing12Months,priceToBook,pegRatio,epsTrailingTwelveMonths,totalRevenue,freeCashflow,operatingMargins,revenueGrowth,totalDebt,totalCash,ebitda,currentRatio,enterpriseValue&crumb=${encodeURIComponent(crumb)}`,
        (e, s, d) => { if (e) { res.writeHead(500); res.end(JSON.stringify({ error: e.message })); return; } res.writeHead(s); res.end(d); });
    });
    return;
  }

  const ticker = (parsed.query.ticker || '').toUpperCase().replace(/[^A-Z0-9.\-]/g, '');
  if (!ticker) { res.writeHead(400); res.end(JSON.stringify({ error: 'Missing ticker' })); return; }

  getYahooCrumb((err, crumb) => {
    if (err || !crumb) { res.writeHead(500); res.end(JSON.stringify({ error: 'Crumb failed' })); return; }

    const type = parsed.query.type || 'all';

    if (type === 'quote') {
      yahooGet('query1.finance.yahoo.com',
        `/v7/finance/quote?symbols=${ticker}&fields=regularMarketPrice,regularMarketChangePercent,trailingPE,forwardPE,marketCap,priceToSalesTrailing12Months,priceToBook,pegRatio,epsTrailingTwelveMonths,longName,sector&crumb=${encodeURIComponent(crumb)}`,
        (e, s, d) => { if (e) { res.writeHead(500); res.end(JSON.stringify({ error: e.message })); return; } res.writeHead(s); res.end(d); });

    } else if (type === 'timeseries') {
      const types = [
        'annualTotalRevenue','annualGrossProfit','annualNetIncome','annualEbitda',
        'annualDilutedEPS','annualFreeCashFlow','annualTotalDebt','annualCashAndCashEquivalents'
      ].join(',');
      yahooGet('query2.finance.yahoo.com',
        `/ws/fundamentals-timeseries/v1/finance/timeseries/${ticker}?type=${types}&period1=1262304000&period2=9999999999&crumb=${encodeURIComponent(crumb)}`,
        (e, s, d) => { if (e) { res.writeHead(500); res.end(JSON.stringify({ error: e.message })); return; }
          if (s === 401) { savedCrumb = ''; savedCookie = ''; }
          res.writeHead(s); res.end(d); });

    } else {
      const modules = 'financialData,defaultKeyStatistics,incomeStatementHistory';
      yahooGet('query2.finance.yahoo.com',
        `/v10/finance/quoteSummary/${ticker}?modules=${modules}&crumb=${encodeURIComponent(crumb)}`,
        (e, s, d) => { if (e) { res.writeHead(500); res.end(JSON.stringify({ error: e.message })); return; }
          if (s === 401) { savedCrumb = ''; savedCookie = ''; }
          res.writeHead(s); res.end(d); });
    }
  });
});

server.listen(PORT, () => console.log('YF Proxy running on port ' + PORT));
