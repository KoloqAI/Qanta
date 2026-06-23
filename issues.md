tests/unit/test_m6_gate.py::test_peer_test_generalizing_strategy FAILED                                                       [ 76%]
tests/unit/test_m6_gate.py::test_peer_test_insufficient_data_fails_closed PASSED                                              [ 77%]
tests/unit/test_m6_gate.py::test_peer_test_primary_no_data_fails PASSED                                                       [ 77%]
tests/unit/test_m6_gate.py::test_harness_includes_peer_hit_gate PASSED                                                        [ 78%]
tests/unit/test_m6_gate.py::test_harness_no_peers_fails_closed PASSED                                                         [ 78%]
tests/unit/test_m6_gate.py::test_stale_report_invalidation PASSED                                                             [ 79%]
tests/unit/test_m8_gate.py::test_tier1_runs PASSED                                                                            [ 80%]
tests/unit/test_m8_gate.py::test_tier2_respects_budget FAILED                                                                 [ 80%]
tests/unit/test_m8_gate.py::test_tier3_requires_human_approval PASSED                                                         [ 81%]
tests/unit/test_m8_gate.py::test_tier3_human_can_decide PASSED                                                                [ 81%]
tests/unit/test_m8_gate.py::test_nothing_self_deploys FAILED                                                                  [ 82%]
tests/unit/test_m8_gate.py::test_digest PASSED                                                                                [ 83%]
tests/unit/test_m8_gate.py::TestMonitoring::test_record_and_check_decay PASSED                                                [ 83%]
tests/unit/test_m8_gate.py::TestMonitoring::test_no_decay_with_stable_performance PASSED                                      [ 84%]
tests/unit/test_m8_gate.py::TestAuditLog::test_log_and_query PASSED                                                           [ 85%]
tests/unit/test_m8_gate.py::TestAuditLog::test_audit_log_immutable PASSED                                                     [ 85%]
tests/unit/test_m8_gate.py::TestCalibration::test_calibration_recording PASSED                                                [ 86%]
tests/unit/test_secrets.py::TestRedactForClient::test_strips_secret_key PASSED                                                [ 86%]
tests/unit/test_secrets.py::TestRedactForClient::test_strips_broker_keys PASSED                                               [ 87%]
tests/unit/test_secrets.py::TestRedactForClient::test_masks_key_like_fields PASSED                                            [ 88%]
tests/unit/test_secrets.py::TestRedactForClient::test_recursive_redaction PASSED                                              [ 88%]
tests/unit/test_secrets.py::TestRedactForClient::test_empty_key_shows_empty PASSED                                            [ 89%]
tests/unit/test_secrets.py::TestRedactForClient::test_no_secret_fields_passes_through PASSED                                  [ 90%]
tests/unit/test_secrets.py::TestMaskConnectionValue::test_masks_long_value PASSED                                             [ 90%]
tests/unit/test_secrets.py::TestMaskConnectionValue::test_masks_short_value PASSED                                            [ 91%]
tests/unit/test_secrets.py::TestMaskConnectionValue::test_masks_empty PASSED                                                  [ 91%]
tests/unit/test_tool_registry.py::test_register_and_get PASSED                                                                [ 92%]
tests/unit/test_tool_registry.py::test_list_by_permission PASSED                                                              [ 93%]
tests/unit/test_tool_registry.py::test_agent_cannot_access_risk_increasing PASSED                                             [ 93%]
tests/unit/test_tool_registry.py::test_deregister PASSED                                                                      [ 94%]
tests/validation_suite/test_verification.py::TestPBO::test_pbo_on_noise_approx_half FAILED                                    [ 95%]
tests/validation_suite/test_verification.py::TestPBO::test_pbo_on_seeded_edge_low FAILED                                      [ 95%]
tests/validation_suite/test_verification.py::TestDSR::test_dsr_monotonic_in_n_eff PASSED                                      [ 96%]
tests/validation_suite/test_verification.py::TestDSR::test_dsr_skew_penalty PASSED                                            [ 96%]
tests/validation_suite/test_verification.py::TestDSR::test_psr_computation PASSED                                             [ 97%]
tests/validation_suite/test_verification.py::TestDSR::test_expected_max_sharpe_increases_with_trials PASSED                   [ 98%]
tests/validation_suite/test_verification.py::TestWalkForward::test_walk_forward_produces_oos_folds PASSED                     [ 98%]
tests/validation_suite/test_verification.py::TestEndToEnd::test_known_good_spec PASSED                                        [ 99%]
tests/validation_suite/test_verification.py::TestEndToEnd::test_confidence_metric_sanity PASSED                               [100%]

============================================================= FAILURES ==============================================================
_______________________________________________ test_peer_test_generalizing_strategy ________________________________________________
tests/unit/test_m6_gate.py:248: in test_peer_test_generalizing_strategy
    result = await tool.invoke({"spec": _PEER_TEST_SPEC}, ctx)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/core/tools/catalog.py:299: in invoke
    candidates = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
____________________________________________________ test_tier2_respects_budget _____________________________________________________
tests/unit/test_m8_gate.py:25: in test_tier2_respects_budget
    result = await loop.run_tier2(budget=5)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/evolution/service.py:192: in run_tier2
    bars = await provider.bars(ticker, val_start, val_end)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:232: in bars
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
_____________________________________________________ test_nothing_self_deploys _____________________________________________________
tests/unit/test_m8_gate.py:53: in test_nothing_self_deploys
    t2 = await loop.run_tier2(budget=10)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/evolution/service.py:192: in run_tier2
    bars = await provider.bars(ticker, val_start, val_end)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:232: in bars
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
_______________________________________________ TestPBO.test_pbo_on_noise_approx_half _______________________________________________
tests/validation_suite/test_verification.py:38: in test_pbo_on_noise_approx_half
    assert 0.3 <= result["pbo"] <= 0.7, f"PBO on noise = {result['pbo']}, expected ~0.5"
E   AssertionError: PBO on noise = 1.0, expected ~0.5
E   assert 1.0 <= 0.7
________________________________________________ TestPBO.test_pbo_on_seeded_edge_low ________________________________________________
tests/validation_suite/test_verification.py:45: in test_pbo_on_seeded_edge_low
    assert result["pbo"] <= 0.5, f"PBO on seeded edge = {result['pbo']}, expected low"
E   AssertionError: PBO on seeded edge = 1.0, expected low
E   assert 1.0 <= 0.5
====================================================== short test summary info ======================================================
FAILED tests/unit/test_m6_gate.py::test_peer_test_generalizing_strategy - RuntimeError: Polygon rate limit exceeded — retry later orupgrade plan
FAILED tests/unit/test_m8_gate.py::test_tier2_respects_budget - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/unit/test_m8_gate.py::test_nothing_self_deploys - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/validation_suite/test_verification.py::TestPBO::test_pbo_on_noise_approx_half - AssertionError: PBO on noise = 1.0, expected ~0.5
FAILED tests/validation_suite/test_verification.py::TestPBO::test_pbo_on_seeded_edge_low - AssertionError: PBO on seeded edge = 1.0,expected low
================================================== 5 failed, 156 passed in 51.23s ===================================================
(base) vipulkaushik@Vipuls-Macbook Qanta % 