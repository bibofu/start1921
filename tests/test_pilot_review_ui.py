from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from typing import Any

import pytest
from history_agent.evaluation.pilot_answers import DIMENSIONS
from history_agent.evaluation.pilot_review_ui import render_review_workspace


def _fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    files: dict[str, Any] = {}
    reviews = {}
    for prefix, variant, capture_hash in (
        ("", "with_history", "a" * 64),
        ("controls/without_history_control/", "without_history_control", "b" * 64),
    ):
        definition = {
            "question": "开放问题",
            "answerability": "answerable",
            "facts": [{"id": "f1", "claim": "必要事实", "required": True}],
            "evidence_groups": [],
        }
        files[prefix + "review_packet.json"] = {
            "capture_sha256": capture_hash,
            "source_documents": {
                "known_document": {"title": "核对用书名", "relative_path": "corpus/book.pdf"}
            },
            "cases": [
                {
                    "case_id": "open_case",
                    "input_variant_id": variant,
                    "definition": definition,
                    "answer": {"answer": "本次回答原文。", "citations": [{"evidence_id": "E1"}]},
                    "request": {
                        "question": "开放问题",
                        "history": [{"role": "user", "content": "先前问题"}] if not prefix else [],
                    },
                }
            ],
        }
        reviews[prefix + "answer_reviews.json"] = {
            "schema_version": 1,
            "capture_sha256": capture_hash,
            "cases": [
                {
                    "case_id": "open_case",
                    "case_definition_sha256": "c" * 64,
                    "answer_sha256": ("d" if not prefix else "e") * 64,
                    "basis": None,
                    "reviewer": None,
                    "reviewed_at": None,
                    "facts": [
                        {
                            "fact_id": "f1",
                            "status": "unknown",
                            "reason": "待逐事实复核",
                            "support_status": "unknown",
                            "answer_excerpt": None,
                            "cited_evidence_ids": [],
                        }
                    ],
                    "dimensions": {
                        name: {"status": "unknown", "reason": "待本次复核"} for name in DIMENSIONS
                    },
                }
            ],
        }
        reviews[prefix + "process_reviews.json"] = {
            "schema_version": 2,
            "capture_sha256": capture_hash,
            "cases": [
                {
                    "case_id": "open_case",
                    "case_definition_sha256": "c" * 64,
                    "basis": None,
                    "reviewer": None,
                    "reviewed_at": None,
                    "criterion": "核对计划",
                    "status": "unknown",
                    "reason": "等待复核",
                    "executed_query_plan": None,
                    "observed_query_variants": ["开放问题"],
                }
            ],
        }
    reviews["specialist_reviews.json"] = {
        "schema_version": 1,
        "capture_sha256": "a" * 64,
        "cases": [],
        "paired_isolation": [
            {
                "case_id": "open_case",
                "input_bindings": [
                    {"input_variant_id": "with_history", "input_sha256": "d" * 64},
                    {"input_variant_id": "without_history_control", "input_sha256": "e" * 64},
                ],
                "basis": None,
                "reviewer": None,
                "reviewed_at": None,
                "dimensions": {
                    "history_isolation": {
                        "denominator": 1,
                        "checks": [
                            {
                                "check_id": "isolation.1",
                                "criterion": "计划未带入上题人物",
                                "status": "unknown",
                                "reason": "等待专项复核",
                            }
                        ],
                    }
                },
            }
        ],
    }
    files["review_bundle.json"] = {
        "schema_version": 1,
        "kind": "pilot-review-bundle",
        "capture_sha256": "a" * 64,
        "calibration_sha256": "f" * 64,
        "template_sha256": "c" * 64,
        "dataset_sha256": "d" * 64,
        "protocol_sha256": None,
        "exported_at": None,
        "files": reviews,
    }
    return files, {"policy": {"principles": ["不强制参考答案措辞"]}, "cases": []}


def _embedded(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S
    )
    assert match
    return json.loads(match.group(1))


def _script(html: str) -> str:
    return html.split("<script>\n", 1)[1].split("</script>", 1)[0]


