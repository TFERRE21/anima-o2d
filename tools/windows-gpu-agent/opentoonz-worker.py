import argparse,json,os,pathlib,tempfile,time,urllib.request,zipfile,subprocess
def call(base,path,token,method="GET",payload=None,timeout=40):
 d=json.dumps(payload).encode() if payload is not None else None;r=urllib.request.Request(base.rstrip("/")+path,data=d,method=method,headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
 with urllib.request.urlopen(r,timeout=timeout) as x:
  b=x.read();return json.loads(b.decode()) if b else {}
def send(base,path,token,zp):
 n=0
 with zp.open("rb") as f:
  while b:=f.read(8*1024*1024):
   r=urllib.request.Request(base.rstrip("/")+path+"/chunks/"+str(n),data=b,method="POST",headers={"Authorization":"Bearer "+token,"Content-Type":"application/octet-stream"})
   with urllib.request.urlopen(r,timeout=180) as x:x.read()
   n+=1
 return call(base,path+"/finalize",token,"POST",{"total_chunks":n},120)
def main():
 p=argparse.ArgumentParser();p.add_argument("--server",default=os.getenv("ANIMA_OPENTOONZ_SERVER","https://animacao2d.vps11710.panel.icontainer.work"));p.add_argument("--token",default=os.getenv("ANIMA_OPENTOONZ_TOKEN",""));p.add_argument("--tcomposer",default=os.getenv("ANIMA_TCOMPOSER",r"C:\Program Files\OpenToonz\tcomposer.exe"));a=p.parse_args();exe=pathlib.Path(a.tcomposer)
 if not a.token:p.error("ANIMA_OPENTOONZ_TOKEN obrigatório.")
 if not exe.is_file():p.error("tcomposer.exe não encontrado: "+str(exe))
 wid=os.getenv("COMPUTERNAME","PC")+"-OpenToonz";print("OPENTOONZ_WORKER_ONLINE",flush=True)
 while True:
  try:
   t=call(a.server,"/api/opentoonz/worker/next?worker_id="+wid,a.token).get("task")
   if not t:continue
   i=t["id"];c=t["config"]
   try:
    scene=pathlib.Path(c["scene_path"]);lo=int(c.get("frame_start",1));hi=int(c.get("frame_end",1))
    if not scene.is_file():raise RuntimeError("Cena .tnz não encontrada: "+str(scene))
    with tempfile.TemporaryDirectory() as d:
     root=pathlib.Path(d);pattern=root/"frame..png";log=root/"render.log";cmd=[str(exe),str(scene),"-o",str(pattern),"-range",str(lo),str(hi),"-step","1","-shrink","1","-multimedia","0","-nthreads","all","-maxtilesize","none"]
     with log.open("w",encoding="utf-8",errors="replace") as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=int(c.get("timeout_seconds",7200)))
     imgs=sorted(root.glob("frame*.png"))
     if r.returncode or len(imgs)!=hi-lo+1:raise RuntimeError("tcomposer exit="+str(r.returncode)+"; quadros="+str(len(imgs))+"/"+str(hi-lo+1)+"; "+log.read_text(errors="replace")[-2000:])
     z=root/"frames.zip"
     with zipfile.ZipFile(z,"w",zipfile.ZIP_STORED) as out:
      for k,img in enumerate(imgs,lo):out.write(img,"frame-"+str(k).zfill(6)+".png")
     send(a.server,"/api/opentoonz/tasks/"+i,a.token,z);print("OPENTOONZ_DONE "+i,flush=True)
   except Exception as e:
    try:call(a.server,"/api/opentoonz/tasks/"+i+"/fail",a.token,"POST",{"error":str(e)})
    except Exception:pass
    print("OPENTOONZ_ERROR "+str(e),flush=True)
  except KeyboardInterrupt:return
  except Exception as e:print("CONNECTION "+str(e),flush=True);time.sleep(5)
if __name__=="__main__":main()
