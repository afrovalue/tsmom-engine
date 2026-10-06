/* TSMOM shared compute core — rebuilt live from the raw monthly series.
   Every view (backtest, signals, risk, execution) derives from these functions, so a change
   to the vol target, leverage cap or deadband propagates everywhere at once. */
const TS = (function(){
  const D = DATA;
  const N = D.inst.length, T = D.dates.length;
  const ACS = ["Equity","Bond","Commodity","FX","Crypto"];

  const trail = (i,t,k) => {
    if(t-k < 0) return null;
    const a = D.midx[i][t], b = D.midx[i][t-k];
    return (a!=null && b!=null && b!==0) ? a/b - 1 : null;
  };
  const mret = (i,t) => {
    const a = D.midx[i][t], b = D.midx[i][t-1];
    return (a!=null && b!=null && b!==0) ? a/b - 1 : null;
  };
  /* Trend STRENGTH, in standard deviations of the k-month move itself:
         z = r_k / (sigma_annual * sqrt(k/12))
     A raw return threshold is the wrong unit — a 2Y note at 1.2% vol that is down 1% has
     moved most of a standard deviation, while natural gas at 42% vol down 1% is noise.
     Judging both against the same "3%" flags every low-vol market and no volatile one. */
  const zscore = (tr, v, k) => (v > 0 ? tr / (v * Math.sqrt(k / 12)) : 0);
  const signal = (tr, v, k, p) =>
    (p.db > 0 && Math.abs(zscore(tr, v, k)) < p.db) ? 0 : Math.sign(tr);
  const lever  = (v,p) => Math.min(p.vt/v, p.cap);

  /* Book at month t for horizon k. Weights are signal*leverage/N where N counts every
     instrument with a usable vol and lookback — a deadbanded position still occupies a slot. */
  function book(t, k, p){
    const rows = []; let n = 0;
    for(let i=0;i<N;i++){
      const v = D.mvol[i][t], tr = trail(i,t,k);
      if(v==null || v<=0 || tr==null) continue;
      n++;
      rows.push({i, v, tr, z: zscore(tr, v, k), s: signal(tr, v, k, p), lv: lever(v,p),
                 capped: p.vt/v > p.cap});
    }
    rows.forEach(r => { r.w = r.s * r.lv / n; });
    return {rows, n};
  }

  /* Monthly TSMOM returns: decided at t-1, earned t-1 -> t. Mirrors tsmom.backtest(). */
  function backtest(k, p, subset){
    const dates=[], ret=[];
    for(let t=1;t<T;t++){
      let s=0, c=0;
      for(let i=0;i<N;i++){
        if(subset && !subset.has(i)) continue;
        const v = D.mvol[i][t-1], tr = trail(i,t-1,k), rr = mret(i,t);
        if(v==null || v<=0 || tr==null || rr==null) continue;
        s += signal(tr, v, k, p) * lever(v,p) * rr; c++;
      }
      if(c>=5){ dates.push(D.dates[t]); ret.push(s/c); }
    }
    return {dates, ret};
  }

  function stats(ret){
    const n = ret.length;
    if(!n) return {n:0, annR:0, annV:0, cagr:0, sharpe:0, sortino:0, downside:0, calmar:0,
                   maxdd:0, ddMonths:0, skew:0, kurt:0, best:0, worst:0, avgWin:0, avgLoss:0,
                   hit:0, total:0, eq:[], dd:[]};
    const mean = ret.reduce((a,b)=>a+b,0)/n;
    const sd = n>1 ? Math.sqrt(ret.reduce((a,b)=>a+(b-mean)*(b-mean),0)/(n-1)) : 0;
    let eqv=1, peak=1, maxdd=0, cur=0, worst=0;
    const eq=[], dd=[];
    for(const r of ret){
      eqv *= (1+r); peak = Math.max(peak, eqv);
      const d = eqv/peak - 1; eq.push(eqv); dd.push(d);
      if(d < maxdd) maxdd = d;
      cur = d < -1e-9 ? cur+1 : 0; worst = Math.max(worst, cur);
    }
    const annR = mean*12, annV = sd*Math.sqrt(12);
    // downside deviation uses only months below zero (MAR = 0)
    const neg = ret.filter(x=>x<0);
    const dsd = neg.length ? Math.sqrt(neg.reduce((a,b)=>a+b*b,0)/n)*Math.sqrt(12) : 0;
    const m3 = sd>0 ? ret.reduce((a,b)=>a+Math.pow((b-mean)/sd,3),0)/n : 0;
    const m4 = sd>0 ? ret.reduce((a,b)=>a+Math.pow((b-mean)/sd,4),0)/n : 0;
    const wins = ret.filter(x=>x>0), losses = ret.filter(x=>x<0);
    const cagr = n>0 ? Math.pow(eqv, 12/n)-1 : 0;
    return {n, annR, annV, cagr, sharpe: annV>0 ? annR/annV : 0,
            sortino: dsd>0 ? annR/dsd : 0, downside: dsd,
            calmar: maxdd<0 ? cagr/Math.abs(maxdd) : 0,
            maxdd, ddMonths: worst, skew: m3, kurt: m4-3,
            best: Math.max(...ret), worst: Math.min(...ret),
            avgWin: wins.length ? wins.reduce((a,b)=>a+b,0)/wins.length : 0,
            avgLoss: losses.length ? losses.reduce((a,b)=>a+b,0)/losses.length : 0,
            hit: wins.length/n, total: eqv-1, eq, dd};
  }

  /* Ex-ante risk of the current book: sigma_p, its perfect-correlation ceiling, and the
     per-instrument contributions that sum to sigma_p. */
  function risk(k, p){
    const t = T-1;
    const {rows, n} = book(t, k, p);
    const byInst = new Map(rows.map(r=>[r.i, r]));
    const ridx = D.risk_idx;
    const w = [], v = [], keep = [];
    ridx.forEach((instI, pos) => {
      const r = byInst.get(instI);
      if(r){ w.push(r.w); v.push(r.v); keep.push(pos); }
    });
    const m = keep.length;
    const sw = new Array(m).fill(0);
    for(let a=0;a<m;a++){
      let acc=0;
      const ca = D.corr[keep[a]];
      for(let b=0;b<m;b++) acc += ca[keep[b]] * v[a] * v[b] * w[b];
      sw[a] = acc;
    }
    let varp = 0;
    for(let a=0;a<m;a++) varp += w[a]*sw[a];
    const sp = Math.sqrt(Math.max(varp,0));
    const ctr = new Map();
    keep.forEach((pos,a)=>{ if(sp>0) ctr.set(ridx[pos], w[a]*sw[a]/sp); });

    let maxVol = 0, net = 0, gross = 0, capped = 0;
    rows.forEach(r => { maxVol += Math.abs(r.w)*r.v; net += r.w; gross += Math.abs(r.w);
                        if(r.capped) capped++; });
    return {rows, n, ctr, sigma_p: sp, max_vol: maxVol,
            div: sp>0 ? maxVol/sp : null, net, gross, capped,
            n_risk: m};
  }

  /* Sleeve aggregates for a book, including risk share when a risk map is supplied. */
  function sleeves(rows, ctr, sp){
    const out = {};
    for(const ac of ACS){
      const g = rows.filter(r => D.inst[r.i].ac === ac);
      const c = g.reduce((a,r)=> a + (ctr && ctr.has(r.i) ? ctr.get(r.i) : 0), 0);
      out[ac] = {
        long:  g.filter(r=>r.s>0).length,
        short: g.filter(r=>r.s<0).length,
        flat:  g.filter(r=>r.s===0).length,
        net:   g.reduce((a,r)=>a+r.w,0),
        gross: g.reduce((a,r)=>a+Math.abs(r.w),0),
        ctr: c, ctr_pct: sp>0 ? c/sp : 0,
      };
    }
    return out;
  }

  /* Realised OLS beta/alpha of the strategy against a benchmark's monthly excess returns.
     Both series are excess returns already, so alpha is a true intercept (no rf term). */
  function benchStats(dates, ret){
    if(!D.bench) return null;
    const bx=[], by=[];
    dates.forEach((d,i)=>{ const j = D.dates.indexOf(d);
      const b = j>=0 ? D.bench[j] : null;
      if(b!=null && ret[i]!=null){ bx.push(b); by.push(ret[i]); } });
    const n = bx.length;
    if(n < 12) return null;
    const mx = bx.reduce((a,b)=>a+b,0)/n, my = by.reduce((a,b)=>a+b,0)/n;
    let cov=0, vx=0, vy=0;
    for(let i=0;i<n;i++){ cov += (bx[i]-mx)*(by[i]-my); vx += (bx[i]-mx)**2; vy += (by[i]-my)**2; }
    const beta = vx>0 ? cov/vx : 0;
    const corr = (vx>0 && vy>0) ? cov/Math.sqrt(vx*vy) : 0;
    return {n, beta, alpha: (my - beta*mx)*12, corr, r2: corr*corr,
            benchAnn: mx*12, benchVol: Math.sqrt(vx/(n-1))*Math.sqrt(12)};
  }

  const acSubset = ac => new Set(D.inst.map((x,i)=>[x,i]).filter(([x])=>x.ac===ac).map(([,i])=>i));

  return {D, N, T, ACS, trail, mret, zscore, signal, lever, book, backtest, stats, risk, sleeves,
          acSubset, benchStats, lastT: () => T-1};
})();
