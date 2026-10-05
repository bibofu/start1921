"""Validate the annotation-only development release and build offline review batches.

This does not run the Agent, assign human labels, or import review decisions.
Run from the repository root with the project's Python environment.
"""

# HTML/CSS/JavaScript templates preserve their own line wrapping.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

from history_agent.config import get_settings
from history_agent.evaluation.pilot import corpus_snapshot, digest, validate_anchors
from history_agent.evaluation.pilot_models import PilotCase, PilotDataset, case_definition
from history_agent.extraction.report import load_page_records
from history_agent.processing.chunks import effective_pages

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = ROOT / "evals/golden/development_annotations_v3.json"
PROTOCOLS = ROOT / "evals/golden/development_protocols_v3.json"
QUEUE = ROOT / "evals/golden/review_queue_v3.json"
OUTPUT = ROOT / "evals/golden/review_v3"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate() -> tuple[dict, dict, dict, dict]:
    annotations, protocols, queue = read(ANNOTATIONS), read(PROTOCOLS), read(QUEUE)
    if protocols["annotation_sha256"] != digest(annotations):
        raise ValueError("protocols refer to a different annotation release")
    if annotations["schema_version"] != 2 or annotations["execution_status"] != "annotation_only":
        raise ValueError(
            "release must remain annotation-only until protocol-aware execution exists"
        )
    cases = [PilotCase.model_validate(case) for case in annotations["cases"]]
    ids = [case.id for case in cases]
    if len(ids) != 20 or len(set(ids)) != 20:
        raise ValueError("development release requires exactly 20 distinct cases")
    design = read(ROOT / "evals/golden/design_v2.json")
    expected = {case["id"]: case for case in design["cases"] if case["split"] == "development"}
    if set(ids) != set(expected):
        raise ValueError("development cases differ from the approved selection")
    for case in cases:
        for field in ("question", "category", "split", "topic_group"):
            if getattr(case, field) != expected[case.id][field]:
                raise ValueError(f"design identity changed: {case.id}/{field}")
        if case.human_review.status != "pending":
            raise ValueError("this prepared release must not invent a human decision")
    for case in design["cases"]:
        if case["split"] == "holdout" and (case["run_allowed"] or case["tuning_allowed"]):
            raise ValueError("holdout isolation was changed")
    old_cases = read(ROOT / "evals/golden/development_v2.json")["cases"]
    current = {case["id"]: case for case in annotations["cases"]}
    expected_old = {case["id"]: deepcopy(case) for case in old_cases}
    adjudications = read(ROOT / "evals/golden/human_adjudications_v3.json")
    for decision in adjudications["decisions"]:
        if decision["scope"] != "partial_annotation_ruling" or decision["case_approved"]:
            raise ValueError("a scoped ruling cannot approve a whole case")
        revised = expected_old[decision["case_id"]]
        if decision["historical_case_sha256"] != digest(revised):
            raise ValueError("scoped ruling historical case hash differs")
        for change in decision["changes"]:
            if change["path"][0] not in {
                "facts",
                "evidence_groups",
                "reference_answer",
                "review_notes",
            }:
                raise ValueError("scoped ruling must not change candidate labels or approval")
            target = revised
            for key in change["path"][:-1]:
                target = target[key]
            if target[change["path"][-1]] != change["before"]:
                raise ValueError("adjudication is not bound to the historical annotation")
            target[change["path"][-1]] = change["after"]
    if any(current[case_id] != case for case_id, case in expected_old.items()):
        raise ValueError("historical case differences require an explicit scoped adjudication")
    by_protocol = {item["case_id"]: item for item in protocols["cases"]}
    if len(protocols["cases"]) != 20 or set(by_protocol) != set(ids):
        raise ValueError("every case requires an explicit evaluation protocol")
    for case in cases:
        protocol = by_protocol[case.id]
        definition = digest(case_definition(case.model_dump(mode="json")))
        if protocol["case_definition_sha256"] != definition:
            raise ValueError(f"stale protocol: {case.id}")
        if protocol["required_fact_ids"] != [fact.id for fact in case.facts if fact.required]:
            raise ValueError(f"fact denominator changed: {case.id}")
        if protocol["required_evidence_group_ids"] != [group.id for group in case.evidence_groups]:
            raise ValueError(f"evidence denominator changed: {case.id}")
        if set(protocol["stages"]) != {
            "query_understanding",
            "routing",
            "retrieval",
            "ranking",
            "context",
            "answer",
            "citation",
            "refusal",
            "cost",
        }:
            raise ValueError(f"incomplete stage rubric: {case.id}")
    paired_id = "dev_constraint_history_isolation"
    paired = by_protocol[paired_id]["input_variants"]
    required_pair = [
        {
            "id": "with_history",
            "question": expected[paired_id]["question"],
            "history": expected[paired_id]["conversation_history"],
        },
        {
            "id": "without_history_control",
            "question": expected[paired_id]["question"],
            "history": [],
        },
    ]
    if paired != required_pair or by_protocol[paired_id]["independent_case_count"] != 1:
        raise ValueError(
            "history isolation must bind both arms to the selected question and history"
        )
    queued = [case_id for batch in queue["batches"] for case_id in batch["case_ids"]]
    if len(queued) != 20 or set(queued) != set(ids):
        raise ValueError("review batches must cover every case exactly once")
    corpus = corpus_snapshot(get_settings())
    dataset = PilotDataset(
        schema_version=1,
        version=annotations["version"],
        description=annotations["description"],
        cases=cases,
    )
    validate_anchors(dataset, get_settings(), corpus)
    # Refusal source-boundary citations are metadata, not positive retrieval gold.
    source_hashes = {doc["document_id"]: doc["sha256"] for doc in corpus["documents"]}
    settings = get_settings()
    pages_cache = {}
    for case in annotations["cases"]:
        basis = case.get("refusal_basis") or {}
        for anchor in basis.get("meta_evidence", []):
            doc = anchor["document_id"]
            if source_hashes[doc] != anchor["file_sha256"]:
                raise ValueError(f"stale refusal source metadata: {case['id']}")
            if doc not in pages_cache:
                ocr = settings.ocr_dir / f"{doc}.jsonl"
                pages_cache[doc] = effective_pages(
                    load_page_records(settings.pages_dir / f"{doc}.jsonl"),
                    load_page_records(ocr) if ocr.exists() else {},
                )
            page = pages_cache[doc][anchor["pdf_page"]]
            if page.file_sha256 != anchor["file_sha256"] or re.sub(
                r"\s+", "", anchor["quote"]
            ) not in re.sub(r"\s+", "", page.normalized_text):
                raise ValueError(f"refusal metadata quote mismatch: {case['id']}")
        project_basis = basis.get("project_basis")
        if project_basis:
            path = (ROOT / project_basis["path"]).resolve()
            if not path.is_relative_to(ROOT):
                raise ValueError("project basis must be inside the repository")
            if hashlib.sha256(path.read_bytes()).hexdigest() != project_basis["file_sha256"]:
                raise ValueError(f"project boundary document changed: {case['id']}")
            for rule in project_basis["rules"]:
                if rule["quote"] not in path.read_text(encoding="utf-8"):
                    raise ValueError(f"project boundary quote mismatch: {case['id']}")
    return annotations, protocols, queue, corpus


