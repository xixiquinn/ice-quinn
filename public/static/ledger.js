let rows=[],fund=null,saveT=null,saveChain=Promise.resolve(),dirty=false,loadVersion=0;
const api=async(u,o={})=>{const r=await fetch(u,{headers:{'Content-Type':'application/json'},...o});if(r.status===401||r.redirected){location='/login';throw Error('Please sign in again');}const j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j;};
const st=t=>document.getElementById('saveSt').textContent=t;
function localDate(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
async function flush(){clearTimeout(saveT);if(dirty&&fund){const id=fund,data=JSON.stringify({rows});dirty=false;saveChain=saveChain.catch(()=>{}).then(()=>api('/api/funds/'+id,{method:'PUT',body:data}));}try{await saveChain;st(dirty?'Saving…':'All changes saved');}catch(e){dirty=true;st('Save failed — retrying');saveT=setTimeout(flush,2500);throw e;}}
function persist(){dirty=true;st('Saving…');clearTimeout(saveT);saveT=setTimeout(()=>flush().catch(()=>{}),600);}
async function loadFunds(sel){const {funds}=await api('/api/funds');if(!funds.length){const {id}=await api('/api/funds',{method:'POST',body:JSON.stringify({name:'Class Fund'})});return loadFunds(id);}const s=document.getElementById('fundSel');s.innerHTML=funds.map(f=>`<option value="${esc(f.id)}">${esc(f.name)}</option>`).join('');const id=sel||fund||funds[0].id;s.value=funds.some(f=>f.id===id)?id:funds[0].id;document.getElementById('fund-count').textContent=funds.length+' funds';await openFund(s.value);}
async function openFund(id){try{await flush();const version=++loadVersion;st('Loading…');const d=await api('/api/funds/'+id);if(version!==loadVersion)return;fund=id;rows=d.rows||[];document.getElementById('transaction-sub').textContent=d.name;draw();st('All changes saved');}catch(e){st('Unable to open fund');}}
async function newFund(){const name=prompt('Fund name');if(!name?.trim())return;try{await flush();const {id}=await api('/api/funds',{method:'POST',body:JSON.stringify({name})});await loadFunds(id);}catch(e){alert(e.message);}}
async function renameFund(){const name=prompt('New fund name');if(!name?.trim()||!fund)return;try{await flush();await api('/api/funds/'+fund,{method:'PATCH',body:JSON.stringify({name})});await loadFunds(fund);}catch(e){alert(e.message);}}
async function deleteFund(){if(!fund||!confirm('Delete this fund and all its transactions? This cannot be undone.'))return;try{await flush();await api('/api/funds/'+fund,{method:'DELETE'});fund=null;rows=[];await loadFunds();}catch(e){alert(e.message);}}
function nav(el){document.querySelectorAll('.nav-link').forEach(a=>a.classList.remove('active'));el.classList.add('active');document.getElementById('sidebar').classList.remove('open');}
function filterRows(){const q=document.getElementById('search').value.trim().toLowerCase();rows.forEach((r,i)=>{const el=document.getElementById('r'+i);if(el)el.hidden=q&&!Object.values(r).join(' ').toLowerCase().includes(q);});}
const fmt=n=>n.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function add(){rows.push({date:localDate(),description:'',category:'',type:'expense',amount:'',tax:0});draw();persist();document.getElementById('transactions').scrollIntoView({behavior:'smooth'});document.querySelector('#tb tr:last-child input[placeholder=Description]')?.focus();}
function del(i){rows.splice(i,1);draw();persist();}
function draw(){
 document.getElementById('tb').innerHTML=rows.map((r,i)=>`<tr id="r${i}">
 <td><input aria-label="Transaction date" type="date" value="${esc(r.date)}" oninput="set(${i},'date',this.value)"></td>
 <td><input aria-label="Description" value="${esc(r.description)}" placeholder="Description" oninput="set(${i},'description',this.value)"></td>
 <td><input aria-label="Category" value="${esc(r.category)}" placeholder="Category" list="catlist" oninput="set(${i},'category',this.value)"></td>
 <td style="min-width:110px"><select aria-label="Transaction type" onchange="set(${i},'type',this.value)"><option value="income" ${r.type=='income'?'selected':''}>Income</option><option value="expense" ${r.type!='income'?'selected':''}>Expense</option></select></td>
 <td><input aria-label="Amount" class="num" type="number" step="0.01" value="${esc(r.amount)}" placeholder="0.00" oninput="set(${i},'amount',this.value)"></td>
 <td><input aria-label="Tax percent" class="num" type="number" step="0.1" value="${esc(r.tax)}" oninput="set(${i},'tax',this.value)" style="width:70px"></td>
 <td class="num" id="t${i}"></td><td id="f${i}"></td>
 <td><button aria-label="Delete transaction" title="Delete transaction" class="x" onclick="del(${i})">✕</button></td></tr>`).join('')+'<datalist id="catlist"></datalist>';
 calc();}
function set(i,k,v){rows[i][k]=v;calc();persist();}
function calc(){
 let inc=0,exp=0,tax=0,cats={},flags=0,finds={},seen={};
 const amts=rows.map(r=>+r.amount||0).filter(a=>a>0),mean=amts.reduce((a,b)=>a+b,0)/(amts.length||1),
 sd=Math.sqrt(amts.reduce((a,b)=>a+(b-mean)**2,0)/(amts.length||1));
 rows.forEach(r=>{const k=[r.date,r.amount,r.description.trim().toLowerCase(),r.type].join('|');seen[k]=(seen[k]||0)+1;});
 rows.forEach((r,i)=>{
  const a=+r.amount||0,t=a*(+r.tax||0)/100,tot=a+t,f=[];
  if(r.type=='income')inc+=tot;else{exp+=tot;const c=r.category||'Uncategorized';cats[c]=(cats[c]||0)+tot;}
  tax+=t;
  if(r.amount===''||!r.date||!r.description)f.push('Missing');
  if(a<0)f.push('Negative');
  if(a>=1000&&a%1000==0)f.push('Round');
  if(r.amount!==''&&seen[[r.date,r.amount,r.description.trim().toLowerCase(),r.type].join('|')]>1)f.push('Duplicate');
  if(amts.length>=5&&sd&&Math.abs(a-mean)>2.5*sd)f.push('Outlier');
  if(r.date){const d=new Date(r.date+'T00:00');if([0,6].includes(d.getDay()))f.push('Weekend');if(d>new Date())f.push('Future');}
  f.forEach(x=>finds[x]=(finds[x]||0)+1);if(f.length)flags++;
  const tc=document.getElementById('t'+i);if(tc){tc.textContent=fmt(tot);tc.className='num '+(r.type=='income'?'pos':'neg');
  document.getElementById('f'+i).innerHTML=f.map(x=>`<span class="tag">${x}</span>`).join('');
  document.getElementById('r'+i).className=f.length?'flag':'';}
 });
 const net=inc-exp;
 document.getElementById('s-inc').textContent=fmt(inc);document.getElementById('s-exp').textContent=fmt(exp);
 document.getElementById('s-net').textContent=fmt(net);
 document.getElementById('s-tax').textContent=fmt(tax);
 document.getElementById('s-mar').textContent=inc?(net/inc*100).toFixed(1)+'%':'—';
 document.getElementById('s-flg').textContent=flags;
 document.getElementById('finds').innerHTML=Object.entries(finds).map(([k,v])=>`<span class="tag">${k}: ${v}</span>`).join('')||'<p class="mute">No issues found.</p>';
 renderCharts(cats,exp);
 document.getElementById('row-count').textContent=rows.length+' transactions';
 document.getElementById('nav-count').textContent=rows.length;
 document.getElementById('nav-flags').textContent=flags;
 document.getElementById('income-count').textContent=rows.filter(r=>r.type==='income').length+' transactions';
 document.getElementById('expense-count').textContent=rows.filter(r=>r.type!=='income').length+' transactions';
 const ready=rows.length?Math.round((rows.length-flags)/rows.length*100):0;
 document.getElementById('audit-ready').textContent=rows.length?ready+'% of transactions have no audit flags.':'No transactions to review.';
 document.getElementById('audit-progress').style.width=ready+'%';
 document.getElementById('empty').classList.toggle('hidden',rows.length>0);
 filterRows();
 const dl=document.getElementById('catlist');if(dl)dl.innerHTML=[...new Set(rows.map(r=>r.category).filter(Boolean))].map(c=>`<option value="${esc(c)}">`).join('');
}

function canvas(id){const el=document.getElementById(id),rect=el.getBoundingClientRect(),dpr=window.devicePixelRatio||1;el.width=rect.width*dpr;el.height=rect.height*dpr;const ctx=el.getContext('2d');ctx.scale(dpr,dpr);return {ctx,w:rect.width,h:rect.height};}
function renderCharts(cats,exp){const css=getComputedStyle(document.documentElement),color=k=>css.getPropertyValue(k).trim(),palette=[color('--acc'),color('--peach'),color('--mint')];
 const {ctx,w,h}=canvas('flowChart'),count=Number(document.getElementById('chart-period').value),now=new Date(),months=Array.from({length:count},(_,i)=>new Date(now.getFullYear(),now.getMonth()-count+1+i,1)),inc=months.map(()=>0),out=months.map(()=>0);
 rows.forEach(r=>{const idx=months.findIndex(d=>r.date?.startsWith(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`));if(idx>=0)(r.type==='income'?inc:out)[idx]+=(Number(r.amount)||0)*(1+(Number(r.tax)||0)/100);});
 const max=Math.max(...inc,...out,1)*1.15,left=42,right=w-8,top=15,bottom=h-28,px=i=>left+i*(right-left)/(count-1),py=v=>bottom-v/max*(bottom-top);ctx.font='9px Manrope,Arial';ctx.fillStyle=color('--mute');ctx.strokeStyle=color('--line');ctx.setLineDash([2,3]);for(let i=0;i<4;i++){let y=bottom-i*(bottom-top)/3;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText((max*i/3).toLocaleString(undefined,{maximumFractionDigits:0,notation:'compact'}),0,y+3);}ctx.setLineDash([]);months.forEach((d,i)=>ctx.fillText(d.toLocaleDateString(undefined,{month:'short'}),px(i)-8,h-7));
 const line=(values,c,dashed)=>{ctx.beginPath();values.forEach((v,i)=>i?ctx.lineTo(px(i),py(v)):ctx.moveTo(px(i),py(v)));ctx.strokeStyle=c;ctx.lineWidth=2.4;ctx.setLineDash(dashed?[5,5]:[]);ctx.stroke();if(!dashed){ctx.lineTo(right,bottom);ctx.lineTo(left,bottom);ctx.closePath();ctx.globalAlpha=.1;ctx.fillStyle=c;ctx.fill();ctx.globalAlpha=1;}ctx.setLineDash([]);};line(inc,palette[0],false);line(out,palette[1],true);
 const d=canvas('expenseChart'),cx=d.w/2,cy=d.h/2,r=Math.min(d.w,d.h)/2-16,vals=Object.entries(cats).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]),total=vals.reduce((s,[,v])=>s+v,0);d.ctx.lineWidth=21;let a=-Math.PI/2;if(!total){d.ctx.strokeStyle=color('--line');d.ctx.beginPath();d.ctx.arc(cx,cy,r,0,Math.PI*2);d.ctx.stroke();}vals.forEach(([c,v],i)=>{const end=a+v/total*2*Math.PI;d.ctx.beginPath();d.ctx.strokeStyle=palette[i%3];d.ctx.arc(cx,cy,r,a,end);d.ctx.stroke();a=end;});document.getElementById('donut-total').textContent=fmt(exp);document.getElementById('cats').innerHTML=vals.map(([c,v],i)=>`<div class="category-line"><span><i class="dot ${i%3===1?'peach':i%3===2?'mint':''}"></i>${esc(c)}</span><b>${Math.round(v/total*100)}%</b></div>`).join('')||'<div class="category-line">No expenses yet</div>';
}
document.getElementById('imp').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;try{await flush();const fd=new FormData();fd.append('file',file);const r=await fetch('/ledger/import',{method:'POST',body:fd});if(r.redirected){location='/login';return;}const j=await r.json();if(!r.ok)throw Error(j.error||'Import failed');if(confirm(`Import ${j.rows.length} rows? OK replaces existing rows; Cancel appends them.`))rows=j.rows;else rows=rows.concat(j.rows);draw();persist();}catch(e){alert(e.message);}finally{e.target.value='';}};
async function exportX(){try{await flush();const r=await fetch('/ledger/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows})});if(!r.ok||r.redirected)throw Error('Export failed. Please sign in and retry.');const blob=await r.blob(),a=document.createElement('a'),url=URL.createObjectURL(blob);a.href=url;a.download=(document.getElementById('fundSel').selectedOptions[0]?.text||'ledger')+'.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){alert(e.message);}}
document.getElementById('today').textContent=new Date().toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'});window.addEventListener('resize',()=>calc());window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});loadFunds().catch(e=>st('Unable to load funds'));
