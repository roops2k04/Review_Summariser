import json, re
from openai import OpenAI
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=20) if LLM_API_KEY and LLM_BASE_URL else None

POS = ["good","great","excellent","amazing","wonderful","best","fantastic","friendly","helpful","clean","spacious","fresh","tasty","cozy","nice","beautiful","comfortable","quiet","peaceful","affordable","yummy","delicious","top notch","impressive","worth"]
NEG = ["bad","worst","terrible","awful","dirty","noisy","expensive","rude","slow","cold","small","uncomfortable","broken","late","issue","problem","deducted","helpless","unclean","overpriced","disappointing","bad food","poor service","flies"]

def _cnt(text, markers): return sum(1 for m in markers if m in (text or "").lower())
def _is_neg(t): return _cnt(t, NEG) > 0
def _is_pos(t): return _cnt(t, POS) > 0
def _generic(p): return any(m in (p or "").lower() for m in ["multiple reviews","some reviews report","overall feedback","issues related to","generally positive","no strong recurring","guests frequently mention","positive feedback mentioned","no major complaints"])
def _normalize(text):
    c = re.sub(r"^[\-•\d\.\)\s]+", "", " ".join((text or "").split()).strip()).strip()
    return c
def _incomplete(text):
    w = (text or "").strip().split()
    if not w: return True
    if len(w[-1]) == 1 and w[-1].isalpha(): return True
    if w[-1].lower().strip(",;:") in {"and","or","but","with","without","for","to","of","by","in","on","at","from"}: return True
    return False
def _clean_json(text):
    text = (text or "").replace("```json","").replace("```","").strip()
    s, e = text.find("{"), text.rfind("}")
    return text[s:e+1] if s != -1 and e >= s else text
def _tag(kw):
    k = kw.lower()
    if any(w in k for w in ["food","meal","breakfast","dinner","taste","tasty","soup","coffee"]): return "Food"
    if any(w in k for w in ["service","staff","helpful","friendly","rude","slow"]): return "Service"
    if any(w in k for w in ["room","bed","spacious","clean","dirty","small"]): return "Rooms"
    if any(w in k for w in ["price","expensive","cost","affordable","worth","deducted"]): return "Value"
    if any(w in k for w in ["location","area","near","access"]): return "Location"
    if any(w in k for w in ["parking","facilities","wifi","air"]): return "Facilities"
    return "Other"
def _ctx(text, phrase):
    for s in re.split(r"[.!?]", text):
        if phrase in s.lower():
            c = s.strip()
            for sep in [" but "," however "," though "," although "," while "]:
                if sep in c.lower():
                    for p in re.split(sep, c, flags=re.IGNORECASE):
                        if phrase in p.lower(): return p.strip(" ,;:-")
            return c
    return phrase.capitalize()
def _extract(reviews):
    ps, ns = {}, {}
    for review in reviews:
        t = " ".join((review or "").split()).strip()
        if not t: continue
        l = t.lower()
        for ph in POS:
            if ph in l:
                kw = _ctx(t, ph); k = kw.lower()
                if k not in ps: ps[k] = {"tag": _tag(kw), "point": kw, "count": 0}
                ps[k]["count"] += 1; break
        for ph in NEG:
            if ph in l:
                kw = _ctx(t, ph); k = kw.lower()
                if k not in ns: ns[k] = {"tag": _tag(kw), "point": kw, "count": 0}
                ns[k]["count"] += 1; break
    pros = [{"tag": v["tag"],"point": v["point"]} for v in sorted(ps.values(), key=lambda x: -x["count"])]
    cons = [{"tag": v["tag"],"point": v["point"]} for v in sorted(ns.values(), key=lambda x: -x["count"])]
    return {"pros": (pros or [{"tag":"General","point":"Positive feedback mentioned"}])[:5],
            "cons": (cons or [{"tag":"General","point":"No major complaints"}])[:5]}