def _run_js(code: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is optional; browser behavior is also verified manually")
    files, calibration = _fixture()
    html = render_review_workspace(files, calibration)
    # Initialize the data model without a DOM implementation or event handlers.
    program = _script(html).split("$('save-draft').addEventListener", 1)[0]
    prelude = (
        "const assert = require('node:assert/strict');\n"
        "const document = {getElementById: () => ({textContent: "
        + json.dumps(json.dumps(_embedded(html), ensure_ascii=False))
        + "})};\n"
    )
    result = subprocess.run(
        [node, "-"], input=prelude + program + code, text=True, encoding="utf8", capture_output=True
    )
    assert result.returncode == 0, result.stderr


def test_embedded_sources_and_reviews_are_lossless_and_unchanged() -> None:
    files, calibration = _fixture()
    before = copy.deepcopy((files, calibration))
    data = _embedded(render_review_workspace(files, calibration))
    assert (files, calibration) == before
    assert data["bundle"] == files["review_bundle.json"]
    assert len(data["packets"]) == 2
    assert data["calibration"] == calibration
    assert data["bundle"]["files"]["answer_reviews.json"]["cases"][0]["basis"] is None


def test_untrusted_answer_does_not_escape_json_script() -> None:
    files, calibration = _fixture()
    attack = '</script><script>alert("answer")</script><img src=x onerror=alert(1)>\u2028&'
    files["review_packet.json"]["cases"][0]["answer"]["answer"] = attack
    calibration["policy"]["principles"].append(attack)
    html = render_review_workspace(files, calibration)
    assert attack not in html
    assert html.count("</script>") == 2
    assert (
        _embedded(html)["packets"]["review_packet.json"]["cases"][0]["answer"]["answer"] == attack
    )
    assert "innerHTML" not in _script(html)
    assert "fetch(" not in _script(html)
    assert "default-src 'none'" in html


def test_workspace_requires_prepared_bundle_and_matching_capture() -> None:
    files, calibration = _fixture()
    files["review_bundle.json"]["capture_sha256"] = "wrong"
    with pytest.raises(ValueError, match="capture binding"):
        render_review_workspace(files, calibration)
    del files["review_bundle.json"]
    with pytest.raises(ValueError, match="prepared"):
        render_review_workspace(files, calibration)


def test_complete_browser_script_is_syntactically_valid() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is optional")
    files, calibration = _fixture()
    result = subprocess.run(
        [node, "--check", "-"],
        input=_script(render_review_workspace(files, calibration)),
        encoding="utf8",
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr


def test_draft_accepts_decisions_but_rejects_binding_and_control_swap() -> None:
    _run_js(
        """
const edited=clone(TEMPLATE);
edited.files['answer_reviews.json'].cases[0].facts[0].status='covered';
edited.files['answer_reviews.json'].cases[0].facts[0].reason='核对本次原文';
assert.doesNotThrow(()=>assertBound(edited));
for(const key of ['capture_sha256','calibration_sha256','template_sha256']){
 const bad=clone(TEMPLATE);bad[key]='changed';assert.throws(()=>assertBound(bad));
}
const swapped=clone(TEMPLATE);
swapped.files['answer_reviews.json']=clone(swapped.files[
 'controls/without_history_control/answer_reviews.json']);
assert.throws(()=>assertBound(swapped));
const observed=clone(TEMPLATE);
observed.files['process_reviews.json'].cases[0].observed_query_variants=['不同查询'];
assert.throws(()=>assertBound(observed));
const criterion=clone(TEMPLATE);
criterion.files['specialist_reviews.json'].paired_isolation[0].dimensions
 .history_isolation.checks[0].criterion='别的口径';
assert.throws(()=>assertBound(criterion));
const malformed=clone(TEMPLATE);
malformed.files['answer_reviews.json'].cases[0].facts[0].cited_evidence_ids={E1:true};
assert.throws(()=>assertBound(malformed));
assert.equal(bundle.files['answer_reviews.json'].cases[0].facts[0].status,'unknown');
"""
    )


def test_export_keeps_unknown_na_and_requires_identity_and_actual_evidence() -> None:
    _run_js(
        """
assert.deepEqual(validateDecisions(),[]);
const row=bundle.files['answer_reviews.json'].cases[0],fact=row.facts[0];
fact.status='covered';fact.support_status='supported';
assert.ok(validateDecisions().some(s=>s.includes('复核人')));
assert.ok(validateDecisions().some(s=>s.includes('实际引文')));
Object.assign(row,{basis:'agent_review',reviewer:'review-agent',
 reviewed_at:'2026-10-11T12:00:00+08:00'});
Object.assign(fact,{cited_evidence_ids:['E1'],answer_excerpt:'本次回答原文。',reason:'核对回答原文与E1'});
assert.deepEqual(validateDecisions(),[]);
fact.cited_evidence_ids=['E999'];
assert.ok(validateDecisions().some(s=>s.includes('引用编号')));
fact.cited_evidence_ids=['E1'];fact.answer_excerpt='不存在的新句子';
assert.ok(validateDecisions().some(s=>s.includes('摘录必须')));
fact.answer_excerpt=null;row.reviewed_at='2026-10-11T12:00:00';
assert.ok(validateDecisions().some(s=>s.includes('时区')));
row.reviewed_at='2026-10-11T12:00:00Z';fact.support_status='unsupported';
row.dimensions.citation_support.status='pass';
assert.ok(validateDecisions().some(s=>s.includes('矛盾')));
"""
    )


def test_paired_check_decision_cannot_inherit_answer_identity() -> None:
    _run_js(
        """
const row=bundle.files['specialist_reviews.json'].paired_isolation[0];
row.dimensions.history_isolation.checks[0].status='pass';
assert.ok(validateDecisions().some(s=>s.includes('专项')));
Object.assign(row,{basis:'human_review',reviewer:'reviewer',reviewed_at:'2026-10-11T12:00:00Z'});
assert.deepEqual(validateDecisions(),[]);
assert.equal(bundle.files['answer_reviews.json'].cases[0].basis,null);
"""
    )


def test_calibrated_decisions_require_body_excerpt_and_substantive_reason() -> None:
    _run_js(
        """
const row=bundle.files['answer_reviews.json'].cases[0],fact=row.facts[0];
Object.assign(row,{basis:'agent_review',reviewer:'review-agent',reviewed_at:'2026-10-11T12:00:00Z'});
fact.status='partial';
assert.ok(validateDecisions().some(s=>s.includes('原文摘录')));
assert.ok(validateDecisions().some(s=>s.includes('占位文字')));
fact.answer_excerpt='本次回答原文。';fact.reason='正文缺少后一项要求';
fact.support_status='not_applicable';
assert.ok(validateDecisions().some(s=>s.includes('支持不能标记')));
fact.status='missing';fact.support_status='supported';fact.cited_evidence_ids=['E1'];
assert.ok(validateDecisions().some(s=>s.includes('未覆盖的正文事实')));
fact.support_status='not_applicable';fact.answer_excerpt=null;
assert.deepEqual(validateDecisions(),[]);
row.dimensions.routing.status='not_applicable';row.dimensions.routing.reason='没有检查路由';
assert.ok(validateDecisions().some(s=>s.includes('适用维度')));
assert.equal(dimensionApplies(arms[0],'citation_support'),true);
assert.equal(dimensionApplies(arms[0],'time_constraint'),false);
arms[0].row.definition.question='只依据此书介绍1925年活动';
assert.equal(dimensionApplies(arms[0],'time_constraint'),true);
assert.equal(dimensionApplies(arms[0],'source_constraint'),true);
arms[0].row.definition.answerability='unanswerable';
assert.equal(dimensionApplies(arms[0],'safe_refusal'),true);
"""
    )


def test_process_and_paired_judgments_reject_template_reasons() -> None:
    _run_js(
        """
const process=bundle.files['process_reviews.json'].cases[0];
const pair=bundle.files['specialist_reviews.json'].paired_isolation[0];
for(const row of [process,pair])Object.assign(row,{basis:'agent_review',reviewer:'review-agent',
 reviewed_at:'2026-10-11T12:00:00Z'});
process.status='pass';process.reason='awaiting_explicit_process_review';
const check=pair.dimensions.history_isolation.checks[0];
check.status='fail';check.reason='awaiting_explicit_specialist_review';
assert.equal(validateDecisions().filter(s=>s.includes('占位文字')).length,2);
process.reason='实际计划保留当前问题实体';check.reason='上下文选择包含上一题人物';
assert.deepEqual(validateDecisions(),[]);
"""
    )


def test_golden_source_title_uses_corpus_mapping_and_falls_back_to_id() -> None:
    _run_js(
        """
assert.equal(sourceTitle({document_id:'known_document'}),'核对用书名');
assert.equal(sourceTitle({document_id:'unmapped_document'}),'unmapped_document');
"""
    )
