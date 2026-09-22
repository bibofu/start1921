import hashlib
import json
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from history_agent.evaluation.pilot import digest, read_json, write_json
from history_agent.evaluation.pilot_metrics import evaluate_stage, evidence_unit
from history_agent.evaluation.pilot_models import PilotDataset, case_definition
from history_agent.evaluation.pilot_review import CONFIRMATIONS, build, import_decisions


@pytest.fixture
def bundle(tmp_path: Path) -> dict[str, Any]:
    pdf = tmp_path / "docs" / "测试 年谱.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"%PDF-1.7\nlocal review test fixture\n")
    file_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    file_hashes = {"doc": file_hash}
    hits = [
        {
            "document_id": "doc",
            "pdf_page_start": page,
            "pdf_page_end": page,
            "text": text,
            "rank": page,
            "retrieval_reason": "SECRET_BRANCH_HINT",
        }
        for page, text in enumerate(
            [
                "他出任总理。主持会议。",
                "相关人物到场。",
                "其他历史背景。",
                "<script>恶意文本</script>",
            ],
            1,
        )
    ]
    units = [evidence_unit(hit, file_hashes) for hit in hits]
    dataset = PilotDataset.model_validate(
        {
            "schema_version": 1,
            "version": "review-test-v1",
            "description": "review test",
            "evidence_group_semantics": {"between": "AND", "within": "OR"},
            "cases": [
                {
                    "id": "p1",
                    "question": "他担任什么职务？",
                    "category": "fact",
                    "answerability": "answerable",
                    "split": "development",
                    "topic_group": "appointment",
                    "human_review": {"status": "pending"},
                    "evidence_groups": [
                        {
                            "id": "g1",
                            "description": "任职事实",
                            "alternatives": [
                                {
                                    "document_id": "doc",
                                    "pdf_page": 1,
                                    "file_sha256": file_hash,
                                    "quote": "出任总理",
                                    "agent_verification": {"reason": "SECRET_AGENT_CHECK"},
                                }
                            ],
                        }
                    ],
                    "facts": [{"id": "f1", "claim": "出任总理。", "evidence_group_ids": ["g1"]}],
                    "reference_answer": "SECRET_AGENT_ANSWER",
                    "review_notes": ["SECRET_AGENT_ADVICE"],
                    "judgments": [
                        {
                            "unit_id": unit_id,
                            "relevance": 2,
                            "reason": "SECRET_AGENT_LABEL",
                            "reviewer": "agent",
                            "reviewed_at": "2026-09-22T01:00:00+00:00",
                            "basis": "agent_review",
                            "supported_groups": ["g1"],
                        }
                        for unit_id in [units[0]["unit_id"], units[1]["unit_id"], "uncaptured"]
                    ],
                }
            ],
        }
    ).model_dump(mode="json")
    documents = [
        {
            "document_id": "doc",
            "title": "测试年谱",
            "sha256": file_hash,
            "relative_path": "docs/测试 年谱.pdf",
            "page_count": 4,
        }
    ]
    capture = {
        "schema_version": 1,
        "dataset_sha256": digest(dataset),
        "corpus": {"documents": documents, "sha256": digest(documents)},
        "cases": [
            {
                "case_id": "p1",
                "question": dataset["cases"][0]["question"],
                "case_definition_sha256": digest(case_definition(dataset["cases"][0])),
                "candidate_pool": units,
                "answer": "SECRET_GENERATED_ANSWER",
                "stages": [{"stage": "SECRET_KEYWORD_STAGE", "hits": hits[:2]}],
                "production_stages": [{"stage": "SECRET_PRODUCTION_STAGE", "hits": hits[2:3]}],
                "generation_contexts": [{"hits": hits[3:]}],
            }
        ],
    }
    dataset_path = tmp_path / "draft.json"
    capture_path = tmp_path / "capture.json"
    write_json(dataset_path, dataset)
    write_json(capture_path, capture)
    packet = build(dataset_path, capture_path, tmp_path / "review", project_root=tmp_path)
    decisions = {
        "schema_version": 1,
        "packet_sha256": packet["packet_sha256"],
        "reviewer": "复核者甲",
        "reviewed_at": "2026-09-22T12:00:00+08:00",
        "cases": [
            {
                "case_id": case["case_id"],
                "case_definition_sha256": case["case_definition_sha256"],
                "status": "pending",
                "confirmations": dict.fromkeys(CONFIRMATIONS, False),
                "notes": "尚在核对",
                "candidates": [
                    {
                        "unit_id": unit["unit_id"],
                        "identity_sha256": unit["identity_sha256"],
                        "relevance": None,
                        "reason": "",
                        "supported_groups": [],
                    }
                    for unit in case["candidates"]
                ],
            }
            for case in packet["cases"]
        ],
    }
    return {
        "root": tmp_path,
        "pdf": pdf,
        "dataset": dataset,
        "capture": capture,
        "packet": packet,
        "decisions": decisions,
        "dataset_path": dataset_path,
        "capture_path": capture_path,
        "packet_path": tmp_path / "review" / "packet.json",
        "decisions_path": tmp_path / "decisions.json",
        "output": tmp_path / "annotations.reviewed.json",
        "hits": hits,
        "file_hashes": file_hashes,
    }


