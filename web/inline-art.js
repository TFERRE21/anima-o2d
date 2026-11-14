/* Unified story → AI illustration → review → video production.
 * No redirect. Characters are permanent season assets; backgrounds are per planet.
 */
(()=>{
'use strict';
const el=id=>document.getElementById(id);
let activeJob=null, pollTimer=null, board=null, refreshing=false, lastArtDigest=null;
const clean=x=>String(x??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const castNames={luna:'Luna',tomi:'Tomi',pipo:'Pipo'};
const titleFor=id=>castNames[id]||'Cena '+(Number((id.match(/scene-(\d+)/)||[])[1]||0)+1);
const apiRoot=id=>'/api/jobs/'+encodeURIComponent(id);
const textMessage=text=>{el('inlineArtStatus').textContent=text;};
let token=sessionStorage.getItem('anima_comfy_token')||'';

function authorize(){
  token=el('inlineArtToken').value.trim();
  if(!token){el('inlineArtToken').focus();throw new Error('Informe uma vez o token de aprovação artística, no campo abaixo das imagens.');}
  sessionStorage.setItem('anima_comfy_token',token);
  return {'Authorization':'Bearer '+token};
}

async function jsonRequest(url,options={}){
  const response=await fetch(url,{cache:'no-store',...options});
  const body=await response.json().catch(()=>({detail:'Resposta inválida da API'}));
  if(!response.ok){
    const detail=body.detail||body.message||body.reason||'Falha ao consultar serviço de arte.';
    throw new Error(typeof detail==='string'?detail:(detail.reason||JSON.stringify(detail)));
  }
  return body;
}

function taskFor(tasks,asset,format){
  return tasks.find(task=>task.asset_id===asset&&
    ((asset in castNames)||task.format===format))||null;
}

function statusName(task){
  if(!task)return 'Aguardando envio';
  if(task.has_image)return 'Imagem pronta para revisão';
  if(task.status==='running')return 'IA desenhando…';
  if(task.status==='queued')return 'Na fila do gerador';
  if(task.status==='failed')return 'Falha · pode retentar';
  return task.status||'Aguardando';
}

function tile(asset,format,state,tasks,official=false){
  const approved=Boolean(state.approved?.[asset]);
  const task=taskFor(tasks,asset,format);
  const candidate=Boolean(task?.has_image && task?.status==='done' && !task?.approved);
  const stamp=(official&&approved?' · FIXO NA SÉRIE':approved?' · Aprovado':' · '+statusName(task));
  const candidateUrl=candidate?apiRoot(activeJob)+'/art/candidate/'+encodeURIComponent(task.id):'';
  const approvedUrl=apiRoot(activeJob)+'/art/approved/'+encodeURIComponent(asset)+'?fmt='+encodeURIComponent(format);
  const image=(candidate && (!official || !approved)
       ?'<img src="'+candidateUrl+'" alt="Imagem IA de '+clean(asset)+'" title="Clique para ampliar" data-inline-view="'+candidateUrl+'">'
       :approved
        ?'<img src="'+approvedUrl+'" alt="Arte oficial de '+clean(asset)+'" title="Clique para ampliar" data-inline-view="'+approvedUrl+'">'
        :'<div class="inline-art-placeholder">'+(task?.status==='running'?'Gerando imagem…':task?.status==='failed'?'Erro no gerador':'Aguardando imagem')+'</div>');
  const approveBtn=(candidate && (!official||!approved)
       ?'<button class="btn good" type="button" data-inline-approve="'+clean(task.id)+'">✓ Aprovar</button>':'');
  const retryBtn=(official&&approved?'':task?.status==='queued'||task?.status==='running'?''
      :'<button class="btn ghost" type="button" data-inline-regenerate="'+clean(asset)+'" data-format="'+clean(format)+'">↻ Refazer</button>');
  return '<div class="inline-art-tile" data-inline-asset="'+clean(asset)+'"><div class="inline-art-head"><b>'+clean(titleFor(asset))+'</b>'+
    '<span class="inline-art-tag">'+clean(format)+'</span></div>'+image+
    '<div class="'+(approved?'inline-art-confirm':'inline-art-tag')+'">'+clean(stamp)+'</div>'+
    '<div class="inline-art-actions">'+approveBtn+retryBtn+'</div></div>';
}

function renderBoard(data){
  board=data;
  const formats=Object.entries(data.formats_status);
  const primary=formats[0]?.[1]||{approved:{},required:[]};
  const digest=JSON.stringify([data.formats_status,data.tasks.map(t=>[t.id,t.status,t.approved,t.has_image])]);
  // Keep artwork images mounted between status polls; do not reload 30 PNGs
  // every six seconds when only the worker heartbeat changed.
  if(digest!==lastArtDigest){
    lastArtDigest=digest;
    const allFixed=['luna','tomi','pipo'];
    const castFmt=formats[0]?.[0]||'9:16';
    el('inlineCast').innerHTML=allFixed.map(id=>tile(id,castFmt,primary,data.tasks,true)).join('');
    const scenes=[];
    for(const [fmt,state] of formats){
      for(const asset of state.required){
        if(asset in castNames)continue;
        scenes.push(tile(asset,fmt,state,data.tasks,false));
      }
    }
    el('inlineScenes').innerHTML=scenes.join('')||'<p class="muted">Nenhum cenário selecionado.</p>';
  }
  if(data.ready && data.story_approved){
    el('inlineArtBadge').textContent='ARTES APROVADAS';
    el('inlineArtBadge').className='badge ready';
    el('inlineArtRender').disabled=false;
    textMessage('Todos os personagens oficiais e cenários deste episódio estão aprovados. O vídeo já pode ser montado.');
    el('renderMessage').textContent='Artes aprovadas — já pode montar o vídeo abaixo.';
  }else{
    el('inlineArtBadge').textContent=data.story_approved?'GERANDO ARTE':'AGUARDANDO ROTEIRO';
    el('inlineArtBadge').className='badge pending';
    el('inlineArtRender').disabled=true;
    const pending=data.tasks.filter(x=>x.status==='queued'||x.status==='running').length;
    textMessage(data.story_approved
     ?data.missing_count+' materiais ainda pendentes. '+pending+' tarefas na fila. '+(data.worker_connected?'Motor de imagens conectado.':'Motor de imagens offline: as tarefas foram salvas e iniciarão quando o agente conectar.')+' Revise e aprove as imagens prontas.'
     :'Aprove o roteiro para começar a gerar imagens automaticamente.');
  }
  el('approveStory').disabled=!!data.story_approved;
  el('approveStory').textContent=data.story_approved?'✓ Roteiro aprovado · imagens iniciadas':'✓ Aprovar roteiro e gerar imagens';
  // Artwork thumbnails are read-only files served by this same panel.
}

async function refresh(){
  if(refreshing||!activeJob||el('storyPreview').style.display==='none')return;
  refreshing=true;
  try{
    const result=await jsonRequest(apiRoot(activeJob)+'/art/board');
    if(result.job_id===activeJob)renderBoard(result);
  }catch(err){textMessage('Não foi possível consultar imagens: '+err.message)}
  finally{refreshing=false}
}

function stop(){
  if(pollTimer){clearInterval(pollTimer);pollTimer=null;}
  board=null;activeJob=null;lastArtDigest=null;
}

window.stopInlineArt=stop;
window.prepareInlineArt=async id=>{
  if(!id)return;
  if(activeJob!==id)stop();
  activeJob=id;
  el('inlineArtPanel').style.display='block';
  el('approveStory').disabled=false;
  el('approveStory').textContent='✓ Aprovar roteiro e gerar imagens';
  await refresh();
  if(!pollTimer)pollTimer=setInterval(refresh,6000);
};

window.startInlineArt=async id=>{
  if(!id)return;
  activeJob=id;
  const button=el('approveStory');
  button.disabled=true;button.textContent='Enviando imagens para o motor…';
  textMessage('Roteiro aprovado. Preparando Luna, Tomi, Pipo e os novos cenários automaticamente…');
  try{
    const data=await jsonRequest(apiRoot(id)+'/story/approve',{method:'POST'});
    el('renderMessage').textContent=data.worker_connected?
      'Roteiro aprovado. Imagens sendo geradas no mesmo painel.':
      'Roteiro aprovado. Geração agendada; ligue o agente ComfyUI para produzir as imagens.';
    await window.prepareInlineArt(id);
  }catch(err){
    button.disabled=false;button.textContent='✓ Aprovar roteiro e gerar imagens';
    textMessage('Falha ao iniciar a geração: '+err.message);
  }
};

async function approveTask(id){
  if(!activeJob)return;
  try{
    textMessage('Validando PNG e salvando imagem aprovada…');
    await jsonRequest(apiRoot(activeJob)+'/art/approve/'+encodeURIComponent(id),{
      method:'POST',headers:authorize()
    });
    await refresh();
  }catch(e){textMessage('Não foi possível aprovar: '+e.message)}
}

async function regenerate(asset,format){
  if(!activeJob)return;
  try{
    textMessage('Solicitando nova versão de '+titleFor(asset)+'…');
    await jsonRequest(apiRoot(activeJob)+'/art/generate',{
      method:'POST',headers:{...authorize(),'Content-Type':'application/json'},
      body:JSON.stringify({format,asset_id:asset})
    });
    await refresh();
  }catch(e){textMessage('Não foi possível regenerar: '+e.message)}
}

async function renderVideo(){
  if(!activeJob||!board?.ready)return;
  const button=el('inlineArtRender');
  button.disabled=true;button.textContent='Preparando vídeo…';
  try{
    const result=await jsonRequest(apiRoot(activeJob)+'/render',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({formats:board.formats})
    });
    el('activeJobCard').style.display='block';
    el('renderMessage').textContent='Personagens fixos e cenários aprovados. Blender montando o vídeo com o áudio do roteiro.';
    textMessage('Produção do vídeo iniciada. Acompanhe a prévia ao vivo mais abaixo.');
    watchJob(result.job_id);
    el('activeJobCard').scrollIntoView({behavior:'smooth',block:'center'});
  }catch(e){
    textMessage('Falha ao iniciar vídeo: '+e.message);
    button.disabled=false;button.textContent='▶ Montar vídeo com artes aprovadas';
  }
}

function init(){
  el('inlineArtToken').value=token;
  el('inlineArtToken').addEventListener('change',()=>{
    token=el('inlineArtToken').value.trim();
    if(token)sessionStorage.setItem('anima_comfy_token',token);
    refresh();
  });
  el('inlineArtRefresh').addEventListener('click',refresh);
  el('inlineArtRetry').addEventListener('click',async()=>{
    if(!activeJob)return;
    try{
      textMessage('Verificando tarefas pendentes e enviando o que faltar…');
      await jsonRequest(apiRoot(activeJob)+'/story/approve',{method:'POST'});
      await refresh();
    }catch(e){textMessage('Falha na fila: '+e.message)}
  });
  el('inlineArtRender').addEventListener('click',renderVideo);
  el('inlineArtPanel').addEventListener('click',event=>{
    const approve=event.target.closest('[data-inline-approve]');
    const regen=event.target.closest('[data-inline-regenerate]');
    const view=event.target.closest('[data-inline-view]');
    if(approve)approveTask(approve.dataset.inlineApprove);
    else if(regen)regenerate(regen.dataset.inlineRegenerate,regen.dataset.format);
    else if(view){
      el('inlineArtModalImage').src=view.dataset.inlineView;
      el('inlineArtModal').showModal();
    }
  });
  el('inlineArtModalClose').addEventListener('click',()=>el('inlineArtModal').close());
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
else init();
})();
