from router_debugger.troubleshooting.playbooks import PLAYBOOKS, list_playbooks, get_playbook

def test_playbooks_structure():
    playbooks = list_playbooks()
    assert len(playbooks) >= 5

    for pb_item in playbooks:
        pb = get_playbook(pb_item["id"])
        assert "title" in pb
        assert len(pb["symptoms"]) > 0
        assert len(pb["root_causes"]) > 0
        assert len(pb["steps"]) > 0
        for step in pb["steps"]:
            assert "step" in step
            assert "action" in step
            assert "detail" in step
