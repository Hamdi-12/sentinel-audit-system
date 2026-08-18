// Auto-dismiss alerts
document.querySelectorAll('.alert').forEach(el=>{
  setTimeout(()=>{el.style.opacity='0';el.style.transform='translateY(-4px)'},4500);
  setTimeout(()=>el.remove(),5000);
});

// Drag and drop upload
const dz=document.querySelector('.dropzone');
const fi=document.getElementById('file-input');
if(dz&&fi){
  dz.addEventListener('click',()=>fi.click());
  fi.addEventListener('change',()=>{
    if(fi.files[0]){document.querySelector('.dz-text').textContent=fi.files[0].name;dz.style.borderColor='var(--hi)'}
  });
  ['dragenter','dragover'].forEach(e=>dz.addEventListener(e,ev=>{ev.preventDefault();dz.classList.add('dragover')}));
  ['dragleave','drop'].forEach(e=>dz.addEventListener(e,ev=>{ev.preventDefault();dz.classList.remove('dragover')}));
  dz.addEventListener('drop',ev=>{
    const f=ev.dataTransfer.files[0];
    if(f){const dt=new DataTransfer();dt.items.add(f);fi.files=dt.files;document.querySelector('.dz-text').textContent=f.name;dz.style.borderColor='var(--hi)'}
  });
}

// Confirm
document.querySelectorAll('[data-confirm]').forEach(el=>el.addEventListener('click',e=>{if(!confirm(el.dataset.confirm))e.preventDefault()}));

// Live stats
if(document.getElementById('live-stats')){
  setInterval(()=>{
    fetch('/dashboard/api/stats').then(r=>r.json()).then(d=>{
      ['stat-tx','stat-flags','stat-open','stat-high'].forEach(id=>{
        const el=document.getElementById(id);
        if(!el)return;
        const key={'stat-tx':'total_tx','stat-flags':'total_flags','stat-open':'open_flags','stat-high':'high_flags'}[id];
        if(d[key]!==undefined)el.textContent=d[key];
      });
    }).catch(()=>{});
  },30000);
}

// Chat
let history=[];

function appendMsg(role,text){
  const c=document.getElementById('chat-msgs');
  const d=document.createElement('div');
  d.className=role==='user'?'user-msg':'ai-msg';
  const label=role==='user'?'You':'Sentinel AI';
  d.innerHTML=`<div class="msg-label">${label}</div><div class="msg-bubble ${role}">${text.replace(/\n/g,'<br>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')}</div>`;
  c.appendChild(d);c.scrollTop=c.scrollHeight;
}

function thinking(){
  const c=document.getElementById('chat-msgs');
  const d=document.createElement('div');
  d.className='ai-msg';d.id='thinking';
  d.innerHTML='<div class="msg-label">Sentinel AI</div><div class="thinking"><div class="ai-dot"></div><div class="ai-dot"></div><div class="ai-dot"></div></div>';
  c.appendChild(d);c.scrollTop=c.scrollHeight;
}

async function sendMsg(text){
  if(!text.trim())return;
  const inp=document.getElementById('chat-input');
  const btn=document.getElementById('send-btn');
  inp.value='';btn.disabled=true;
  appendMsg('user',text);thinking();
  try{
    const resp=await fetch('/chat/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,history})});
    const data=await resp.json();
    document.getElementById('thinking')?.remove();
    appendMsg('assistant',data.response);
    history.push({role:'user',content:text},{role:'assistant',content:data.response});
    if(history.length>20)history=history.slice(-20);
  }catch(e){
    document.getElementById('thinking')?.remove();
    appendMsg('assistant','Connection error. Please try again.');
  }
  btn.disabled=false;inp.focus();
}

document.getElementById('send-btn')?.addEventListener('click',()=>sendMsg(document.getElementById('chat-input').value));
document.getElementById('chat-input')?.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg(e.target.value)}});
function askSugg(t){sendMsg(t)}

// Inline AI flag analysis
document.querySelectorAll('.ai-flag-btn').forEach(btn=>{
  btn.addEventListener('click',async function(){
    const fid=this.dataset.flagId;
    const box=document.getElementById('ai-box-'+fid);
    if(!box)return;
    box.style.display='block';
    box.innerHTML='<div class="ai-panel"><div class="ai-header"><span class="ai-badge">Sentinel AI</span><span class="ai-model">Analysing...</span></div><div style="display:flex;gap:5px;padding:4px 0"><div class="ai-dot"></div><div class="ai-dot"></div><div class="ai-dot"></div></div></div>';
    try{
      const res=await fetch('/transactions/flags/'+fid+'/analyse');
      const data=await res.json();
      box.innerHTML=`<div class="ai-panel"><div class="ai-header"><span class="ai-badge">Sentinel AI</span><span class="ai-model">Claude — Forensic Analysis</span></div><div class="ai-text">${data.analysis.replace(/\n/g,'<br>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')}</div></div>`;
    }catch(e){
      box.innerHTML='<div class="ai-panel"><div class="ai-text" style="color:var(--red)">Analysis unavailable. Check your API key.</div></div>';
    }
  });
});
