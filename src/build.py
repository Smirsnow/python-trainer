import io, json, re, sys, html, contextlib
sys.stdout.reconfigure(encoding='utf-8')
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from tasks import TOPICS, VARY


def run(code, inputs):
    q = list(inputs)

    def _input(prompt=""):
        if not q:
            raise EOFError("NOINPUT")
        return q.pop(0)

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(code, "<code>", "exec"), {"__name__": "__main__", "input": _input})
    assert not q, f"unused inputs {q}"
    return out.getvalue()


def norm(s):
    lines = [l.rstrip() for l in s.replace("\r", "").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    return "\n".join(lines).replace("ё", "е").replace("Ё", "Е")


def inline(s):
    s = html.escape(s, quote=False)
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    s = re.sub(r"`([^`]+)`", keep, s)          # код прячем, чтобы его не трогало оформление
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: "<code>" + codes[int(m.group(1))] + "</code>", s)


def md(text):
    out, para, ul, tip = [], [], [], []
    lines = text.split("\n")
    i = 0

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>"); para.clear()
        if ul:
            out.append("<ul>" + "".join("<li>" + inline(x) + "</li>" for x in ul) + "</ul>"); ul.clear()
        if tip:
            out.append('<div class="tip">💡 ' + inline(" ".join(tip)) + "</div>"); tip.clear()

    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            flush()
            kind = l[3:].strip() or "py"
            j = i + 1
            buf = []
            while not lines[j].startswith("```"):
                buf.append(lines[j]); j += 1
            body = html.escape("\n".join(buf), quote=False)
            if kind == "out":
                typed = "[[" in body
                body = re.sub(r"\[\[(.+?)\]\]", r'<span class="typed">\1</span>', body)
                legend = '<span class="legend">⌨️ жёлтым — то, что ввёл человек</span>' if typed else ""
                out.append('<div class="outblock"><span class="lbl">На экране:</span>' + legend + '<pre>' + body + "</pre></div>")
            else:
                out.append('<pre class="code">' + body + "</pre>")
            i = j + 1
            continue
        if l.startswith("## "):
            flush(); out.append("<h3>" + inline(l[3:]) + "</h3>")
        elif l.startswith("- "):
            if para or tip:
                flush()
            ul.append(l[2:])
        elif l.startswith("> "):
            if para or ul: flush()
            tip.append(l[2:])
        elif not l.strip():
            flush()
        else:
            if ul or tip: flush()
            para.append(l)
        i += 1
    flush()
    return "\n".join(out)


errors = []
data = []
total = 0
for t in TOPICS:
    tt = dict(id=t["id"], emoji=t["emoji"], title=t["title"], theory=md(t["theory"]), tasks=[])
    for k, task in enumerate(t["tasks"]):
        task = dict(task)
        task["id"] = f'{t["id"]}-{k+1}'
        try:
            if task["t"] == "quiz":
                assert 0 <= task["a"] < len(task["opts"])
            elif task["t"] == "out":
                task["a"] = run(task["code"], task["inputs"]).rstrip("\n")
                print(f'--- {task["id"]} OUT:\n{task["a"]}')
            else:
                exp = []
                tests = list(task["tests"])
                subs = [{} for _ in tests]
                for inp in tests:
                    exp.append(run(task["sol"], inp).rstrip("\n"))
                for v in VARY.pop(task["id"], []):
                    code = task["sol"]
                    for k, val in v.items():
                        assert k in code and k in task["start"], f"vary key {k!r} not in sol/start"
                        code = code.replace(k, val)
                    tests.append(tests[0]); subs.append(v)
                    exp.append(run(code, tests[0]).rstrip("\n"))
                task["tests"], task["subs"], task["exp"] = tests, subs, exp
                for rx, msg in task["need"]:
                    assert re.search(rx, task["sol"]), f"sol misses need {rx}"
                for rx, msg in task["ban"]:
                    assert not re.search(rx, task["sol"]), f"sol has ban {rx}"
                if task["start"]:
                    compile(task["start"], "s", "exec")
                print(f'--- {task["id"]} CODE: ' + " | ".join(e.replace("\n", "⏎") for e in exp))
        except Exception as e:
            errors.append(f'{task["id"]}: {e!r}')
        tt["tasks"].append(task)
        total += 1
    data.append(tt)

assert not VARY, f"unused VARY: {list(VARY)}"
print("TOTAL", total, "ERRORS", errors)
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/null", js))
