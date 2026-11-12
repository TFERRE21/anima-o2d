import os, time, json, pathlib, requests, uuid
from urllib.parse import urljoin

SERVER=os.environ["ANIMA_STUDIO_URL"].rstrip("/")
TOKEN=os.environ["ANIMA_COMFY_TOKEN"]
COMFY=os.getenv("COMFYUI_URL","http://127.0.0.1:8188").rstrip("/")
WORKER=os.getenv("ANIMA_COMFY_WORKER_ID",os.environ.get("COMPUTERNAME","windows")+"-comfyui")
ROOT=pathlib.Path(__file__).resolve().parent
WF=pathlib.Path(os.getenv("COMFYUI_API_WORKFLOW",str(ROOT/"workflow_api.json")))
OUT=pathlib.Path(os.getenv("ANIMA_COMFY_OUTPUT",str(ROOT/"generated")))
OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers["Authorization"]="Bearer "+TOKEN

def report(task_id,status,message="",output=None):
    S.post(f"{SERVER}/api/comfy/tasks/{task_id}/result",json={"status":status,"message":message,"output":output},timeout=30).raise_for_status()

def make_workflow(cfg):
    if not WF.is_file(): raise RuntimeError("Falta workflow_api.json. Exporte o workflow no formato API do ComfyUI e coloque ao lado do agente.")
    wf=json.loads(WF.read_text(encoding="utf-8"))
    nodes=list(wf.values())
    def find(cls):
        for n in nodes:
            if n.get("class_type")==cls:return n["inputs"]
        raise RuntimeError("Nó ausente no workflow API: "+cls)
    find("CheckpointLoaderSimple")["ckpt_name"]=cfg["checkpoint"]
    find("CLIPTextEncode")["text"]=cfg["prompt"]
    clips=[n["inputs"] for n in nodes if n.get("class_type")=="CLIPTextEncode"]
    if len(clips)>1: clips[1]["text"]=cfg["negative_prompt"]
    k=find("KSampler"); k.update(steps=cfg["steps"],cfg=cfg["cfg"],seed=cfg["seed"] if cfg["seed"]>=0 else int(time.time())%2147483647)
    find("EmptyLatentImage").update(width=cfg["width"],height=cfg["height"],batch_size=1)
    find("SaveImage")["filename_prefix"]="AnimaStudio"
    return wf

def main():
    print("Agente Anima Studio / ComfyUI online:",COMFY,flush=True)
    requests.get(COMFY+"/system_stats",timeout=10).raise_for_status()
    while True:
        try:
            S.post(SERVER+"/api/comfy/heartbeat",params={"worker_id":WORKER},timeout=15).raise_for_status()
            task=S.get(SERVER+"/api/comfy/next",params={"worker_id":WORKER},timeout=30).json().get("task")
            if not task: continue
            tid=task["id"]
            try:
                prompt_id=requests.post(COMFY+"/prompt",json={"prompt":make_workflow(task["config"]),"client_id":str(uuid.uuid4())},timeout=60).json()["prompt_id"]
                while True:
                    time.sleep(2)
                    hist=requests.get(COMFY+"/history/"+prompt_id,timeout=30).json()
                    if prompt_id not in hist: continue
                    outputs=hist[prompt_id].get("outputs",{})
                    images=[img for node in outputs.values() for img in node.get("images",[])]
                    if not images: raise RuntimeError("ComfyUI terminou sem retornar imagem.")
                    img=images[0]
                    data=requests.get(COMFY+"/view",params=img,timeout=60).content
                    target=OUT/(tid+"_"+pathlib.Path(img["filename"]).name)
                    target.write_bytes(data)
                    report(tid,"done","Imagem gerada com sucesso.",str(target))
                    print("Imagem salva:",target,flush=True); break
            except Exception as e:
                report(tid,"failed",str(e)); print("Falha:",e,flush=True)
        except Exception as e:
            print("Conexão/ComfyUI:",e,flush=True); time.sleep(5)

if __name__=="__main__": main()