def _polar_sentences(reviews, want, limit=5):
    picked, seen = [], set()
    for review in reviews or []:
        for s in re.split(r"[.!?]", " ".join((review or "").split()).strip()):
            s = s.strip(" \t\n\r\f\v-•")
            if not s or s.lower() in seen: continue
            if want == "neg":
                if not _is_neg(s): continue
                if _is_pos(s) and _cnt(s, ["however","but"]) == 0: continue
            else:
                if not _is_pos(s) or _is_neg(s): continue
            seen.add(s.lower()); picked.append({"tag":"Other","point":s})
            if len(picked) >= limit: return picked
    return picked
def _postprocess(result):
    if not isinstance(result, dict): return result
    for name, data in result.items():
        def _norm_list(items):
            out, seen = [], set()
            for item in (items or []):
                p = _normalize((item or {}).get("point",""))
                if _incomplete(p) or not p or p.lower() in seen: continue
                seen.add(p.lower()); out.append({"tag":(item or {}).get("tag","Other"),"point":p})
            return out
        pros = _norm_list(data.get("pros",[]) if isinstance(data,dict) else [])
        cons = _norm_list(data.get("cons",[]) if isinstance(data,dict) else [])
        pk = {p["point"].lower() for p in pros}
        cons = [c for c in cons if c["point"].lower() not in pk]
        result[name] = {"pros": (pros or [{"tag":"Other","point":"No standout positives highlighted"}])[:5],
                        "cons": (cons or [{"tag":"Other","point":"No standout negatives highlighted"}])[:5]}
    return result
def _inject(result, source_data):
    if not isinstance(result, dict): return result
    for name, data in result.items():
        if name not in source_data: continue
        pros, cons = data.get("pros",[]), data.get("cons",[])
        ext = _extract(source_data[name])
        def _filt(items, want):
            out, seen = [], set()
            for item in (items or []):
                p = _normalize((item or {}).get("point",""))
                if not p or p.lower() in seen: continue
                if want == "neg":
                    if not _is_neg(p): continue
                else:
                    if _is_neg(p) or not _is_pos(p): continue
                seen.add(p.lower()); out.append({"tag":(item or {}).get("tag","Other"),"point":p})
            return out
        def _backfill(target, cands, want):
            ex = {t["point"].lower() for t in target}
            for item in (cands or []):
                p = _normalize((item or {}).get("point",""))
                if not p or p.lower() in ex: continue
                if want == "neg":
                    if not _is_neg(p): continue
                else:
                    if not _is_pos(p) or _is_neg(p): continue
                target.append({"tag":(item or {}).get("tag","Other"),"point":p}); ex.add(p.lower())
                if len(target) >= 5: break
        fp = _filt(pros, "pos"); fc = _filt(cons, "neg")
        if all(_generic((p or {}).get("point","")) for p in pros) or len(fp) < 3:
            data["pros"] = ext.get("pros",[])
        else:
            _backfill(fp, ext.get("pros",[]), "pos"); data["pros"] = fp[:5]
        if all(_generic((c or {}).get("point","")) for c in cons) or len(fc) < 3:
            data["cons"] = ext.get("cons",[])
        else:
            _backfill(fc, ext.get("cons",[]), "neg"); data["cons"] = fc[:5]
    return result
