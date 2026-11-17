/* Anima Studio: approved 2D comic cast, narrated drawing and live preview.
   One-time official model installation; no per-scene approval.
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
  if(value.production_engine==='2d'){
    if(value.advanced_illustration_ready){
      text+=' · Cenários ilustrados por IA: ativos.';
    }else{
      text+=' · Cenários em modo local simples. Para qualidade de ilustração detalhada, configure a API de imagens na VPS.';
    }
    if(value.real_hand_ready)text+=' · Mão real configurada.';
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
  if(running && watching!==episode){
    watching=episode;
    const card=el('activeJobCard');
    if(card)card.style.display='block';
    if(typeof watchJob==='function')watchJob(episode);
  }
  if(!running && watching===episode && (done||failed))watching=null;
}
let previewClipKey='',clipStartedAt=0;
async function refreshLivePreview(value){
  const area=el('inlineLiveArea'),image=el('inlineLiveImage');
  const video=el('inlineLiveVideo'),placeholder=el('inlineLivePlaceholder');
  const badge=el('inlineLiveState'),frame=el('inlineLiveFrame');
  const caption=el('inlineLiveCaption');
  if(!area||!image||!video||!episode)return;
  const running=['queued','processing'].includes(value.video_status);
  const done=value.video_status==='done';
  area.style.display=running||done?'block':'none';
  if(!running&&!done){
    video.pause();video.removeAttribute('src');video.load();previewClipKey='';
    return;
  }
  try{
    const state=await json(endpoint()+'/render-status');
    const fmt=state.format||'16:9';
    frame.style.aspectRatio=fmt==='9:16'?'9 / 16':'16 / 9';
    badge.textContent=done?'FINALIZADO':state.live_scene_ready?'REPRODUZINDO CENA REAL':'DESENHANDO AO VIVO';
    if(state.live_scene_ready && state.live_scene_number !== null){
      const clipKey=episode+':'+fmt+':'+state.live_scene_number;
      if(previewClipKey!==clipKey){
        previewClipKey=clipKey;
        clipStartedAt=Date.now();
        video.src=endpoint()+'/live-scene/'+encodeURIComponent(fmt)+'/'+state.live_scene_number;
        video.style.display='block';
        image.style.display='none';
        placeholder.style.display='none';
        video.play().catch(()=>{video.controls=true;});
      }
      // Keep displaying the real playable clip instead of swapping image URLs.
      caption.textContent='Cena '+(state.live_scene_number+1)+' reproduzida do vídeo real, enquanto a VPS continua a próxima.';
    }else if(state.preview_ready){
      video.style.display='none';
      image.onload=()=>{image.style.display='block';placeholder.style.display='none';};
      image.onerror=()=>{image.style.display='none';placeholder.style.display='block';};
      image.src=endpoint()+'/preview/'+encodeURIComponent(fmt)+'?t='+Date.now();
      caption.textContent=(state.message||'')+' · Quadros atualizados durante o desenho.';
    }else{
      video.style.display='none';
      image.style.display='none';
      placeholder.style.display='block';
      placeholder.textContent='Preparando narração e o primeiro quadrinho…';
      caption.textContent=state.message||'O primeiro vídeo aparecerá após a renderização da cena.';
    }
  }catch(error){caption.textContent='Falha ao consultar a prévia: '+error.message;}
}
async function refresh(){
  if(!episode||busy||el('storyPreview').style.display==='none')return;
  busy=true;
  try{
    const state=await json(endpoint()+'/art/board');
    if(state.job_id===episode){statusText(state);await refreshLivePreview(state);}
  }catch(error){
    el('inlineArtStatus').textContent='Não foi possível acompanhar a produção: '+error.message;
  }finally{busy=false}
}
function stop(){
  if(poll)clearInterval(poll);
  poll=null;episode=null;watching=null;previewClipKey='';
}
window.stopInlineArt=stop;
window.prepareInlineArt=async id=>{
  if(!id)return;
  if(id!==episode)stop();
  episode=id;
  await refresh();
  if(!poll)poll=setInterval(refresh,2500);
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