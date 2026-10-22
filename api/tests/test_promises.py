from antang_api.agents.promises import (
    CARE_PLAN_TOOL_NAME,
    promises_follow_up,
    unbacked_promise,
)


def test_detects_a_promised_check_in() -> None:
    assert promises_follow_up("好，我会在明早 8:00 主动来找你，问问昨晚睡得怎么样。")


def test_detects_shorter_phrasings() -> None:
    assert promises_follow_up("那我今晚 9 点来问你。")
    assert promises_follow_up("到时我来问候你一声。")


def test_ignores_generic_offers() -> None:
    assert not promises_follow_up("你想聊的时候随时来找我。")
    assert not promises_follow_up("你可以自己定个闹钟，八点提醒你。")


def test_flags_a_promise_without_the_plan_tool() -> None:
    reply = "好，我会在明早 8:00 主动来找你。"
    assert unbacked_promise(reply, set())
    assert unbacked_promise(reply, {"search_diabetes_knowledge"})


def test_accepts_a_promise_backed_by_the_plan_tool() -> None:
    reply = "好，我会在明早 8:00 主动来找你。"
    assert not unbacked_promise(reply, {CARE_PLAN_TOOL_NAME})


def test_ignores_replies_without_a_promise() -> None:
    assert not unbacked_promise("先把糖块放手边，十五分钟后再测一次。", set())
