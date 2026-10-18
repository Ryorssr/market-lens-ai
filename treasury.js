
/* Market Lens AI: official historical FX and US10Y, without synthetic live charts. */
(function () {
  const liveIds = new Set(['usdjpy', 'eurjpy', 'gbpjpy', 'audjpy', 'us10y']);
  const originalSeries = series;
  series = function (x, period) {
    if (liveIds.has(x.id) && x.source && !Array.isArray(x.history?.[period])) {
      return [x.value, x.value];
    }
    return originalSeries(x, period);
  };
  const originalRenderChart = renderChart;
  renderChart = function () {
    originalRenderChart();
    const x = data.find(v => v.id === asset);
    if (!x || !liveIds.has(x.id) || !x.source) return;
    const real = Array.isArray(x.history?.[period]) && x.history[period].length > 1;
    const label = document.querySelector('#chartMeta');
    if (label) label.textContent += real ? ' · 公式データの実際の推移' : ' · この期間の実データなし（水平線で表示）';
    if (!real) {
      const touch = document.querySelector('#chartTouch');
      if (touch) touch.textContent = 'この期間の時系列データは未取得です';
    }
  };
  function mergeHistory(rows) {
    let changed = false;
    for (const row of rows) {
      if (!liveIds.has(row.id)) continue;
      const index = data.findIndex(x => x.id === row.id);
      if (index < 0 || !Number.isFinite(row.value)) continue;
      const history = row.history;
      if (!history || typeof history !== 'object') continue;
      const clean = {};
      for (const key of ['1W', '1M', '3M', '1Y', '5Y']) {
        const arr = history[key];
        if (Array.isArray(arr) && arr.length >= 2 && arr.length <= 1500 &&
            arr.every(v => typeof v === 'number' && Number.isFinite(v))) clean[key] = arr;
      }
      data[index] = {...data[index], ...row, history: clean};
      changed = true;
    }
    if (changed) render();
  }
  async function loadTreasury() {
    try {
      const response = await fetch('./data/treasury.json', {cache:'no-store'});
      if (!response.ok) throw Error('HTTP ' + response.status);
      const payload = await response.json();
      const x = payload?.indicators?.[0];
      if (payload.status !== 'ok' || x?.id !== 'us10y' ||
          !Number.isFinite(x.value) || !Number.isFinite(x.change) ||
          !/^\d{4}-\d{2}-\d{2}$/.test(x.date)) throw Error('Invalid Treasury data');
      mergeHistory([x]);
      sourceMode = fxLoaded ? 'FX + US10Y LIVE / OTHERS DEMO' : 'US10Y LIVE / OTHERS DEMO';
      const note = document.querySelector('#demoNote');
      if (note) note.textContent = '為替はECB公式参考レート、米10年債は米財務省公表値（取得できない場合はFRED）。実データのある期間のみ実際のチャートを表示。株価・商品・AI回答・朝刊解説はデモです。';
      render();
    } catch (error) {
      console.warn('Treasury data unavailable:', error);
    }
  }
  async function loadFxHistory() {
    try {
      const response = await fetch('./data/fx.json', {cache:'no-store'});
      if (!response.ok) throw Error('HTTP ' + response.status);
      const payload = await response.json();
      if (payload.status !== 'ok' || !Array.isArray(payload.indicators)) throw Error('Invalid FX data');
      for (let attempt = 0; attempt < 40 && !fxLoaded; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 250));
      }
      if (!fxLoaded) return;
      mergeHistory(payload.indicators);
      if (data.some(x => x.id === 'us10y' && x.source)) {
        sourceMode = 'FX + US10Y LIVE / OTHERS DEMO';
        render();
      }
    } catch (error) {
      console.warn('FX history unavailable:', error);
    }
  }
  loadTreasury();
  loadFxHistory();
})();