def _import(bundle: dict[str, Any], *, output: Path | None = None) -> dict[str, Any]:
    write_json(bundle["decisions_path"], bundle["decisions"])
    return import_decisions(
        bundle["dataset_path"],
        bundle["capture_path"],
        bundle["packet_path"],
        bundle["decisions_path"],
        output or bundle["output"],
        project_root=bundle["root"],
    )


def _human_label(bundle: dict[str, Any]) -> None:
    first_id = bundle["capture"]["cases"][0]["candidate_pool"][0]["unit_id"]
    first = next(
        item
        for item in bundle["decisions"]["cases"][0]["candidates"]
        if item["unit_id"] == first_id
    )
    first.update(
        relevance=2, reason="原文明确记载出任总理，直接支持任职事实。", supported_groups=["g1"]
    )


def test_review_is_blinded_deterministic_and_links_exact_sources(bundle: dict[str, Any]) -> None:
    packet = bundle["packet"]
    again = build(
        bundle["dataset_path"],
        bundle["capture_path"],
        bundle["root"] / "another",
        project_root=bundle["root"],
    )
    assert again == packet
    html = (bundle["root"] / "review" / "review.html").read_text(encoding="utf8")
    serialized = json.dumps(packet, ensure_ascii=False)
    for secret in ["SECRET_", "agent_verification", '"rank"', '"score"', '"stages"']:
        assert secret not in serialized
        assert secret not in html
    candidates = packet["cases"][0]["candidates"]
    originals = bundle["capture"]["cases"][0]["candidate_pool"]
    assert {u["unit_id"] for u in candidates} == {u["unit_id"] for u in originals}
    assert [u["unit_id"] for u in candidates] != [u["unit_id"] for u in originals]
    for unit in candidates:
        assert unit["title"] == "测试年谱"
        assert unit["pdf_url"] == bundle["pdf"].as_uri() + f"#page={unit['pdf_page_start']}"
        original = next(u for u in originals if u["unit_id"] == unit["unit_id"])
        assert unit["text"] == original["text"]
    assert "<script>恶意文本</script>" not in html
    assert "\\u003cscript>恶意文本\\u003c/script>" in html
    assert "AND" in html and "OR" in html
    assert "不是已批准的 Golden" in html
    assert "fetch(" not in html
    assert "connect-src 'none'" in html


