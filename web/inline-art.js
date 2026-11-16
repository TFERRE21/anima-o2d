/* Anima Studio — one approved script => female narrator + CPU-drawn 2D scenes.
   No GPU, image API, ComfyUI, PNG upload, or per-scene approval.
*/
(()=>{
'use strict';
const el=id=>document.getElementById(id);
let episode=null,poll=null,busy=false,watching=null;
const endpoint=()=>'/api/jobs/'+encodeURIComponent(episode);
async function json(url,opts={}){
  const reply=await fetch(url,{cache:'no-store',...opts});
  const value=await reply.json().catch(()=>({detail:'Resposta inválida da aplicação.'}));
  if(!reply.ok)throw new Error(typeof value.detail==='string'?value.detail:(value.message||JSON.stringify(value.detail||value)));
  return value;
}
function statusText(value){
  const p=Number(value.video_progress||0);
  const total=Number(value.total_artworks||0);
  const drawn=Number(value.approved_artworks||0);
  const approved=Boolean(value.story_approved);
  const running=['queued','processing'].includes(value.video_status);
  const done=value.video_status==='done';
  const failed=value.video_status==='failed';
  let badge='ROTEIRO AGUARDANDO APROVAÇÃO';
  let text='Aprove o roteiro. A narradora conta a aventura enquanto as ilustrações são desenhadas e coloridas automaticamente na VPS.';
  if(done){
    badge='VÍDEO 2D PRONTO';
    text='Episódio finalizado com voz narradora e cenas desenhadas em 2D. Veja os arquivos de vídeo abaixo.';
  }else if(running){
    badge='NARRAÇÃO E DESENHO 2D';
    text=(value.message||'Produzindo as cenas narradas.')+
      (drawn&&total?' · '+drawn+'/'+total+' cenas desenhadas.':'');
  }else if(failed){
    badge='FALHA NA PRODUÇÃO 2D';
    text='A produção parou: '+(value.video_error||'Confira os registros do servidor.')+
      ' O roteiro continua salvo.';
  }else if(approved){
    badge='ROTEIRO APROVADO';
    text='Esta história já foi aprovada. Vamos produzi-la no novo motor 2D da VPS, sem esperar GPU ou fotos.';
  }
  // A CPU renderer cannot turn simple procedural characters into
  // an illustrator-quality comic without approved visual assets.
  if(value.production_engine==='2d'){
    const artCount=Number(value.curated_artworks||0);
    const artTotal=Number(value.required_artworks||0);
    const hasHand=Boolean(value.real_hand_ready);
    const artDetail=artTotal>0&&artCount<artTotal
      ?' · Artes profissionais: '+artCount+'/'+artTotal+
       ' (cenas restantes ainda usam ilustração simples).'
      :'';
    const handDetail=hasHand
      ?' · Mão fotográfica disponível.'
      :' · Mão real ainda não configurada; sem lápis artificial.';
    text+=artDetail+handDetail;
  }
  el('inlineArtBadge').textContent=badge;
  el('inlineArtStatus').textContent=text;
  el('inlineArtProgressFill').style.width=(done?100:p)+'%';
  el('inlineArtProgress').setAttribute('aria-valuenow',String(done?100:p));
  el('inlineArtProgressText').textContent=(done?'100%':p+'%')+
    (drawn&&total?' · '+drawn+'/'+total+' cenas ilustradas':'')+
    ' · Narradora + desenho progressivo';
  const btn=el('approveStory');
  btn.disabled=running||done;
  btn.textContent=done?'✓ Vídeo 2D concluído':
    running?'✓ Produzindo automaticamente em 2D':
    approved?'▶ Produzir esta história em 2D':'✓ Aprovar roteiro e produzir vídeo 2D';
  if((running||done||failed)&&watching!==episode){
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
    const state=await json(endpoint()+'/art/board');
    if(state.job_id===episode)statusText(state);
  }catch(error){
    el('inlineArtStatus').textContent='Não foi possível acompanhar a produção: '+error.message;
  }finally{busy=false}
}
function stop(){
  if(poll)clearInterval(poll);
  poll=null;episode=null;watching=null;
}
window.stopInlineArt=stop;
window.prepareInlineArt=async id=>{
  if(!id)return;
  if(id!==episode)stop();
  episode=id;
  await refresh();
  if(!poll)poll=setInterval(refresh,5000);
};
window.startInlineArt=async id=>{
  if(!id)return;
  episode=id;
  const btn=el('approveStory');
  btn.disabled=true;
  btn.textContent='Iniciando narradora e desenhos 2D…';
  el('inlineArtStatus').textContent='Enviando o roteiro para o motor 2D da VPS. Não é necessária GPU.';
  try{
    await json(endpoint()+'/story/approve',{method:'POST'});
    el('renderMessage').textContent='Produção iniciada: narração → desenho das cenas → vídeo 2D.';
    await window.prepareInlineArt(id);
  }catch(error){
    btn.disabled=false;
    btn.textContent='▶ Produzir história em 2D';
    el('inlineArtStatus').textContent='Falha ao iniciar a produção: '+error.message;
  }
};
})();