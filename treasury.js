/* Market Lens AI: verified daily US 10Y Treasury yield from FRED. */
(async function () {
  try {
    const response = await fetch('./data/treasury.json', {cache:'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const payload = await response.json();
    const x = payload?.indicators?.[0];
    if (payload.status !== 'ok' || x?.id !== 'us10y' ||
        !Number.isFinite(x.value) || !Number.isFinite(x.change) ||
        !/^\d{4}-\d{2}-\d{2}$/.test(x.date)) throw new Error('Invalid data');
    const i = data.findIndex(row => row.id === 'us10y');
    if (i < 0) return;
    data[i] = {...data[i], ...x, history:null};
    sourceMode = fxLoaded ? 'FX + US10Y LIVE / OTHERS DEMO' : 'US10Y LIVE / OTHERS DEMO';
    const note = document.querySelector('#demoNote');
    if (note) note.textContent = '米10年債利回りはFRB H.15の公表値（FRED経由）。為替はECBの取得状況に従います。その他の株価・商品・チャート時系列・AI回答・朝刊解説はデモです。';
    render();
  } catch (e) {
    console.warn('Treasury reference data unavailable; demo remains clearly labeled:', e);
  }
})();