def _enforce(result, source_data=None):
    if not isinstance(result, dict): return result
    for name, data in result.items():
        if not isinstance(data, dict): continue
        def _norm(items):
            out, seen = [], set()
            for item in (items or []):
                p = _normalize((item or {}).get("point",""))
                if not p or p.lower() in seen: continue
                seen.add(p.lower()); out.append({"tag":(item or {}).get("tag","Other"),"point":p})
            return out
        pros = [p for p in _norm(data.get("pros",[])) if _is_pos(p["point"]) and not _is_neg(p["point"]) and not _generic(p["point"])]
        cons = [c for c in _norm(data.get("cons",[])) if _is_neg(c["point"]) and not _generic(c["point"])]
        reviews = (source_data or {}).get(name, [])
        ext = _extract(reviews)
        def _backfill(target, cands, want):
            ex = {t["point"].lower() for t in target}
            for item in (cands or []):
                p = _normalize((item or {}).get("point",""))
                if not p or p.lower() in ex: continue
                if want == "neg":
                    if not _is_neg(p): continue
                else:
                    if not _is_pos(p) or _is_neg(p): continue
                target.append({"tag":(item or {}).get("tag","Other"),"point":p}); ex.add(p.lower())
                if len(target) >= 5: break
        _backfill(pros, ext.get("pros",[]), "pos"); _backfill(cons, ext.get("cons",[]), "neg")
        if len(pros) < 5: _backfill(pros, _polar_sentences(reviews, "pos", 5), "pos")
        if len(cons) < 5: _backfill(cons, _polar_sentences(reviews, "neg", 5), "neg")
        result[name] = {"pros": (pros or [{"tag":"Other","point":"No standout positives highlighted"}])[:5],
                        "cons": (cons or [{"tag":"Other","point":"No major complaints mentioned in reviews"}])[:5]}
    return result
def _fallback(data):
    return _postprocess({name: _extract(reviews) for name, reviews in data.items()})

def analyze_reviews(data):
    prompt = f"""You are a PROFESSIONAL REVIEW ANALYST.
Task: Analyze ALL reviews. Find TOP 5 pros and TOP 5 cons.
Rules: ONLY extract actual phrases from reviews | Prioritize repeated themes | 2-10 words per point | No overlap | STRICT JSON only
Output format - EXACTLY 5 pros and 5 cons:
{{"Business Name": {{"pros": [{{"tag": "Food", "point": "Fresh and delicious meals"}},{{"tag": "Service", "point": "Friendly and attentive staff"}}],"cons": [{{"tag": "Price", "point": "Expensive prices"}},{{"tag": "Location", "point": "Hard to find parking"}}]}}}}
Reviews ({len(list(data.values())[0])} total):
{json.dumps(data, ensure_ascii=False)}"""
    if client is None: return _enforce(_fallback(data), data)
    try:
        r = client.chat.completions.create(model=LLM_MODEL, messages=[{"role":"user","content":prompt}], temperature=0)
        return _enforce(_inject(_postprocess(json.loads(_clean_json(r.choices[0].message.content))), data), data)
    except Exception:
        return _enforce(_fallback(data), data)

def ask_llm(query, context):
    prompt = f"""You are a STRICT assistant.
Rules: ONLY use the given context | DO NOT add external knowledge | DO NOT hallucinate | If answer not present → say "Not found in reviews"
Context:\n{context}\nQuestion:\n{query}"""
    def _fb(reason=None):
        snippets = [l.strip() for l in context.splitlines() if l.strip()]
        if not snippets: return "Not found in reviews"
        h = f"The LLM is unavailable right now ({reason})" if reason else "The LLM is unavailable right now"
        return h + ", so here are the most relevant review excerpts:\n" + "\n".join(f"- {s}" for s in snippets[:3])
    if client is None:
        return _fb("missing LLM_API_KEY" if not LLM_API_KEY else "missing LLM_BASE_URL" if not LLM_BASE_URL else "LLM unavailable")
    try:
        r = client.chat.completions.create(model=LLM_MODEL, messages=[{"role":"user","content":prompt}], temperature=0)
        return r.choices[0].message.content or "Not found in reviews"
    except Exception as exc:
        t = str(exc).lower()
        reason = "invalid LLM_API_KEY" if "invalid api key" in t or "incorrect api key" in t else f"invalid LLM_MODEL ({LLM_MODEL})" if "model not found" in t else "rate limited" if "rate limit" in t or "429" in t else "timeout" if "timeout" in t else type(exc).__name__
        return _fb(reason)