def test_partial_review_replaces_only_captured_labels_and_keeps_unknown(
    bundle: dict[str, Any],
) -> None:
    _human_label(bundle)
    original_bytes = bundle["dataset_path"].read_bytes()
    result = _import(bundle)
    case = result["cases"][0]
    assert case["human_review"]["status"] == "pending"
    assert len(case["judgments"]) == 2
    assert {j["basis"] for j in case["judgments"]} == {"human_review", "agent_review"}
    assert (
        next(j for j in case["judgments"] if j["basis"] == "agent_review")["unit_id"]
        == "uncaptured"
    )
    assert sum(j["basis"] == "human_review" for j in case["judgments"]) == 1
    assert digest(case_definition(case)) == digest(case_definition(bundle["dataset"]["cases"][0]))
    assert bundle["dataset_path"].read_bytes() == original_bytes
    audit = read_json(bundle["output"].with_suffix(".audit.json"))
    assert audit["reviewed_dataset_sha256"] == digest(result)
    assert audit["packet_sha256"] == bundle["packet"]["packet_sha256"]
    assert (
        audit["decisions"]["cases"][0]["candidates"]
        == bundle["decisions"]["cases"][0]["candidates"]
    )


def test_production_only_candidate_is_reviewable_and_identity_bound(bundle: dict[str, Any]) -> None:
    raw = bundle["capture"]["cases"][0]
    production_hit = raw["production_stages"][0]["hits"][0]
    assert all(
        production_hit not in stage["hits"]
        for stage in [*raw["stages"], *raw["generation_contexts"]]
    )
    unit_id = evidence_unit(production_hit, bundle["file_hashes"])["unit_id"]
    packet_unit = next(
        unit for unit in bundle["packet"]["cases"][0]["candidates"] if unit["unit_id"] == unit_id
    )
    assert packet_unit["text"] == production_hit["text"]
    decision = next(
        unit for unit in bundle["decisions"]["cases"][0]["candidates"] if unit["unit_id"] == unit_id
    )
    decision.update(relevance=1, reason="描述时代背景，没有直接记载任职事实。")
    reviewed = _import(bundle)
    judgment = next(
        unit for unit in reviewed["cases"][0]["judgments"] if unit["unit_id"] == unit_id
    )
    assert judgment["basis"] == "human_review"
    assert judgment["relevance"] == 1

    raw["production_stages"] = []
    write_json(bundle["capture_path"], bundle["capture"])
    with pytest.raises(ValueError, match="candidate pool differs from the executed stages"):
        build(
            bundle["dataset_path"],
            bundle["capture_path"],
            bundle["root"] / "missing-production",
            project_root=bundle["root"],
        )


def test_explicit_approval_allows_unknown_candidates_without_zero_scoring(
    bundle: dict[str, Any],
) -> None:
    _human_label(bundle)
    decision = bundle["decisions"]["cases"][0]
    decision.update(status="approved", confirmations=dict.fromkeys(CONFIRMATIONS, True))
    reviewed = _import(bundle)
    case = reviewed["cases"][0]
    assert case["human_review"]["status"] == "approved"
    metrics = evaluate_stage(
        case, bundle["hits"], bundle["file_hashes"], (1, 2), label_mode="approved"
    )
    assert metrics["metrics"]["precision@1"]["value"] == 1.0
    assert metrics["metrics"]["precision@2"]["value"] is None
    assert metrics["metrics"]["mrr@2"]["value"] == 1.0


@pytest.mark.parametrize("missing", ["question", "evidence", "facts", "refusal"])
def test_approval_requires_every_explicit_confirmation(
    bundle: dict[str, Any], missing: str
) -> None:
    case = bundle["decisions"]["cases"][0]
    case.update(status="approved", confirmations=dict.fromkeys(CONFIRMATIONS, True))
    case["confirmations"][missing] = False
    with pytest.raises(ValueError, match="approval requires"):
        _import(bundle)
    assert not bundle["output"].exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [("reviewer", "  "), ("reviewed_at", " "), ("reviewed_at", "2026-09-22T12:00:00")],
)
def test_missing_review_metadata_is_rejected(
    bundle: dict[str, Any], field: str, value: str
) -> None:
    bundle["decisions"][field] = value
    with pytest.raises(ValueError):
        _import(bundle)


@pytest.mark.parametrize("reason", ["", "   ", "是"])
def test_scored_candidate_cannot_import_without_specific_reason(
    bundle: dict[str, Any], reason: str
) -> None:
    unit = bundle["decisions"]["cases"][0]["candidates"][0]
    unit.update(relevance=1, reason=reason)
    with pytest.raises(ValueError, match="specific review reason"):
        _import(bundle)


