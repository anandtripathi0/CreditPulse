(() => {
  'use strict';
  const form = document.querySelector('#tool-form');
  const fields = document.querySelector('#tool-fields');
  const results = document.querySelector('#tool-results');
  const error = document.querySelector('#tool-error');
  const submit = document.querySelector('#calculate');
  const money = n => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:2}).format(n);
  const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let current = 'loan', controller, csv = null;
  const drafts = {};
  const input = (key,label,value,max=100000000,min=0,step='any') => `<label>${label}<input name="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${value}" required></label>`;
  const nameInput = (key,value) => `<label>Account label<input name="${key}" value="${value}" maxlength="60" required></label>`;
  const grid = html => `<div class="field-grid">${html}</div>`;
  const loanFields = (prefix='',extra=true) => grid(input(prefix+'principal','Loan amount (₹)',500000,100000000,.01)+input(prefix+'annual_rate','Annual interest (%)',10.5,60)+input(prefix+'months','Term (months)',60,600,1,1)+input(prefix+'fee','Upfront fee (₹)',2500)+(extra?input(prefix+'monthly_extra','Extra monthly payment (₹)',0):''));
  const configs = {
    loan: ['Plan your loan repayment','See the full cost of borrowing and how extra payments change your timeline.', () => loanFields()],
    compare: ['Compare two loan offers','Use the same loan amount for both offers. Fees are paid upfront, not financed.', () => [0,1].map(i=>`<fieldset><legend>Offer ${i+1}</legend>${loanFields('o'+i+'_',false)}</fieldset>`).join('')],
    payoff: ['Build your debt-free plan','Compare highest-rate-first and smallest-balance-first. The total monthly budget stays constant as accounts are paid off.', () => `<label>Number of debts<input name="count" type="number" min="1" max="10" step="1" value="2" required></label><div id="account-rows"></div>${input('extra','Extra monthly budget (₹)',2000)}`],
    affordability: ['Find your borrowing room','Choose a debt-to-income ceiling and a savings reserve. Your result also accounts for living expenses.', () => grid(input('income','Monthly take-home income (₹)',75000,100000000,.01)+input('expenses','Living expenses, excluding EMIs (₹)',25000)+input('existing_emis','Existing monthly EMIs (₹)',10000)+input('reserve','Monthly savings reserve (₹)',10000)+input('target_dti','Your target DTI ceiling (%)',35,100,.01)+input('annual_rate','Annual interest (%)',10.5,60)+input('months','Loan term (months)',60,600,1,1))],
    utilization: ['Understand your credit usage','Set a personal utilization target. Balances above the credit limit are supported; this is not a score prediction.', () => `<label>Number of cards<input name="count" type="number" min="1" max="10" step="1" value="2" required></label><div id="account-rows"></div>${input('target','Target utilization (%)',30,100)}`]
  };
  function rows(count) {
    const container = document.querySelector('#account-rows');
    if (!container) return;
    const previous = Object.fromEntries(new FormData(form));
    container.innerHTML = Array.from({length:count},(_,i)=>`<fieldset><legend>${current==='payoff'?'Debt':'Card'} ${i+1}</legend>${grid(nameInput('a'+i+'_name',`Account ${i+1}`)+input('a'+i+'_balance','Outstanding balance (₹)',i?20000:50000,100000000,current==='payoff'?.01:0)+(current==='payoff'?input('a'+i+'_annual_rate','Annual interest (%)',i?12:24,60)+input('a'+i+'_minimum','Fixed monthly minimum (₹)',i?1500:3000,100000000,.01):input('a'+i+'_limit','Credit limit (₹)',100000,100000000,.01)))}</fieldset>`).join('');
    Object.entries(previous).forEach(([k,v])=>{ if(form.elements[k]) form.elements[k].value=v; });
  }
  function select(tool) {
    if(form.elements.length) drafts[current]=Object.fromEntries(new FormData(form));
    controller?.abort(); current=tool; csv=null;
    document.querySelectorAll('[data-tool]').forEach(b=>{ const active=b.dataset.tool===tool; b.setAttribute('aria-selected',active); b.tabIndex=active?0:-1; });
    document.querySelector('#tool-panel').setAttribute('aria-labelledby','tab-'+tool);
    document.querySelector('#tool-title').textContent=configs[tool][0];
    document.querySelector('#tool-description').textContent=configs[tool][1];
    fields.innerHTML=configs[tool][2]();
    if(form.elements.count) { rows(Number(drafts[tool]?.count||2)); form.elements.count.addEventListener('change',()=>{if(form.elements.count.checkValidity()) rows(Number(form.elements.count.value));}); }
    Object.entries(drafts[tool]||{}).forEach(([k,v])=>{if(form.elements[k])form.elements[k].value=v;});
    error.textContent=''; submit.disabled=false;
    results.innerHTML='<span class="eyebrow">YOUR RESULTS</span><h3>Explore your next move.</h3><p>Adjust the illustrative inputs and calculate your scenario.</p><div class="empty-art" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>';
  }
  document.querySelectorAll('[data-tool]').forEach((b,i,buttons)=>{
    b.addEventListener('click',()=>select(b.dataset.tool));
    b.addEventListener('keydown',e=>{let index;if(e.key==='ArrowRight')index=(i+1)%buttons.length;if(e.key==='ArrowLeft')index=(i+buttons.length-1)%buttons.length;if(e.key==='Home')index=0;if(e.key==='End')index=buttons.length-1;if(index!==undefined){e.preventDefault();buttons[index].focus();select(buttons[index].dataset.tool);}});
  });
  const metric = (label,value) => `<div class="metric"><small>${label}</small><strong>${escape(value)}</strong></div>`;
  const note = s => `<p class="result-note">${escape(s)}</p>`;
  function table(headers, rows) {return `<div class="table-scroll"><table><thead><tr>${headers.map(h=>`<th scope="col">${escape(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${escape(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;}
  function render(data) {
    let html='<span class="eyebrow">YOUR PLAN / ESTIMATED RESULTS</span>';
    if(current==='loan') {
      html+=`<h3>Monthly EMI</h3><div class="metric-primary">${money(data.emi)}</div><div class="metric-grid">${metric('Total interest',money(data.interest))+metric('Total paid, including fee',money(data.total))+metric('Payoff time',data.payoff_months+' months')+metric('Interest saved',money(data.interest_saved))}</div>`;
      html+=`<div class="result-bar" aria-hidden="true"><span style="width:${Math.max(0,Math.min(100,(data.total-data.interest-data.fee)/data.total*100))}%"></span></div>`;
      html+=note(`Extra payments shorten this loan by ${data.months_saved} months. The EMI above excludes your extra payment; the schedule includes it.`);
      const headers=['Month','Payment','Principal','Interest','Balance'];
      csv=[headers,...data.schedule.map(r=>[r.month,r.payment,r.principal,r.interest,r.balance])];
      html+='<button type="button" class="secondary-button" id="download-plan">Download schedule CSV</button>';
      html+=table(headers,data.schedule.map(r=>[r.month,money(r.payment),money(r.principal),money(r.interest),money(r.balance)]));
    } else if(current==='compare') {
      data.offers.forEach((o,i)=>{html+=`<h3 class="result-heading">Offer ${i+1}${i===data.lowest_cost_index?'<span>Lowest total cost</span>':''}</h3><div class="metric-grid">${metric('Monthly EMI',money(o.emi))+metric('Total paid',money(o.total))+metric('Interest',money(o.interest))+metric('Term',o.payoff_months+' months')}</div>`;});
      html+=note('Cost difference: '+money(Math.abs(data.offers[0].total-data.offers[1].total))+'. Compare lender terms and all charges before choosing.');
    } else if(current==='affordability') {
      html+=`<h3>Estimated loan capacity</h3><div class="metric-primary">${money(data.principal_capacity)}</div><div class="metric-grid">${metric('Room for new EMI',money(data.monthly_capacity))+metric('Current DTI',data.current_dti+'%')+metric('Cash after expenses, EMIs & reserve',money(data.remaining_cash))}</div>`+note('This is a budget scenario using your chosen DTI ceiling, not a lender eligibility decision.');
    } else if(current==='utilization') {
      html+=`<h3>Overall utilization</h3><div class="metric-primary">${data.utilization}%</div><div class="metric-grid">${metric('Total card balance',money(data.total_balance))+metric('Total limit',money(data.total_limit))+metric('Available credit',money(data.available))+metric('Paydown to overall target',money(data.paydown))}</div>`;
      html+=table(['Account','Usage','Paydown to card target'],data.cards.map(c=>[c.name,c.utilization+'%',money(c.paydown)]))+note('Individual cards may need additional paydown even if your overall usage meets the target. No score increase is guaranteed.');
    } else {
      ['avalanche','snowball'].forEach(key=>{const d=data[key];html+=`<h3>${key==='avalanche'?'Avalanche · highest rate first':'Snowball · smallest balance first'}</h3><div class="metric-grid">${metric('Debt-free in',d.completed?d.months+' months':'Beyond 600 months')+metric(d.completed?'Total interest':'Interest over 600 months',money(d.interest))+metric('Monthly budget',money(d.monthly_budget))}</div>`; if(!d.completed) html+=note('This budget does not repay all debts within 600 months. Remaining balance: '+money(d.remaining)+'. Try increasing the monthly budget.');html+=table(['Account cleared','Month'],d.order.map(o=>[o.name,o.month]));});
      html+=note('Minimum payments are fixed at your entered amounts. Freed payments roll into other debts. No new borrowing or fees are included.');
    }
    results.innerHTML=html;
    document.querySelector('#download-plan')?.addEventListener('click',()=>{const blob=new Blob([csv.map(r=>r.join(',')).join('\r\n')],{type:'text/csv;charset=utf-8;'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='creditpulse-repayment-plan.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  }
  form.addEventListener('submit',async e=>{
    e.preventDefault(); if(!form.reportValidity())return;
    const raw=Object.fromEntries(new FormData(form));
    const pick=(prefix,keys)=>Object.fromEntries(keys.map(k=>[k,k==='name'?raw[prefix+k].trim():Number(raw[prefix+k])]));
    let payload;
    if(current==='loan') payload=pick('',['principal','annual_rate','months','fee','monthly_extra']);
    if(current==='compare') payload={offers:[0,1].map(i=>pick('o'+i+'_',['principal','annual_rate','months','fee']))};
    if(current==='affordability') payload=pick('',['income','expenses','existing_emis','reserve','target_dti','annual_rate','months']);
    if(current==='payoff') payload={extra:Number(raw.extra),debts:Array.from({length:Number(raw.count)},(_,i)=>pick('a'+i+'_',['name','balance','annual_rate','minimum']))};
    if(current==='utilization') payload={target:Number(raw.target),cards:Array.from({length:Number(raw.count)},(_,i)=>pick('a'+i+'_',['name','balance','limit']))};
    controller?.abort(); const active=new AbortController();controller=active;
    error.textContent=''; submit.disabled=true;results.setAttribute('aria-busy','true');
    try {
      const response=await fetch('/api/tools/'+current,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:active.signal});
      const data=await response.json();
      if(!response.ok)throw new Error(Array.isArray(data.detail)?data.detail.map(d=>d.msg).join('; '):(data.detail||'Calculation failed. Please try again.'));
      render(data);
    } catch(e) {if(e.name!=='AbortError'){error.textContent=e.message||'Unable to connect. Please try again.';results.innerHTML='<h3>No result calculated</h3><p>Check your inputs and connection, then try again.</p>';}}
    finally {if(controller===active){submit.disabled=false;results.removeAttribute('aria-busy');}}
  });
  select('loan');
})();
