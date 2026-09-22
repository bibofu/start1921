"""Build a blinded offline review packet and import explicitly audited decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from history_agent.config import get_settings
from history_agent.evaluation.pilot import DEFAULT_DATASET, digest, read_json
from history_agent.evaluation.pilot_metrics import evidence_unit
from history_agent.evaluation.pilot_models import PilotDataset, case_definition

PACKET_VERSION = "offline-pilot-review-v1"
DEFAULT_SEED = 20260922
CONFIRMATIONS = {"question", "evidence", "facts", "refusal"}


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class UnitDecision(ReviewModel):
    unit_id: str
    identity_sha256: str
    relevance: Literal[0, 1, 2] | None
    reason: str = ""
    supported_groups: list[str] = Field(default_factory=list)

    @field_validator("relevance", mode="before")
    @classmethod
    def integer_grade(cls, value: Any) -> Any:
        if value is not None and type(value) is not int:
            raise ValueError("relevance must be null or an integer grade")
        return value

    @model_validator(mode="after")
    def support_is_explicit(self) -> UnitDecision:
        if self.relevance is not None and len(self.reason.strip()) < 2:
            raise ValueError(
                "scored candidates require a specific review reason (at least 2 characters)"
            )
        if len(self.supported_groups) != len(set(self.supported_groups)):
            raise ValueError("duplicate supported evidence groups")
        if self.relevance != 2 and self.supported_groups:
            raise ValueError("only directly supporting evidence can confirm required groups")
        return self


class CaseDecision(ReviewModel):
    case_id: str
    case_definition_sha256: str
    status: Literal["pending", "approved", "rejected"]
    confirmations: dict[str, bool]
    notes: str = ""
    candidates: list[UnitDecision]

    @model_validator(mode="after")
    def explicit_approval(self) -> CaseDecision:
        if set(self.confirmations) != CONFIRMATIONS:
            raise ValueError("review must specify question/evidence/facts/refusal confirmations")
        if self.status == "approved" and not all(self.confirmations.values()):
            raise ValueError("approval requires explicit confirmation of every review boundary")
        ids = [item.unit_id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate candidate decisions")
        return self


class ReviewDecisions(ReviewModel):
    schema_version: Literal[1]
    packet_sha256: str
    reviewer: str
    reviewed_at: str
    cases: list[CaseDecision]

    @field_validator("reviewer", "reviewed_at")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reviewer and review timestamp are required")
        return value.strip()

    @field_validator("reviewed_at")
    @classmethod
    def timestamp_with_timezone(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("review timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def unique_cases(self) -> ReviewDecisions:
        ids = [item.case_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate case decisions")
        return self


def _write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _document_views(corpus: dict[str, Any], project_root: Path) -> dict[str, dict[str, Any]]:
    documents = corpus["documents"]
    if digest(documents) != corpus["sha256"]:
        raise ValueError("capture corpus digest differs from its documents")
    result = {}
    for item in documents:
        doc = item["document_id"]
        if doc in result:
            raise ValueError("duplicate corpus document")
        path = (project_root / item["relative_path"]).resolve()
        if not path.is_relative_to(project_root):
            raise ValueError("PDF path is outside the project root")
        result[doc] = {
            "title": item["title"],
            "file_sha256": item["sha256"],
            "pdf_url": path.as_uri(),
            "path": path,
        }
    return result


def _source_view(
    anchor: dict[str, Any],
    documents: dict[str, dict[str, Any]],
    *,
    page_key: str,
) -> dict[str, Any]:
    document = documents.get(anchor["document_id"])
    if document is None or anchor["file_sha256"] != document["file_sha256"]:
        raise ValueError("evidence source is absent or its PDF hash differs")
    return {
        "title": document["title"],
        "pdf_url": f"{document['pdf_url']}#page={anchor[page_key]}",
    }


def _make_packet(
    dataset: PilotDataset,
    capture: dict[str, Any],
    *,
    project_root: Path,
    seed: int,
) -> dict[str, Any]:
    normalized = dataset.model_dump(mode="json")
    if capture["dataset_sha256"] != digest(normalized):
        raise ValueError("capture does not belong to the supplied original dataset")
    captured = {item["case_id"]: item for item in capture["cases"]}
    if len(captured) != len(capture["cases"]):
        raise ValueError("duplicate captured cases")
    if set(captured) != {case.id for case in dataset.cases}:
        raise ValueError("capture and dataset case IDs differ")
    project_root = project_root.resolve()
    documents = _document_views(capture["corpus"], project_root)
    file_hashes = {doc: item["file_sha256"] for doc, item in documents.items()}
    used_documents: set[str] = set()
    cases = []
    for model in dataset.cases:
        case = model.model_dump(mode="json")
        raw = captured[model.id]
        definition_hash = digest(case_definition(case))
        if raw["case_definition_sha256"] != definition_hash or raw["question"] != model.question:
            raise ValueError(f"question or evidence definition changed: {model.id}")
        actual_pool = {}
        for unit in raw["candidate_pool"]:
            derived = evidence_unit(unit, file_hashes)
            if any(unit.get(key) != value for key, value in derived.items()):
                raise ValueError(f"candidate identity or text was changed: {model.id}")
            if derived["unit_id"] in actual_pool:
                raise ValueError("duplicate candidate unit in capture")
            actual_pool[derived["unit_id"]] = derived
        expected_pool: dict[str, dict[str, Any]] = {}
        for stage in [
            *raw["stages"],
            *raw.get("production_stages", []),
            *raw.get("generation_contexts", []),
        ]:
            for hit in stage["hits"]:
                derived = evidence_unit(hit, file_hashes)
                expected_pool.setdefault(derived["unit_id"], derived)
        if actual_pool != expected_pool:
            raise ValueError("captured candidate pool differs from the executed stages")
        units = []
        for unit in actual_pool.values():
            used_documents.add(unit["document_id"])
            units.append(
                {
                    **unit,
                    **_source_view(unit, documents, page_key="pdf_page_start"),
                    "identity_sha256": digest(unit["identity"]),
                }
            )
        # Sort before shuffling so source insertion order/ranking cannot become a cue.
        units.sort(key=lambda item: item["unit_id"])
        random.Random(f"{seed}:{model.id}").shuffle(units)
        groups = []
        for group in case["evidence_groups"]:
            alternatives = []
            for anchor in group["alternatives"]:
                used_documents.add(anchor["document_id"])
                clean = {key: value for key, value in anchor.items() if key != "agent_verification"}
                alternatives.append(
                    {**clean, **_source_view(anchor, documents, page_key="pdf_page")}
                )
            groups.append(
                {
                    "id": group["id"],
                    "description": group["description"],
                    "alternatives": alternatives,
                }
            )
        cases.append(
            {
                "case_id": model.id,
                "question": model.question,
                "case_definition_sha256": definition_hash,
                "category": model.category,
                "answerability": model.answerability,
                "evidence_groups": groups,
                "facts": case["facts"],
                "forbidden_claims": case["forbidden_claims"],
                "refusal_basis": case["refusal_basis"],
                "not_applicable_metrics": case["not_applicable_metrics"],
                "candidates": units,
            }
        )
    for doc in used_documents:
        item = documents[doc]
        with item["path"].open("rb") as stream:
            actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual_hash != item["file_sha256"]:
            raise ValueError(f"local PDF differs from the captured source: {doc}")
    payload = {
        "schema_version": 1,
        "packet_version": PACKET_VERSION,
        "project_root": str(project_root),
        "seed": seed,
        "dataset_sha256": digest(normalized),
        "capture_sha256": digest(capture),
        "corpus_sha256": capture["corpus"]["sha256"],
        "evidence_group_semantics": dataset.evidence_group_semantics,
        "cases": cases,
    }
    return {**payload, "packet_sha256": digest(payload)}


def build(
    dataset_path: Path,
    capture_path: Path,
    output_dir: Path,
    *,
    project_root: Path | None = None,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Write a new immutable packet; refuse to overwrite an existing review bundle."""
    packet_path = output_dir / "packet.json"
    html_path = output_dir / "review.html"
    if packet_path.exists() or html_path.exists():
        raise FileExistsError("review packet already exists; choose a new output directory")
    dataset = PilotDataset.model_validate(read_json(dataset_path))
    packet = _make_packet(
        dataset,
        read_json(capture_path),
        project_root=project_root or get_settings().project_root,
        seed=seed,
    )
    html = _render_html(packet)
    _write_new_json(packet_path, packet)
    with html_path.open("x", encoding="utf8") as stream:
        stream.write(html)
    return packet