def render(annotations: dict, protocols: dict, queue: dict, corpus: dict) -> str:
    esc = html.escape
    cases = {case["id"]: case for case in annotations["cases"]}
    by_protocol = {case["case_id"]: case for case in protocols["cases"]}
    docs = {doc["document_id"]: doc for doc in corpus["documents"]}
    packet = {
        "schema_version": 1,
        "kind": "source_fact_boundary_review_only",
        "annotation_sha256": digest(annotations),
        "protocol_sha256": digest(protocols),
        "queue_sha256": digest(queue),
        "adjudication_sha256": digest(read(ROOT / "evals/golden/human_adjudications_v3.json")),
        "case_definitions": {
            case_id: by_protocol[case_id]["case_definition_sha256"] for case_id in cases
        },
        "batches": queue["batches"],
    }
    packet["packet_sha256"] = digest(packet)
    panels = []
    for batch in queue["batches"]:
        cards = []
        for case_id in batch["case_ids"]:
            case, protocol = cases[case_id], by_protocol[case_id]
            facts = (
                "".join(
                    f"<li><code>{esc(fact['id'])}</code> {esc(fact['claim'])}"
                    f"<small>证据组：{esc(' AND '.join(fact['evidence_group_ids']))}</small></li>"
                    for fact in case["facts"]
                )
                or "<li>拒答题没有正向事实分母；核对下方拒答依据。</li>"
            )
            sources = []
            for group in case["evidence_groups"]:
                anchors = []
                for anchor in group["alternatives"]:
                    doc = docs[anchor["document_id"]]
                    url = "../../../" + quote(doc["relative_path"].replace("\\", "/"))
                    anchors.append(
                        f"<p><a href='{esc(url)}#page={anchor['pdf_page']}' target='_blank'>"
                        f"{esc(doc['title'])} · PDF {anchor['pdf_page']}页</a></p>"
                        f"<blockquote>{esc(anchor['quote'])}</blockquote>"
                        f"<small>PDF SHA-256：{esc(anchor['file_sha256'])}</small>"
                    )
                sources.append(
                    f"<details><summary>{esc(group['id'])} · {esc(group['description'])}</summary>"
                    + "<p>下列锚点互为 OR；事实引用的多个证据组为 AND。</p>"
                    + "<hr>".join(anchors)
                    + "</details>"
                )
            refusal = ""
            if case.get("refusal_basis"):
                basis = case["refusal_basis"]
                refusal = "<details open><summary>拒答依据及边界</summary>"
                refusal += f"<p>{esc(case.get('reference_answer') or '')}</p>"
                for anchor in basis.get("meta_evidence", []):
                    doc = docs[anchor["document_id"]]
                    url = "../../../" + quote(doc["relative_path"].replace("\\", "/"))
                    refusal += (
                        f"<p><a href='{esc(url)}#page={anchor['pdf_page']}' target='_blank'>"
                        f"{esc(doc['title'])} · PDF {anchor['pdf_page']}页</a></p>"
                        f"<blockquote>{esc(anchor['quote'])}</blockquote>"
                    )
                refusal += "<details><summary>完整检索审计和项目依据</summary><pre>"
                refusal += esc(json.dumps(basis, ensure_ascii=False, indent=2))
                refusal += "</pre></details></details>"
            issues = "".join(f"<li>{esc(item)}</li>" for item in protocol["human_review_focus"])
            forbidden = "".join(
                f"<li>{esc(item['claim'])}<small>{esc(item['reason'])}</small></li>"
                for item in case["forbidden_claims"]
            )
            notes = "".join(f"<li>{esc(item)}</li>" for item in case["review_notes"])
            stages = "".join(
                f"<tr><td>{esc(stage)}</td><td>{esc(item['criterion'])}</td>"
                f"<td>{esc(str(item['denominator']))}</td><td>{esc(item['status'])}</td></tr>"
                for stage, item in protocol["stages"].items()
            )
            history = ""
            if len(protocol["input_variants"]) > 1:
                history = (
                    "<details open><summary>配对输入（尚未运行）</summary><pre>"
                    + esc(json.dumps(protocol["input_variants"], ensure_ascii=False, indent=2))
                    + "</pre></details>"
                )
            cards.append(f"""<article data-case="{esc(case_id)}">
<small>{esc(case_id)} · {esc(case["category"])}</small>
<h3>{esc(case["question"])}</h3>
<aside><b>人工需裁定</b><ul>{issues}</ul></aside>
<h4>建议的必要事实（Agent预标，待核对）</h4><ol>{facts}</ol>
{history}{"".join(sources)}{refusal}
<details><summary>参考回答与不应出现的结论</summary>
<p>{esc(case.get("reference_answer") or "")}</p><ul>{forbidden}</ul></details>
<details><summary>标注边界和核验备注</summary><ul>{notes}</ul></details>
<details><summary>各阶段判据、分母与当前支持状态</summary>
<div class="table"><table><thead><tr><th>阶段</th><th>判据</th><th>分母</th><th>状态</th></tr></thead>
<tbody>{stages}</tbody></table></div></details>
<fieldset><legend>本题人工意见</legend>
<label>状态 <select class="decision"><option value="pending">待复核</option>
<option value="approved">批准题干、证据与事实边界</option><option value="rejected">需修改</option></select></label>
<div class="checks">
<label><input type="checkbox" data-confirm="question">已确认题干及回答范围</label>
<label><input type="checkbox" data-confirm="evidence">已核对原页和证据关系</label>
<label><input type="checkbox" data-confirm="facts">已确认必要事实及评分边界</label>
<label><input type="checkbox" data-confirm="refusal">已确认可答／拒答边界</label>
</div><label>修改意见或裁定理由<textarea class="notes" rows="3"></textarea></label>
</fieldset></article>""")
        panels.append(
            f"<section id='{esc(batch['id'])}'><h2>{esc(batch['title'])}</h2>"
            f"<p>{esc(batch['purpose'])}</p>"
            + "".join(cards)
            + f"<button type='button' data-export='{esc(batch['id'])}'>导出这一批意见</button></section>"
        )
    nav = "".join(f"<a href='#{esc(b['id'])}'>{esc(b['title'])}</a>" for b in queue["batches"])
    embedded = json.dumps(packet, ensure_ascii=False).replace("<", "\\u003c")
    return (
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>开发集原文与事实复核 · 20题</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#1e293b;font:16px/1.65 system-ui,'Microsoft YaHei',sans-serif}
main{max-width:1080px;margin:auto;padding:32px 24px 80px}header{border-bottom:2px solid #334155;padding-bottom:24px}
h1{font-size:30px;margin:0 0 10px}h2{font-size:24px;margin:36px 0 8px}h3{font-size:20px;margin:10px 0}h4{margin:24px 0 6px}
nav{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}a{color:#1d4ed8}nav a{background:#e2e8f0;padding:8px 12px;border-radius:6px}
article{background:white;border:1px solid #d8dee7;border-radius:10px;margin:20px 0;padding:24px;overflow-wrap:anywhere}
aside{background:#fff7e6;border-left:4px solid #b7791f;padding:12px 18px}small{display:block;color:#64748b;font-size:13px}
li{margin:8px 0}details{margin:12px 0;padding:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px}
summary{cursor:pointer;font-weight:600}blockquote{margin:12px 0;padding:12px 18px;border-left:3px solid #94a3b8;background:white}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,monospace}.table{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #cbd5e1;padding:9px;text-align:left;vertical-align:top;min-width:95px}
fieldset{border:1px solid #cbd5e1;border-radius:6px;padding:16px;margin-top:22px}label{display:block;margin:8px 0}
input[type=text],select,textarea{font:inherit;padding:8px;border:1px solid #94a3b8;border-radius:4px;max-width:100%}
textarea{display:block;width:100%}.checks{display:grid;grid-template-columns:1fr 1fr;gap:2px 12px}
button{background:#1e40af;color:white;border:0;border-radius:6px;padding:12px 20px;font:inherit;cursor:pointer}
.notice{background:#e8eef7;padding:16px;border-radius:6px}#message{color:#9f1239;white-space:pre-wrap}
@media(max-width:640px){main{padding:20px 12px}.checks{grid-template-columns:1fr}article{padding:16px}}
</style><main><header><h1>开发集原文与事实复核</h1>
<p>20题预标注 · 人工批准尚未完成 · 2026-10-05</p>
<div class="notice">先复核第1—3批原有13题，再复核第4—5批新增7题。
本页只审核题干、原文、必要事实与回答边界，不包含候选相关性或真实模型答案打分。
所有状态默认“待复核”。导出意见不会修改数据集或自动发布 Golden；后续须核验版本哈希、复核者和具体意见。
当前标注包尚未接入采集器，尤其不能把单轮运行当成多轮隔离测试。</div>
<label>复核者姓名或可追溯标识 <input id="reviewer" type="text" autocomplete="name"></label>
<p>点击原页链接可打开本地PDF；请核对物理页码。页面不自动保存，离开前请导出意见。</p>
<div id="message" role="alert"></div></header><nav>"""
        + nav
        + "</nav>"
        + "".join(panels)
        + """
<script id="packet" type="application/json">"""
        + embedded
        + """</script>
<script>
'use strict';
const packet=JSON.parse(document.getElementById('packet').textContent);
function decisions(batchId){
 const batch=packet.batches.find(x=>x.id===batchId);
 if(!batch)throw Error('未知复核批次');
 const reviewer=document.getElementById('reviewer').value.trim();
 if(!reviewer)throw Error('请填写可追溯的复核者标识。');
 const cases=batch.case_ids.map(id=>{
  const card=document.querySelector('[data-case="'+id+'"]');
  const status=card.querySelector('.decision').value;
  const confirmations=Object.fromEntries(Array.from(card.querySelectorAll('[data-confirm]')).map(e=>[e.dataset.confirm,e.checked]));
  const notes=card.querySelector('.notes').value.trim();
  if(status==='approved'&&!Object.values(confirmations).every(Boolean))throw Error(id+'：批准需要四项明确确认。');
  if(status==='rejected'&&!notes)throw Error(id+'：请记录需修改的具体原因。');
  return {case_id:id,case_definition_sha256:packet.case_definitions[id],status,confirmations,notes};
 });
 return {schema_version:1,kind:packet.kind,packet_sha256:packet.packet_sha256,
  annotation_sha256:packet.annotation_sha256,protocol_sha256:packet.protocol_sha256,
  queue_sha256:packet.queue_sha256,adjudication_sha256:packet.adjudication_sha256,
  batch_id:batchId,reviewer,reviewed_at:new Date().toISOString(),cases};
}
document.querySelectorAll('[data-export]').forEach(button=>button.addEventListener('click',()=>{
 try{const value=decisions(button.dataset.export);
  const blob=new Blob([JSON.stringify(value,null,2)+'\\n'],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='development_v3_'+value.batch_id+'_review.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  document.getElementById('message').textContent='已导出本批意见；尚未导入或批准任何数据。';
 }catch(error){document.getElementById('message').textContent=error.message;document.getElementById('message').scrollIntoView();}
}));
</script></main></html>"""
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="validate without writing review files"
    )
    args = parser.parse_args()
    annotations, protocols, queue, corpus = validate()
    text = render(annotations, protocols, queue, corpus)
    if args.check:
        if (OUTPUT / "index.html").read_text(encoding="utf-8") != text:
            raise ValueError("review HTML is stale; rebuild after annotation changes")
        print(
            "20 cases, protocols, batches, historical cases with scoped rulings, PDF hashes and anchors valid"
        )
        return
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "index.html").write_text(text, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "status": "prepared_not_human_approved",
        "annotation_sha256": digest(annotations),
        "protocol_sha256": digest(protocols),
        "queue_sha256": digest(queue),
        "adjudication_sha256": digest(read(ROOT / "evals/golden/human_adjudications_v3.json")),
        "html_sha256": hashlib.sha256((OUTPUT / "index.html").read_bytes()).hexdigest(),
        "reviewed_cases": 0,
        "candidate_review_included": False,
        "answer_review_included": False,
    }
    write(OUTPUT / "manifest.json", manifest)
    print(f"Prepared {len(annotations['cases'])} cases in {len(queue['batches'])} review batches")


if __name__ == "__main__":
    main()
