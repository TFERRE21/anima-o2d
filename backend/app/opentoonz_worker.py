import os,queue,shutil,time,uuid,hmac
from pathlib import Path
from datetime import datetime,timezone
from fastapi import APIRouter,Header,HTTPException,Request
router=APIRouter(prefix="/api/opentoonz",tags=["OpenToonz"]); TASKS={}; Q=queue.Queue(); SEEN={}
def auth(a):
 e=os.getenv("ANIMA_OPENTOONZ_TOKEN",os.getenv("ANIMA_WORKER_TOKEN","")).strip(); s=(a or "").removeprefix("Bearer ").strip()
 if not e: raise HTTPException(503,"Configure ANIMA_OPENTOONZ_TOKEN.")
 if not s or not hmac.compare_digest(s,e): raise HTTPException(401,"Token inválido.")
@router.get("/worker/status")
def status(authorization:str|None=Header(default=None)):
 auth(authorization); w=[n for n,t in SEEN.items() if time.time()-t<75]; return {"engine":"opentoonz","connected":bool(w),"workers":w,"queued":Q.qsize(),"active":sum(t["status"]=="running" for t in TASKS.values())}
@router.get("/worker/next")
def next_task(worker_id:str="windows-opentoonz",authorization:str|None=Header(default=None)):
 auth(authorization); SEEN[worker_id]=time.time()
 try:i=Q.get(timeout=20)
 except queue.Empty:return {"task":None}
 t=TASKS.get(i)
 if not t or t["status"]!="queued":return {"task":None}
 t.update(status="running",worker_id=worker_id,started_at=datetime.now(timezone.utc).isoformat()); return {"task":{"id":i,"config":t["config"]}}
@router.post("/tasks",status_code=202)
async def create(request:Request,authorization:str|None=Header(default=None)):
 auth(authorization); c=(await request.json()).get("config"); p=str((c or {}).get("scene_path",""))
 if not p.lower().endswith(".tnz"):raise HTTPException(400,"Informe o caminho de uma cena .tnz existente no PC do agente.")
 a,b=int(c.get("frame_start",1)),int(c.get("frame_end",1))
 if a<1 or b<a or b-a>20000:raise HTTPException(400,"Intervalo inválido.")
 i=uuid.uuid4().hex; TASKS[i]={"id":i,"status":"queued","config":c,"created_at":datetime.now(timezone.utc).isoformat()};Q.put(i);return {"task_id":i,"status":"queued","engine":"opentoonz"}
@router.post("/tasks/{i}/chunks/{n}",status_code=202)
async def chunk(i:str,n:int,request:Request,authorization:str|None=Header(default=None)):
 auth(authorization);t=TASKS.get(i);d=await request.body()
 if not t or t["status"]!="running":raise HTTPException(404,"Tarefa inativa.")
 if not d or len(d)>12*1024*1024 or n<0 or n>10000:raise HTTPException(400,"Bloco inválido.")
 p=Path(os.getenv("ANIMA_STORAGE","/data/jobs"))/"opentoonz"/i/"chunks";p.mkdir(parents=True,exist_ok=True);f=p/f"{n:06d}.part";tmp=f.with_suffix(".tmp");tmp.write_bytes(d);tmp.replace(f);return {"received":n}
@router.post("/tasks/{i}/finalize")
def finalize(i:str,payload:dict,authorization:str|None=Header(default=None)):
 auth(authorization);t=TASKS.get(i);n=int(payload.get("total_chunks",0));root=Path(os.getenv("ANIMA_STORAGE","/data/jobs"))/"opentoonz"/i
 if not t or t["status"]!="running":raise HTTPException(404,"Tarefa inativa.")
 if n<1 or n>10001:raise HTTPException(400,"Número de blocos inválido.")
 tmp=root/"result.zip.part";out=root/"result.zip"
 try:
  with tmp.open("wb") as dst:
   for x in range(n):
    f=root/"chunks"/f"{x:06d}.part"
    if not f.is_file():raise HTTPException(400,f"Bloco {x} ausente.")
    with f.open("rb") as src:shutil.copyfileobj(src,dst,1024*1024)
  if not tmp.stat().st_size:raise HTTPException(400,"ZIP vazio.")
  tmp.replace(out)
 except Exception:tmp.unlink(missing_ok=True);raise
 shutil.rmtree(root/"chunks",ignore_errors=True);t.update(status="done",result_path=str(out),completed_at=datetime.now(timezone.utc).isoformat());return {"status":"done","bytes":out.stat().st_size}
@router.post("/tasks/{i}/fail")
async def fail(i:str,request:Request,authorization:str|None=Header(default=None)):
 auth(authorization);t=TASKS.get(i)
 if not t:raise HTTPException(404,"Tarefa inexistente.")
 t.update(status="failed",error=str((await request.json()).get("error","Falha"))[:3000]);return {"status":"failed"}
@router.get("/tasks/{i}")
def get_task(i:str,authorization:str|None=Header(default=None)):
 auth(authorization);t=TASKS.get(i)
 if not t:raise HTTPException(404,"Tarefa inexistente.")
 return {k:t.get(k) for k in ("id","status","error","result_path","created_at","started_at","completed_at")}
