/* Anima Studio — one-click script → AI images → automatic Blender video.
   No PNG uploads, artwork approvals or manual render buttons on this screen.
   Image generation uses the configured cloud engine or ComfyUI workstation.
   Tasks persist across restart, with accurate readiness diagnostics.
*/
(()=>{
'use strict';
const el = id => document.getElementById(id);
let episode=null, poll=null, busy=false, lastView=null, watching=null;
const esc = s => String(s??'').replace(/[&<>"']/g, c => (
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
));
const castNames = {luna:'Luna', tomi:'Tomi', pipo:'Pipo'};
const endpoint = () => '/api/jobs/'+encodeURIComponent(episode);
const label = id => castNames[id] || 'Cena '+(Number((id.match(/scene-(\d+)/)||[])[1]||0)+1);

async function json(url, options={}){
  const response = await fetch(url, {cache:'no-store', ...options});
  const body = await response.json().catch(()=>({detail:'Resposta inválida da API.'}));
  if(!response.ok){
    const detail=body.detail || body.message || 'Falha ao consultar API.';
    throw new Error(typeof detail === 'string' ? detail : (detail.reason || JSON.stringify(detail)));
  }
  return body;
}
const message = str => {el('inlineArtStatus').textContent=str};
const taskFor = (tasks, asset, format) =>
  tasks.find(t => t.asset_id===asset && (asset in castNames || t.format===format));

function tile(asset, format, state, tasks, shared){
  const approved=Boolean(state.approved?.[asset]);
  const task=taskFor(tasks, asset, format);
  const candidate=task?.has_image && task.status==='done';
  const imageSrc=approved
    ?endpoint()+'/art/approved/'+encodeURIComponent(asset)+'?fmt='+encodeURIComponent(format)
    :candidate?endpoint()+'/art/candidate/'+encodeURIComponent(task.id):null;
  let status;
  if(approved)status=shared?'PERSONAGEM OFICIAL · FIXO':'CENÁRIO CONCLUÍDO';
  else if(task?.status==='failed')status='Verificando nova tentativa…';
  else if(task?.status==='running')status='IA desenhando…';
  else if(candidate)status='Imagem gerada · validando…';
  else if(task?.status==='queued')status='Na fila do gerador';
  else status='Preparando geração';
  const image=imageSrc
    ?'<img src="'+esc(imageSrc)+'" alt="'+esc(label(asset))+'" data-inline-view="'+esc(imageSrc)+'">'
    :'';
  return '<div class="inline-art-tile">'+
    '<div class="inline-art-head"><b>'+esc(label(asset))+'</b><span class="inline-art-tag">'+esc(format)+'</span></div>'+
    image+'<div class="'+(approved?'inline-art-confirm':'inline-art-tag')+'">'+esc(status)+'</div></div>';
}

function render(state){
  const formats=Object.entries(state.formats_status||{});
  const tasks=state.tasks||[];
  const first=formats[0]||['9:16',{approved:{},required:[]}];
  const fingerprint=JSON.stringify([state.formats_status, tasks.map(t=>[t.id,t.status,t.has_image,t.approved])]);
  if(fingerprint!==lastView){
    lastView=fingerprint;
    const hasImage=(asset,fmt,record)=>Boolean(record.approved?.[asset])||
      Boolean(taskFor(tasks,asset,fmt)?.has_image);
    const cast=['luna','tomi','pipo']
      .filter(id=>hasImage(id,first[0],first[1]))
      .map(id=>tile(id, first[0], first[1], tasks,true));
    const scenes=[];
    for(const [fmt, data] of formats){
      for(const id of data.required||[]){
        if(id in castNames||!hasImage(id,fmt,data))continue;
        scenes.push(tile(id,fmt,data,tasks,false));
      }
    }
    el('inlineCast').innerHTML=cast.join('');
    el('inlineScenes').innerHTML=scenes.join('');
    el('inlineCastSection').style.display=cast.length?'block':'none';
    el('inlineScenesSection').style.display=scenes.length?'block':'none';
    el('inlineArtGallery').style.display=(cast.length||scenes.length)?'block':'none';
  }
  const total=Number(state.total_artworks||0);
  const approved=Number(state.approved_artworks||0);
  const pct=total?Math.round(100*approved/total):0;
  el('inlineArtProgressFill').style.width=pct+'%';
  el('inlineArtProgress').setAttribute('aria-valuenow',String(pct));
  el('inlineArtProgressText').textContent=approved+' de '+total+' imagens prontas · '+pct+'%';
  const status=state.video_status;
  const ongoing=['queued','processing'].includes(status);
  const done=status==='done';
  const failed=status==='failed';
  const waiting=state.auto_production && !state.ready &&
       !state.image_engine?.ready && !done && !ongoing;
  let badge='AGUARDANDO APROVAÇÃO';
  let detail='Clique em Aprovar roteiro e produzir vídeo. Todas as demais etapas serão automáticas.';
  if(state.image_engine?.credits_exhausted?.length && !state.image_engine.ready && !done && !ongoing){
    badge='PRODUÇÃO PAUSADA · SEM CRÉDITOS';
    detail=state.image_engine.detail+
      ' O roteiro e as tarefas foram preservados. A geração continuará automaticamente quando um motor com créditos estiver disponível.';
  }else if(state.art_stage==='error'){
    badge='ERRO NAS IMAGENS';
    detail='Falha na geração automática: '+(state.art_error||'Consulte os registros do gerador.');
  }else if(done){
    badge='VÍDEO CONCLUÍDO';
    detail='O vídeo foi montado com os personagens oficiais e cenários deste planeta. Veja os arquivos abaixo.';
  }else if(failed && state.ready){
    badge='ERRO NO VÍDEO';
    detail='As imagens estão prontas, mas o motor de vídeo falhou: '+(state.video_error||'verifique o Blender');
  }else if(ongoing){
    badge='MONTANDO O VÍDEO';
    detail='Imagens criadas. O Blender e FFmpeg estão montando o episódio automaticamente. '+(state.video_progress||0)+'% concluído.';
  }else if(state.ready && state.auto_production){
    badge='PREPARANDO O VÍDEO';
    detail='Imagens concluídas. Iniciando automaticamente animação, vozes e montagem…';
  }else if(waiting){
    badge='AGUARDANDO GERADOR DE IMAGENS';
    detail='Roteiro aprovado, mas o gerador não está disponível nesta aplicação. '+(state.image_engine?.detail||'Conecte o motor de imagens.')+' Nenhuma foto precisa ser enviada.';
  }else if(state.auto_production){
    const pending=tasks.filter(t=>t.status==='queued'||t.status==='running').length;
    badge='GERANDO IMAGENS';
    detail='Motor '+(state.image_engine?.provider||'de imagens')+' preparando a arte: '+state.missing_count+' imagens pendentes · '+pending+' tarefas na produção. O vídeo começará automaticamente assim que estiverem prontas.';
  }
  el('inlineArtBadge').textContent=badge;
  el('inlineArtStatus').textContent=detail;
  el('approveStory').disabled=Boolean(state.story_approved);
  el('approveStory').textContent=state.story_approved
     ?'✓ Roteiro aprovado · produção automática'
     :'✓ Aprovar roteiro e produzir vídeo';
  if(state.auto_production && (ongoing||done||failed) && watching!==episode){
    watching=episode;
    const card=el('activeJobCard');
    if(card)card.style.display='block';
    if(typeof watchJob==='function')watchJob(episode);
  }
}

async function refresh(){
  if(!episode||busy||el('storyPreview').style.display==='none')return;
  busy=true;
  try{
    const result=await json(endpoint()+'/art/board');
    if(result.job_id===episode)render(result);
  }catch(e){message('Erro ao acompanhar produção: '+e.message)}
  finally{busy=false}
}

function stop(){
  if(poll)clearInterval(poll);
  poll=null;episode=null;lastView=null;watching=null;
}

window.stopInlineArt=stop;
window.prepareInlineArt=async id=>{
  if(!id)return;
  if(id!==episode)stop();
  episode=id;
  await refresh();
  if(!poll)poll=setInterval(refresh,6000);
};
window.startInlineArt=async id=>{
  if(!id)return;
  episode=id;
  const btn=el('approveStory');
  btn.disabled=true;btn.textContent='Iniciando produção automática…';
  message('Roteiro aprovado. Enviando personagens oficiais e cenários para o gerador de imagens…');
  try{
    const approval=await json(endpoint()+'/story/approve',{method:'POST'});
    el('renderMessage').textContent=approval.worker_connected
      ?'Produção iniciada: imagens → animação → vídeo.'
      :'Roteiro aprovado, mas o motor de imagens está desconectado. A fila está salva.';
    await window.prepareInlineArt(id);
  }catch(e){
    btn.disabled=false;btn.textContent='✓ Aprovar roteiro e produzir vídeo';
    message('Não foi possível iniciar a produção: '+e.message);
  }
};

function init(){
  const panel=el('inlineArtPanel');
  if(!panel)return;
  panel.addEventListener('click',event=>{
    const image=event.target.closest('[data-inline-view]');
    if(image){
      el('inlineArtModalImage').src=image.dataset.inlineView;
      el('inlineArtModal').showModal();
    }
  });
  el('inlineArtModalClose')?.addEventListener('click',()=>el('inlineArtModal').close());
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
else init();
})();