@pytest.mark.parametrize("target", ["question", "evidence", "candidate", "digest"])
def test_packet_tampering_rejected_even_with_recomputed_hash(
    bundle: dict[str, Any], target: str
) -> None:
    packet = deepcopy(bundle["packet"])
    case = packet["cases"][0]
    if target == "question":
        case["question"] = "篡改问题"
    elif target == "evidence":
        case["evidence_groups"][0]["alternatives"][0]["quote"] = "伪造引文"
    elif target == "candidate":
        case["candidates"][0]["text"] = "伪造候选"
    packet["packet_sha256"] = digest({k: v for k, v in packet.items() if k != "packet_sha256"})
    if target == "digest":
        packet["packet_sha256"] = "0" * 64
    write_json(bundle["packet_path"], packet)
    with pytest.raises(ValueError, match="immutable packet"):
        _import(bundle)


@pytest.mark.parametrize(
    "attack", ["duplicate", "unknown", "missing", "identity", "rewrite", "bool"]
)
def test_bad_candidate_decisions_rejected(bundle: dict[str, Any], attack: str) -> None:
    units = bundle["decisions"]["cases"][0]["candidates"]
    if attack == "duplicate":
        units.append(deepcopy(units[0]))
    elif attack == "unknown":
        units[0]["unit_id"] = "unknown-unit"
    elif attack == "missing":
        units.pop()
    elif attack == "identity":
        units[0]["identity_sha256"] = "0" * 64
    elif attack == "rewrite":
        units[0]["text"] = "不能改写证据"
    else:
        units[0].update(relevance=True, reason="无效布尔分数")
    with pytest.raises(ValueError):
        _import(bundle)
    assert not bundle["output"].exists()


@pytest.mark.parametrize("target", ["dataset", "capture", "pdf"])
def test_changed_original_inputs_rejected(bundle: dict[str, Any], target: str) -> None:
    if target == "dataset":
        bundle["dataset"]["cases"][0]["facts"][0]["claim"] = "被改写的事实"
        write_json(bundle["dataset_path"], bundle["dataset"])
    elif target == "capture":
        bundle["capture"]["cases"][0]["answer"] = "改变运行结果也需重新建包"
        write_json(bundle["capture_path"], bundle["capture"])
    else:
        bundle["pdf"].write_bytes(b"different PDF")
    with pytest.raises(ValueError):
        _import(bundle)


@pytest.mark.parametrize("attack", ["identity", "text", "missing", "duplicate", "stage"])
def test_build_rejects_pool_identity_and_actual_trace_disagreement(
    bundle: dict[str, Any], attack: str
) -> None:
    case = bundle["capture"]["cases"][0]
    units = case["candidate_pool"]
    if attack == "identity":
        units[0]["identity"]["pdf_page_start"] = 99
    elif attack == "text":
        units[0]["text"] = "替换实际召回原文"
    elif attack == "missing":
        units.pop()
    elif attack == "duplicate":
        units.append(deepcopy(units[0]))
    else:
        case["stages"][0]["hits"].pop()
    write_json(bundle["capture_path"], bundle["capture"])
    with pytest.raises(ValueError):
        build(
            bundle["dataset_path"],
            bundle["capture_path"],
            bundle["root"] / "bad",
            project_root=bundle["root"],
        )


def test_output_cannot_overwrite_original_or_existing_golden(bundle: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="original input"):
        _import(bundle, output=bundle["dataset_path"])
    golden = bundle["root"] / "existing_golden.json"
    golden.write_text("preserve exact content", encoding="utf8")
    with pytest.raises(FileExistsError):
        _import(bundle, output=golden)
    assert golden.read_text(encoding="utf8") == "preserve exact content"
    with pytest.raises(FileExistsError):
        build(
            bundle["dataset_path"],
            bundle["capture_path"],
            bundle["root"] / "review",
            project_root=bundle["root"],
        )
    _import(bundle)
    with pytest.raises(FileExistsError):
        _import(bundle)


