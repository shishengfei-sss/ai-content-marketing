import re, os, glob

base = "app/routers"
files = glob.glob(base + "/**/*.py", recursive=True) + glob.glob(base + "/*.py")
routes = []
for f in files:
    if f.endswith("__init__.py"):
        continue
    try:
        txt = open(f, encoding="utf-8").read()
    except Exception:
        continue
    prefs = re.findall(r'APIRouter\(prefix\s*=\s*["\']([^"\']+)', txt)
    prefix = prefs[0] if prefs else ""
    pat = re.compile(r'@router\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)')
    for m in pat.finditer(txt):
        method, path = m.group(1).upper(), m.group(2)
        full = (prefix.rstrip("/") + "/" + path.lstrip("/")).replace("//", "/")
        routes.append((method, full, os.path.basename(f)))
routes.sort(key=lambda x: (x[1], x[0]))
print("=== 后端路由总数:", len(routes), "===")
for method, path, f in routes:
    print(f"{method:6} /api/v1{path}   [{f}]")
