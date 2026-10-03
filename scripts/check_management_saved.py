"""Compare the management candidate with the authoring readback."""
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]/"outputs/environment-management-20261003/implementation"

def compare(a,b,path=""):
    differences=[]
    if isinstance(a,dict) and isinstance(b,dict):
        for k in a.keys()|b.keys():
            if k not in a or k not in b:
                differences.append((path+"/"+k,a.get(k),b.get(k)))
            else:differences+=compare(a[k],b[k],path+"/"+k)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):differences.append((path+"/length",len(a),len(b)))
        for i,(v,w) in enumerate(zip(a,b)):differences+=compare(v,w,path+"/"+str(i))
    elif a!=b:differences.append((path,a,b))
    return differences

if __name__=="__main__":
    for p in (ROOT/"candidate/canvas").glob("*.pa.yaml"):
        a=yaml.safe_load(p.read_text(encoding="utf-8-sig"));b=yaml.safe_load((ROOT/"saved/canvas"/p.name).read_text(encoding="utf-8-sig"))
        diff=compare(a,b)
        # Authoring omits standard defaults. Verify only these documented
        # defaults, without suppressing any behavioral or nondefault change.
        defaults={"X":"=0","Y":"=0","Mode":"=TextMode.SingleLine","Fill":"=RGBA(255, 255, 255, 1)"}
        normalized=[d for d in diff if d[2] is None and d[0].split("/")[-1] in defaults and d[1]==defaults[d[0].split("/")[-1]]]
        diff=[d for d in diff if d not in normalized]
        print(p.name,len(diff))
        if p.name!="_EditorState.pa.yaml":
            for item in diff:print(item)
            if diff:raise SystemExit("Unexpected saved definition difference.")