def test_offline_javascript_has_no_default_grades_or_automatic_approval(
    bundle: dict[str, Any],
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable for the offline JavaScript interaction check")
    html = (bundle["root"] / "review" / "review.html").read_text(encoding="utf8")
    script = re.search(r"<script>\n(.*?)</script>", html, flags=re.DOTALL)
    assert script is not None
    # A minimal DOM runs the shipped JavaScript, including its initial state and
    # export gates; all validation against immutable sources remains in Python.
    harness = """
const assert = require('node:assert/strict');
class Element {
 constructor(tag) {
  this.tag=tag; this.value=''; this.checked=false; this.children=[]; this.handlers={};
 }
 append(...items) {
  if(this.tag==='select'&&!this.children.length&&items.length)this.value=items[0].value;
  this.children.push(...items);
 }
 setAttribute() {}
 addEventListener(name,handler) { this.handlers[name]=handler; }
 scrollIntoView() { this.scrolled=true; }
}
const names=['packet','reviewer','cases','save','resume','feedback','case-nav','case-progress'];
const ids = new Map(names.map(id=>[id,new Element(id)]));
const document={
 getElementById:id=>ids.get(id),createElement:tag=>new Element(tag),createTextNode:t=>t
};
"""
    ui_packet = deepcopy(bundle["packet"])
    second = deepcopy(ui_packet["cases"][0])
    second.update(case_id="p2", question="第二个待审问题")
    ui_packet["cases"].append(second)
    harness += "ids.get('packet').textContent=" + json.dumps(json.dumps(ui_packet)) + ";\n"
    harness += script.group(1)
    harness += """
assert.throws(()=>decisionData(),/复核者/);
ids.get('reviewer').value='人工甲';
const initial=decisionData();
assert.equal(initial.cases.length,2);
assert.equal(ids.get('case-nav').children.length,2);
assert.equal(states[0].section.hidden,false);
assert.equal(states[1].section.hidden,true);
assert.equal(initial.cases[0].status,'pending');
assert.ok(initial.cases[0].candidates.every(u=>u.relevance===null));
assert.ok(states[0].units.every(u=>u.radios.every(r=>!r.checked)));
assert.ok(Object.values(initial.cases[0].confirmations).every(v=>v===false));
states[0].status.value='approved';
assert.throws(()=>decisionData(),/全部四项/);
Object.values(states[0].confirms).forEach(input=>input.checked=true);
const explicit=decisionData();
assert.equal(explicit.cases[0].status,'approved');
assert.ok(explicit.cases[0].candidates.every(u=>u.relevance===null));
states[0].units[0].radios[2].checked=true;
states[0].units[0].sync();
assert.ok(Object.values(states[0].units[0].groupInputs).every(input=>!input.disabled));
assert.equal(decisionData().cases[0].candidates[0].relevance,2);
states[0].units[0].reason.value='第一题原文支持';
states[0].notes.value='保留第一题复核意见';
ids.get('case-nav').value='1';
ids.get('case-nav').handlers.change();
assert.equal(states[0].section.hidden,true);
assert.equal(states[1].section.hidden,false);
assert.equal(states[1].section.scrolled,true);
assert.equal(decisionData().cases[1].status,'pending');
assert.ok(decisionData().cases[1].candidates.every(u=>u.relevance===null));
assert.equal(decisionData().cases[0].candidates[0].relevance,2);
states[1].notes.value='保留第二题复核意见';
ids.get('case-nav').value='0';
ids.get('case-nav').handlers.change();
const afterSwitch=decisionData();
assert.equal(states[0].section.hidden,false);
assert.equal(states[1].section.hidden,true);
assert.equal(afterSwitch.cases[0].status,'approved');
assert.equal(afterSwitch.cases[0].candidates[0].reason,'第一题原文支持');
assert.equal(afterSwitch.cases[0].notes,'保留第一题复核意见');
assert.equal(afterSwitch.cases[1].notes,'保留第二题复核意见');
assert.ok(Object.values(afterSwitch.cases[1].confirmations).every(v=>v===false));
"""
    result = subprocess.run(
        [node, "-"], input=harness, encoding="utf8", capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
