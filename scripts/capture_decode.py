import json,base64,sys,pathlib
from PIL import Image
src,name=sys.argv[1],sys.argv[2]
d=json.loads(open(src,encoding='utf-8').read())
out=pathlib.Path(__file__).parent / "work" / name
out.write_bytes(base64.b64decode(d['returnValue']['image']['data']))
im=Image.open(out); im.thumbnail((1100,620)); im.save(out); print(im.size)
