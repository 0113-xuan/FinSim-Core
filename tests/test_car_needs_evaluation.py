from scripts.evaluate_car_needs_live import compare, expected_conflict, summarize


def test_live_eval_distinguishes_semantics_and_uncertainty():
    c = dict(field='priorities',operation='add',value='comfort',evidence='舒服')
    e = dict(candidates=[c],unclear=[])
    assert compare(e,e)['category'] == '正確'
    assert compare(e,dict(candidates=[],unclear=[]))['category'] == '漏判'
    assert compare(dict(candidates=[],unclear=[]),e)['category'] == '誤判'
    assert compare(e,dict(candidates=[dict(c,value='space')],unclear=[]))['category'] == '誤判及漏判'
    assert compare(e,dict(candidates=[c],unclear=[dict(reason='uncertain')]))['category'] == '無法確認'
    assert expected_conflict(dict(c,operation='remove'))
    assert not expected_conflict(c)


def test_live_summary_does_not_treat_timeouts_as_semantic_passes():
    rows=[dict(category='正確',raw_comparison=dict(category='正確'),latency_seconds=2,format_valid=True,
        http_statuses=[200],model_versions=['gemini-3.5-flash-lite'],usage=[dict(promptTokenCount=100,candidatesTokenCount=10)])]
    rows.append(dict(category='服務失敗',error_type='timeout',latency_seconds=20,format_valid=False,http_statuses=[],model_versions=[],usage=[]))
    result=summarize(rows)
    assert result['total']==2 and result['categories']['正確']==1
    assert result['timeouts']==1 and result['format_failures']==0
    assert result['observed_prompt_tokens']==100
    assert result['observed_token_cost_usd_estimate']==.000055