def import_decisions(
    dataset_path: Path,
    capture_path: Path,
    packet_path: Path,
    decisions_path: Path,
    output: Path,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Bind human edits to original immutable inputs; write a separate reviewed dataset."""
    protected = {
        path.resolve() for path in [dataset_path, capture_path, packet_path, decisions_path]
    }
    audit_path = output.with_suffix(".audit.json")
    if output.resolve() in protected or audit_path.resolve() in protected:
        raise ValueError("review output cannot overwrite an original input")
    if output.exists() or audit_path.exists():
        raise FileExistsError("review output already exists; choose a new file")
    dataset = PilotDataset.model_validate(read_json(dataset_path))
    capture = read_json(capture_path)
    packet = read_json(packet_path)
    expected = _make_packet(
        dataset,
        capture,
        project_root=project_root or get_settings().project_root,
        seed=packet["seed"],
    )
    if packet != expected:
        raise ValueError("immutable packet differs from the original dataset/capture")
    decisions = ReviewDecisions.model_validate(read_json(decisions_path))
    if decisions.packet_sha256 != expected["packet_sha256"]:
        raise ValueError("decisions belong to a different immutable packet")
    selected = {case.case_id: case for case in decisions.cases}
    if set(selected) != {case.id for case in dataset.cases}:
        raise ValueError("decisions must include every packet case, pending cases included")
    packet_cases = {case["case_id"]: case for case in packet["cases"]}
    result = deepcopy(dataset.model_dump(mode="json"))
    for case in result["cases"]:
        decision = selected[case["id"]]
        original = packet_cases[case["id"]]
        if decision.case_definition_sha256 != original["case_definition_sha256"]:
            raise ValueError("decision question/evidence definition digest differs")
        units = {unit["unit_id"]: unit for unit in original["candidates"]}
        if {unit.unit_id for unit in decision.candidates} != set(units):
            raise ValueError("candidate decisions are missing units or contain unknown units")
        group_ids = {group["id"] for group in case["evidence_groups"]}
        # Null explicitly means unknown: never let an old agent label masquerade
        # as the reviewer's decision. Uncaptured labels retain their provenance.
        retained = [item for item in case["judgments"] if item["unit_id"] not in units]
        for judgment in decision.candidates:
            if judgment.identity_sha256 != units[judgment.unit_id]["identity_sha256"]:
                raise ValueError("candidate decision identity differs from immutable packet")
            if not set(judgment.supported_groups) <= group_ids:
                raise ValueError("decision refers to an unknown evidence group")
            if judgment.relevance is None:
                continue
            retained.append(
                {
                    "unit_id": judgment.unit_id,
                    "relevance": judgment.relevance,
                    "reason": judgment.reason.strip(),
                    "reviewer": decisions.reviewer,
                    "reviewed_at": decisions.reviewed_at,
                    "basis": "human_review",
                    "supported_groups": judgment.supported_groups,
                }
            )
        case["judgments"] = retained
        case["human_review"] = {
            "status": decision.status,
            "reviewed_by": decisions.reviewer,
            "reviewed_at": decisions.reviewed_at,
            "notes": decision.notes,
            "confirmations": decision.confirmations,
        }
    result["annotation_status"] = "human_review_imported_with_explicit_case_statuses"
    reviewed = PilotDataset.model_validate(result).model_dump(mode="json")
    audit = {
        "packet_sha256": packet["packet_sha256"],
        "original_dataset_sha256": packet["dataset_sha256"],
        "capture_sha256": packet["capture_sha256"],
        "reviewed_dataset_sha256": digest(reviewed),
        "decisions_sha256": digest(decisions.model_dump(mode="json")),
        "decisions": decisions.model_dump(mode="json"),
    }
    _write_new_json(output, reviewed)
    _write_new_json(audit_path, audit)
    return reviewed


def _render_html(packet: dict[str, Any]) -> str:
    # Escaping '<' prevents source text from terminating the application/json tag.
    embedded = json.dumps(packet, ensure_ascii=False).replace("<", "\\u003c")
    return HTML_TEMPLATE.replace("__PACKET_JSON__", embedded)


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src data:; base-uri 'none'; form-action 'none'">
<title>评测试点 · 人工复核</title>
<style>
body{margin:0;background:#f5f6f8;color:#202a35;font:16px/1.65 system-ui,sans-serif}
main{max-width:1080px;margin:auto;padding:28px}h1{font-size:28px;margin:0 0 12px}
h2{font-size:22px}h3{font-size:18px;margin:14px 0 8px}p{margin:8px 0}
.notice{border-left:4px solid #a66a00;background:#fff6df;padding:16px}.toolbar{position:sticky;top:0;background:#f5f6f8;z-index:1;padding:12px 0;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
section{background:white;border:1px solid #d6dce4;border-radius:10px;padding:22px;margin:22px 0;scroll-margin-top:180px}
.case-navigation{flex-basis:100%;display:flex;gap:10px;align-items:center;margin:0}.case-navigation select{min-width:0;flex:1;max-width:760px}
article,.group{border:1px solid #dce1e7;border-radius:7px;padding:16px;margin:14px 0}
blockquote{white-space:pre-wrap;margin:10px 0;padding:12px;background:#f4f6fa;overflow-wrap:anywhere}
input[type=text],textarea,select{font:inherit;border:1px solid #9aa6b5;border-radius:5px;padding:8px;box-sizing:border-box}
textarea{display:block;width:100%;min-height:62px;margin-top:8px}label{display:inline-block;margin:4px 16px 4px 0}
button,.file-button{font:inherit;padding:8px 14px;background:#154e83;color:white;border:0;border-radius:6px;cursor:pointer}
a{color:#125794}.muted,small{color:#526171}.controls{display:flex;gap:10px;flex-wrap:wrap}
.checks label{display:block}summary{cursor:pointer;font-weight:600}.error{color:#a02020}
@media(max-width:600px){main{padding:14px}section{padding:14px}.toolbar{position:static}}
</style></head><body><main>
<h1>评测试点 · 人工复核</h1>
<div class="notice"><strong>这是待审草案，不是已批准的 Golden。</strong>
<p>必要证据组之间为 AND：需要逐组覆盖；同一组内替代原文为 OR：命中任一有效来源即可。一个事实关联多个证据组时仍为 AND。</p>
<p>候选顺序已打乱，隐藏了检索分支、排名和 Agent 建议标签。请按问题边界独立判断：0 不相关，1 相关背景，2 直接支持。未判不会算作不相关。</p>
<p>可以只审一部分后保存。导出文件不会自动批准题目；批准必须在每题明确选择，并确认四项口径。可保留未判候选，相关指标可能仍不可评。</p>
<p>已评分候选导入时必须填写具体理由（至少 2 字）。可先导出未完成的草稿，补充理由后再导入；没有把握的候选请保持未判。</p>
<p>所有操作在本地完成。PDF 链接使用物理页码；若浏览器不允许打开，请复制链接到本机 PDF 阅读器。</p></div>
<div class="toolbar"><label class="case-navigation">选择题目 <select id="case-nav" aria-label="切换复核题目"></select></label>
<span id="case-progress" class="muted" aria-live="polite"></span><label>复核者（必填） <input id="reviewer" type="text" autocomplete="name"></label>
<button id="save" type="button">导出复核决定 JSON</button><label class="file-button">载入上次决定<input id="resume" type="file" accept=".json" hidden></label></div>
<p id="feedback" aria-live="polite"></p><div id="cases"></div>
<script id="packet" type="application/json">__PACKET_JSON__</script>
<script>
'use strict';
const packet=JSON.parse(document.getElementById('packet').textContent);
const states=[];
const navigation=document.getElementById('case-nav');
const labels={question:'已确认问题及来源、时间、人物等边界',evidence:'已逐组确认全部必要证据及替代原文（无证据目标时已核实不适用）',facts:'已逐项确认全部必要事实及禁止推断（无事实目标时已核实不适用）',refusal:'已确认可答性、部分可答和拒答口径'};
function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function check(text){const label=el('label');const input=el('input');input.type='checkbox';label.append(input,document.createTextNode(' '+text));return {label,input};}
function quote(parent,item,pageKey){parent.append(el('p',item.title+' · PDF 物理页 '+item[pageKey],'muted'));const a=el('a','打开 PDF 对应页');a.href=item.pdf_url;a.target='_blank';a.rel='noopener';parent.append(a,el('blockquote',item.quote||item.text));}
packet.cases.forEach((item,ci)=>{
 const section=el('section');section.id='review-case-'+ci;section.hidden=ci!==0;section.append(el('h2',(ci+1)+'. '+item.question));
 const navOption=el('option',(ci+1)+'. '+item.question);navOption.value=String(ci);navigation.append(navOption);
 section.append(el('p','待审草案的可答性：'+(item.answerability==='answerable'?'可回答':'不可回答')+' · '+item.case_id,'muted'));
 const draft=el('details');draft.open=true;draft.append(el('summary','核对必要事实、证据与回答边界'));
 item.facts.forEach(f=>draft.append(el('p',f.id+'：'+f.claim+'（关联证据组 AND：'+f.evidence_group_ids.join('、')+'）')));
 item.evidence_groups.forEach(group=>{const box=el('div',undefined,'group');box.append(el('h3',group.id+'：'+group.description),el('small','本组多个替代来源为 OR；请核对每条原文与页码。'));group.alternatives.forEach(a=>quote(box,a,'pdf_page'));draft.append(box);});
 if(!item.facts.length&&!item.evidence_groups.length)draft.append(el('p','本题没有正向事实和证据组目标；请核实拒答边界。'));
 item.forbidden_claims.forEach(f=>draft.append(el('p','禁止推断：'+f.claim+'；依据：'+f.reason)));
 if(item.refusal_basis)draft.append(el('h3','拒答依据（待审）'),el('blockquote',JSON.stringify(item.refusal_basis,null,2)));
 if(Object.keys(item.not_applicable_metrics).length)draft.append(el('p','不适用指标：'+JSON.stringify(item.not_applicable_metrics)));
 section.append(draft,el('h3','候选相关性 · 顺序已随机化'));
 const units=[];
 item.candidates.forEach((unit,ui)=>{
  const card=el('article');card.append(el('h3','候选 '+(ui+1)));quote(card,unit,'pdf_page_start');
  if(unit.pdf_page_end!==unit.pdf_page_start)card.append(el('small','原文页码范围：'+unit.pdf_page_start+'—'+unit.pdf_page_end));
  const radios=[];const controls=el('div',undefined,'controls');
  [['0','不相关'],['1','相关背景'],['2','直接支持'],['unknown','未判']].forEach(([value,text])=>{const label=el('label');const radio=el('input');radio.type='radio';radio.name='c'+ci+'u'+ui;radio.value=value;label.append(radio,document.createTextNode(' '+text));controls.append(label);radios.push(radio);});
  card.append(controls);const support=el('div',undefined,'checks');const groupInputs={};
  item.evidence_groups.forEach(group=>{const c=check('明确支持证据组 '+group.id);c.input.disabled=true;groupInputs[group.id]=c.input;support.append(c.label);});
  const sync=()=>{const direct=radios.some(r=>r.checked&&r.value==='2');Object.values(groupInputs).forEach(x=>{x.disabled=!direct;if(!direct)x.checked=false;});};radios.forEach(r=>r.addEventListener('change',sync));
  const reason=el('textarea');reason.placeholder='具体判断理由（已评分候选导入时必填，至少 2 字；可先保存草稿）';reason.setAttribute('aria-label','候选 '+(ui+1)+' 判断理由');card.append(support,reason);section.append(card);units.push({unit,radios,groupInputs,reason,sync});
 });
 const approvals=el('div',undefined,'checks');approvals.append(el('h3','题目定义复核（独立于候选是否全部评完）'));const confirms={};Object.entries(labels).forEach(([key,text])=>{const c=check(text);confirms[key]=c.input;approvals.append(c.label);});
 const status=el('select');status.setAttribute('aria-label','题目审批状态');[['pending','待审 / 保存部分进度'],['approved','明确批准此题定义'],['rejected','退回修改（不批准）']].forEach(([value,text])=>{const option=el('option',text);option.value=value;status.append(option);});
 const notes=el('textarea');notes.placeholder='题目复核意见、疑点或退回原因';notes.setAttribute('aria-label','题目复核意见');approvals.append(status,notes);section.append(approvals);document.getElementById('cases').append(section);states.push({item,units,confirms,status,notes,section});
});
function showCase(index,scroll=false){if(!Number.isInteger(index)||index<0||index>=states.length)return;states.forEach((s,i)=>s.section.hidden=i!==index);navigation.value=String(index);document.getElementById('case-progress').textContent='第 '+(index+1)+' / '+states.length+' 题 · '+states[index].units.length+' 个候选 · 切换保留已填进度';if(scroll)states[index].section.scrollIntoView({block:'start'});}
navigation.addEventListener('change',()=>showCase(Number(navigation.value),true));
showCase(0);
function decisionData(){const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer)throw Error('请填写复核者。');const cases=states.map(s=>{const confirmations=Object.fromEntries(Object.entries(s.confirms).map(([k,v])=>[k,v.checked]));if(s.status.value==='approved'&&!Object.values(confirmations).every(Boolean))throw Error('批准前请确认该题全部四项口径：'+s.item.question);return {case_id:s.item.case_id,case_definition_sha256:s.item.case_definition_sha256,status:s.status.value,confirmations,notes:s.notes.value,candidates:s.units.map(u=>{const selected=u.radios.find(r=>r.checked);return {unit_id:u.unit.unit_id,identity_sha256:u.unit.identity_sha256,relevance:!selected||selected.value==='unknown'?null:Number(selected.value),reason:u.reason.value,supported_groups:Object.entries(u.groupInputs).filter(([,input])=>input.checked).map(([key])=>key)};})};});return {schema_version:1,packet_sha256:packet.packet_sha256,reviewer,reviewed_at:new Date().toISOString(),cases};}
document.getElementById('save').addEventListener('click',()=>{try{const decisions=decisionData();const blob=new Blob([JSON.stringify(decisions,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=el('a');link.href=url;link.download='review_decisions.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById('feedback').textContent='已导出。未判候选及待审题目仍保持未判、待审；请保留原 packet.json。';}catch(error){document.getElementById('feedback').textContent=error.message;}});
document.getElementById('resume').addEventListener('change',async event=>{try{const file=event.target.files[0];if(!file)return;const data=JSON.parse(await file.text());if(data.packet_sha256!==packet.packet_sha256)throw Error('该决定文件不属于此复核包。');if(!Array.isArray(data.cases)||data.cases.length!==states.length)throw Error('题目数量不一致。');const byCase=new Map(data.cases.map(c=>[c.case_id,c]));if(byCase.size!==states.length)throw Error('题目重复。');const assignments=states.map(s=>{const c=byCase.get(s.item.case_id);if(!c||c.case_definition_sha256!==s.item.case_definition_sha256||!Array.isArray(c.candidates)||c.candidates.length!==s.units.length)throw Error('题目或候选身份不一致。');const units=new Map(c.candidates.map(u=>[u.unit_id,u]));if(units.size!==s.units.length||!['pending','approved','rejected'].includes(c.status))throw Error('无效状态或重复候选。');const mapped=s.units.map(u=>{const d=units.get(u.unit.unit_id);if(!d||d.identity_sha256!==u.unit.identity_sha256||![null,0,1,2].includes(d.relevance)||!Array.isArray(d.supported_groups)||d.supported_groups.some(g=>!(g in u.groupInputs)))throw Error('候选身份或判断格式不一致。');return [u,d];});return [s,c,mapped];});document.getElementById('reviewer').value=data.reviewer||'';assignments.forEach(([s,c,mapped])=>{s.status.value=c.status;s.notes.value=c.notes||'';Object.entries(s.confirms).forEach(([key,input])=>input.checked=c.confirmations?.[key]===true);mapped.forEach(([u,d])=>{u.radios.forEach(r=>r.checked=d.relevance!==null&&r.value===String(d.relevance));u.sync();u.reason.value=d.reason||'';Object.entries(u.groupInputs).forEach(([g,input])=>input.checked=d.relevance===2&&d.supported_groups.includes(g));});});document.getElementById('feedback').textContent='已载入上次进度；最终导入仍会对原始题目、证据和候选做严格校验。';}catch(error){document.getElementById('feedback').textContent=error.message;}finally{event.target.value='';}});
</script></main></body></html>"""  # noqa: E501 - standalone HTML/CSS/JS asset, with no remote dependencies.


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    build_parser.add_argument("--capture", type=Path, required=True)
    build_parser.add_argument("--output-dir", type=Path, required=True)
    build_parser.add_argument("--project-root", type=Path)
    build_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    importer = sub.add_parser("import")
    importer.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    importer.add_argument("--capture", type=Path, required=True)
    importer.add_argument("--packet", type=Path, required=True)
    importer.add_argument("--decisions", type=Path, required=True)
    importer.add_argument("--output", type=Path, required=True)
    importer.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        build(
            args.dataset,
            args.capture,
            args.output_dir,
            project_root=args.project_root,
            seed=args.seed,
        )
        print(args.output_dir / "review.html")
    else:
        import_decisions(
            args.dataset,
            args.capture,
            args.packet,
            args.decisions,
            args.output,
            project_root=args.project_root,
        )
        print(args.output)


if __name__ == "__main__":
    main()
