"""Prepare a local candidate from a freshly saved Dataverse workflow record.

This command performs no network calls and does not deploy or run a flow.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


def walk(actions):
    for name, action in actions.items():
        yield name, action
        yield from walk(action.get("actions", {}))
        yield from walk(action.get("else", {}).get("actions", {}))


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def log_line(suffix, index):
    lines = f"outputs('Compose_LogLines{suffix}')"
    get = lambda i: f"string(coalesce({lines}?[{i}],''))"
    return f"if(startsWith({get(0)},'処理日: '),{get(index+1)},{get(index)})"


def mismatch(kind, raw_line, prefix, case_column):
    selected = f"string(coalesce(outputs('Get_case')?['body/{case_column}'],''))"
    actual = f"substring({raw_line},{len(prefix)})"
    return (
        f"concat('{kind}が一致しないため、照合を停止しました。',decodeUriComponent('%0A'),"
        f"'選択した{kind}：',{selected},decodeUriComponent('%0A'),"
        f"'ログの{kind}：',{actual},decodeUriComponent('%0A'),"
        f"'ログを取得した{kind}を選び直してください。')"
    )


def pair_filter():
    # OData string literals must escape apostrophes in user-entered names.
    quote = "decodeUriComponent('%27')"
    escaped = lambda col: (
        f"replace(string(outputs('Get_case')?['body/{col}']),"
        f"{quote},decodeUriComponent('%27%27'))"
    )
    return (
        "@concat('cr6cb_environment eq '," + quote + ","
        + escaped("cr6cb_environment") + "," + quote
        + ",' and cr6cb_server eq '," + quote + ","
        + escaped("cr6cb_server") + "," + quote + ")"
    )


def prepare(record):
    before = json.loads(record["clientdata"])
    candidate = copy.deepcopy(before)
    actions = dict(walk(candidate["properties"]["definition"]["actions"]))
    base_actions = dict(walk(before["properties"]["definition"]["actions"]))
    allowed = set()
    for suffix in ("", "_MQ"):
        reason_key = "Compose_LogValidationReason" + suffix
        expr = actions[reason_key]["inputs"]
        for kind, index, prefix, column in (
            ("環境", 0, "環境: ", "cr6cb_environment"),
            ("サーバー", 1, "サーバー: ", "cr6cb_server"),
        ):
            raw = log_line(suffix, index)
            missing = f"not(startsWith({raw},{literal(prefix)}))"
            assert missing in expr, (reason_key, kind)
            expr = expr.replace(missing, f"or({missing},equals({raw},{literal(prefix)}))", 1)
            old_missing = f"ログに{kind}の識別情報がありません。"
            new_missing = (
                f"ログから{kind}名を読み取れないため、照合を停止しました。\n"
                f"ログの先頭に「{prefix}実際の名称」が記載されているか確認してください。"
            )
            assert literal(old_missing) in expr
            expr = expr.replace(literal(old_missing), literal(new_missing), 1)
            old_mismatch = f"ログの{kind}が件の{kind}と一致しません。"
            assert literal(old_mismatch) in expr
            expr = expr.replace(literal(old_mismatch), mismatch(kind, raw, prefix, column), 1)
        actions[reason_key]["inputs"] = expr
        allowed.add(reason_key)

        query_key = "List_active_destinations" + suffix
        query = actions[query_key]["inputs"]["parameters"]
        query["$select"] += ",cr6cb_environmentenabled"
        query["$filter"] = pair_filter()
        query["$top"] = 2
        allowed.add(query_key)

        filter_body = "body('Filter_active_destinations" + suffix + "')"
        row = f"first({filter_body})"
        condition_key = "Condition_One_Destination" + suffix
        old_check = actions[condition_key]["expression"]["equals"][0]
        folder_id = "01VTXCECE5BP476QXS7RFIAAAMC5QNGY6X"
        assert folder_id in old_check
        actions[condition_key]["expression"]["equals"][0] = (
            f"@if(equals(length({filter_body}),1),and("
            f"equals(coalesce({row}?['cr6cb_environmentenabled'],true),true),"
            f"equals({row}?['cr6cb_isactive'],true),"
            f"equals({row}?['cr6cb_folderid'],{literal(folder_id)}),"
            f"not(empty({row}?['cr6cb_driveid']))),false)"
        )

        stop_key = "Update_case_stop_destination" + suffix
        stop = actions[stop_key]["inputs"]["parameters"]
        invalid = "環境・サーバーの登録を確認できないため、照合を停止しました。\n環境・サーバーの管理で登録内容を確認してから、照合するファイルを選び直してください。"
        ended_env = "選択した環境は使用終了のため、照合を停止しました。\n環境・サーバーの管理で使用状態を確認してから、環境を選び直してください。"
        ended_server = "選択したサーバーは使用終了のため、照合を停止しました。\n環境・サーバーの管理で使用状態を確認してから、サーバーを選び直してください。"
        storage = "保存先の設定を確認できないため、照合を停止しました。\n共通保存先の設定を確認してから、照合するファイルを選び直してください。"
        reason = (
            f"if(not(equals(length({filter_body}),1)),{literal(invalid)},"
            f"if(not(equals(coalesce({row}?['cr6cb_environmentenabled'],true),true)),{literal(ended_env)},"
            f"if(not(equals({row}?['cr6cb_isactive'],true)),{literal(ended_server)},{literal(storage)})))"
        )
        old_item = stop["item"]
        expected = literal("有効な転記先が一意に確認できません。")
        assert expected in old_item
        stop["item"] = old_item.replace(expected, reason, 1)
        allowed.update((condition_key, stop_key))

    # Flatten only the node's own properties: a nested child's change must not
    # be mistaken for a change to its parent. Assert MQ/Excel actions untouched.
    def own(action):
        return {k: v for k, v in action.items() if k not in ("actions", "else")}

    actual = {name for name in base_actions if own(base_actions[name]) != own(actions[name])}
    assert actual == allowed, (actual - allowed, allowed - actual)
    assert before["properties"]["definition"]["triggers"] == candidate["properties"]["definition"]["triggers"]
    assert before["properties"]["connectionReferences"] == candidate["properties"]["connectionReferences"]
    return candidate, sorted(actual)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    record = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    candidate, changes = prepare(record)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "main-candidate-clientdata.json").write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "main-workflow-patch.json").write_text(json.dumps({"clientdata": json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))}, ensure_ascii=False), encoding="utf-8")
    (args.output / "main-candidate-report.json").write_text(json.dumps({"workflowId":record["workflowid"],"baselineEtag":record["@odata.etag"],"changedActions":changes,"deployed":False},ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Local candidate prepared: {len(changes)} action properties changed; MQ/Excel actions, trigger and connections unchanged. Not deployed.")


if __name__ == "__main__":
    main()
