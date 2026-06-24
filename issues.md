[run.sh] Running pytest suite inside api container...
============================================================== test session starts ===============================================================
platform linux -- Python 3.12.13, pytest-8.4.2, pluggy-1.6.0 -- /usr/local/bin/python
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: asyncio-0.26.0, anyio-4.14.0, langsmith-0.9.1, cov-5.0.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 221 items                                                                                                                              

tests/e2e/test_paper_loop.py::TestFullPaperLoop::test_full_paper_loop PASSED                                                               [  0%]
tests/e2e/test_paper_loop.py::TestFullPaperLoop::test_critical_event_fires_notification PASSED                                             [  0%]
tests/e2e/test_paper_loop.py::TestFullPaperLoop::test_assistant_stages_risk_increasing PASSED                                              [  1%]
tests/e2e/test_paper_loop.py::TestFullPaperLoop::test_audit_log_captures_all PASSED                                                        [  1%]
tests/integration/test_exploration_e2e.py::TestPreflight::test_sample_data_provider_active FAILED                                          [  2%]
tests/integration/test_exploration_e2e.py::TestPreflight::test_archetypes_load_without_exclusions PASSED                                   [  2%]
tests/integration/test_exploration_e2e.py::TestPreflight::test_archetype_templates_parse_after_fill PASSED                                 [  3%]
tests/integration/test_exploration_e2e.py::TestPreflight::test_scan_returns_candidates FAILED                                              [  3%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_trials_run_within_budget ERROR                                                [  4%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_ledger_populated ERROR                                                        [  4%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_ledger_has_hypothesis_family ERROR                                            [  4%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_n_configs_distinct_gt_1 ERROR                                                 [  5%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_n_configs_swept_gt_1 ERROR                                                    [  5%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_families_seen_matches_archetypes ERROR                                        [  6%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_is_sample_fallback ERROR                                                      [  6%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_instance_ledger_matches ERROR                                                 [  7%]
tests/integration/test_exploration_e2e.py::TestT2Cycle::test_n_eff_equals_trials_run ERROR                                                 [  7%]
tests/integration/test_exploration_e2e.py::TestArchetypePathRegression::test_ledger_entries_trace_to_loaded_archetypes FAILED              [  8%]
tests/integration/test_exploration_e2e.py::TestDSRClamp::test_n_eff_1_is_deliberate_clamp PASSED                                           [  8%]
tests/integration/test_exploration_e2e.py::TestDSRClamp::test_n_eff_0_is_clamped PASSED                                                    [  9%]
tests/integration/test_exploration_e2e.py::TestDSRClamp::test_n_eff_gte_2_is_finite_and_monotonic PASSED                                   [  9%]
tests/integration/test_exploration_e2e.py::TestDeflation::test_dsr_bar_rises_with_n_eff PASSED                                             [  9%]
tests/integration/test_exploration_e2e.py::TestDeflation::test_n_eff_increments_per_family_not_per_config FAILED                           [ 10%]
tests/integration/test_exploration_e2e.py::TestDeflation::test_budget_cap_pauses_exploration FAILED                                        [ 10%]
tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_zero_survivors_is_honest_suppression ERROR                          [ 11%]
tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_survivors_have_gates_version_3 ERROR                                [ 11%]
tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_survivors_registered_in_registry ERROR                              [ 12%]
tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_digest_reflects_run ERROR                                           [ 12%]
tests/integration/test_exploration_e2e.py::TestStalenessGate::test_approve_rejects_stale_report PASSED                                     [ 13%]
tests/integration/test_exploration_e2e.py::TestStalenessGate::test_approve_succeeds_with_current_gates PASSED                              [ 13%]
tests/integration/test_exploration_e2e.py::TestDeterminism::test_two_runs_produce_identical_results FAILED                                 [ 14%]
tests/integration/test_exploration_e2e.py::TestApproveDeployPath::test_discovered_strategy_through_approve_paper FAILED                    [ 14%]
tests/integration/test_exploration_e2e.py::TestSeededEdgePositiveControl::test_edge_is_genuine PASSED                                      [ 14%]
tests/integration/test_exploration_e2e.py::TestSeededEdgePositiveControl::test_min_trades_is_sole_binding_gate PASSED                      [ 15%]
tests/integration/test_exploration_e2e.py::TestSeededEdgePositiveControl::test_no_survivors_is_expected_gate_finding PASSED                [ 15%]
tests/integration/test_exploration_e2e.py::TestSeededEdgePositiveControl::test_ledger_fully_populated PASSED                               [ 16%]
tests/integration/test_exploration_e2e.py::TestSeededEdgePositiveControl::test_n_eff_accounting_correct PASSED                             [ 16%]
tests/integration/test_exploration_e2e.py::TestSeededEdgePositiveControl::test_gates_version_3_in_pipeline PASSED                          [ 17%]
tests/integration/test_exploration_e2e.py::TestNegativeControlStillZero::test_sample_data_yields_zero_survivors FAILED                     [ 17%]
tests/integration/test_exploration_e2e.py::TestDeployFromDiscovery::test_approve_paper_deploy PASSED                                       [ 18%]
tests/integration/test_exploration_e2e.py::TestSizingSchemaEnforcement::test_flat_fixed_pct_rejected PASSED                                [ 18%]
tests/integration/test_exploration_e2e.py::TestSizingSchemaEnforcement::test_canonical_nested_fixed_pct_accepted PASSED                    [ 19%]
tests/integration/test_exploration_e2e.py::TestArchetypeTemplateSizing::test_nested_fixed_pct_sizing PASSED                                [ 19%]
tests/integration/test_exploration_e2e.py::TestArchetypeTemplateSizing::test_nested_vol_scaled_sizing PASSED                               [ 19%]
tests/safety/test_safety_drills.py::TestStopLoss::test_order_without_stop_rejected PASSED                                                  [ 20%]
tests/safety/test_safety_drills.py::TestStopLoss::test_order_with_stop_allowed PASSED                                                      [ 20%]
tests/safety/test_safety_drills.py::TestPositionSizing::test_oversize_order_rejected PASSED                                                [ 21%]
tests/safety/test_safety_drills.py::TestGrossExposure::test_gross_exposure_cap_rejects PASSED                                              [ 21%]
tests/safety/test_safety_drills.py::TestPortfolioAggregate::test_per_symbol_cap_rejects PASSED                                             [ 22%]
tests/safety/test_safety_drills.py::TestPortfolioAggregate::test_max_strategies_rejects PASSED                                             [ 22%]
tests/safety/test_safety_drills.py::TestKillSwitch::test_daily_drawdown_triggers_kill PASSED                                               [ 23%]
tests/safety/test_safety_drills.py::TestKillSwitch::test_kill_switch_blocks_all_subsequent PASSED                                          [ 23%]
tests/safety/test_safety_drills.py::TestKillSwitch::test_flatten_all_on_kill PASSED                                                        [ 23%]
tests/safety/test_safety_drills.py::TestPDT::test_pdt_block_fires PASSED                                                                   [ 24%]
tests/safety/test_safety_drills.py::TestPDT::test_pdt_passes_with_sufficient_equity PASSED                                                 [ 24%]
tests/safety/test_safety_drills.py::TestMarketCalendar::test_weekend_not_trading_day PASSED                                                [ 25%]
tests/safety/test_safety_drills.py::TestMarketCalendar::test_holiday_not_trading_day PASSED                                                [ 25%]
tests/safety/test_safety_drills.py::TestMarketCalendar::test_regular_day_is_trading PASSED                                                 [ 26%]
tests/safety/test_safety_drills.py::TestMarketCalendar::test_next_trading_day_skips_weekend PASSED                                         [ 26%]
tests/safety/test_safety_drills.py::TestAllocator::test_fixed_fraction_allocation PASSED                                                   [ 27%]
tests/safety/test_safety_drills.py::TestAllocator::test_max_strategies_capped PASSED                                                       [ 27%]
tests/safety/test_safety_drills.py::TestPaperBroker::test_submit_and_positions PASSED                                                      [ 28%]
tests/safety/test_safety_drills.py::TestPaperBroker::test_reconcile PASSED                                                                 [ 28%]
tests/safety/test_safety_drills.py::TestOrderFlow::test_full_order_flow PASSED                                                             [ 28%]
tests/safety/test_safety_drills.py::TestOrderFlow::test_rejected_order_no_stop PASSED                                                      [ 29%]
tests/safety/test_safety_drills.py::TestDeploymentGate::test_live_deploy_without_validation_refused PASSED                                 [ 29%]
tests/safety/test_safety_drills.py::TestDeploymentGate::test_paper_deploy_always_allowed PASSED                                            [ 30%]
tests/safety/test_safety_drills.py::TestDeploymentGate::test_live_deploy_with_approval_succeeds PASSED                                     [ 30%]
tests/safety/test_safety_drills.py::TestHaltDetection::test_halted_symbol_rejected PASSED                                                  [ 31%]
tests/safety/test_safety_drills.py::TestHaltDetection::test_resumed_symbol_allowed PASSED                                                  [ 31%]
tests/safety/test_safety_drills.py::TestHaltDetection::test_non_halted_symbol_unaffected PASSED                                            [ 32%]
tests/safety/test_safety_drills.py::TestLockbox::test_lockbox_enforced PASSED                                                              [ 32%]
tests/safety/test_safety_drills.py::TestLockbox::test_lockbox_split_covers_all_bars PASSED                                                 [ 33%]
tests/safety/test_safety_drills.py::TestEODFlatten::test_eod_flatten_fires_before_close PASSED                                             [ 33%]
tests/safety/test_safety_drills.py::TestEODFlatten::test_eod_flatten_skips_outside_window PASSED                                           [ 33%]
tests/safety/test_safety_drills.py::TestBracketOrders::test_bracket_stop_created_on_submit PASSED                                          [ 34%]
tests/safety/test_safety_drills.py::TestBracketOrders::test_bracket_stop_triggers PASSED                                                   [ 34%]
tests/safety/test_safety_drills.py::TestBracketOrders::test_bracket_survives_heartbeat_loss PASSED                                         [ 35%]
tests/safety/test_safety_drills.py::TestBracketOrders::test_bracket_tp_triggers PASSED                                                     [ 35%]
tests/unit/test_auth.py::TestPasswordHashing::test_hash_and_verify PASSED                                                                  [ 36%]
tests/unit/test_auth.py::TestPasswordHashing::test_wrong_password_fails PASSED                                                             [ 36%]
tests/unit/test_auth.py::TestPasswordHashing::test_different_hashes_for_same_password PASSED                                               [ 37%]
tests/unit/test_auth.py::TestTokenHashing::test_hash_is_deterministic PASSED                                                               [ 37%]
tests/unit/test_auth.py::TestTokenHashing::test_different_tokens_different_hashes PASSED                                                   [ 38%]
tests/unit/test_auth_api.py::test_setup_status_unconfigured PASSED                                                                         [ 38%]
tests/unit/test_auth_api.py::test_register_first_user PASSED                                                                               [ 38%]
tests/unit/test_auth_api.py::test_register_second_user_blocked PASSED                                                                      [ 39%]
tests/unit/test_auth_api.py::test_login_success PASSED                                                                                     [ 39%]
tests/unit/test_auth_api.py::test_login_wrong_password PASSED                                                                              [ 40%]
tests/unit/test_auth_api.py::test_me_authenticated PASSED                                                                                  [ 40%]
tests/unit/test_auth_api.py::test_me_unauthenticated PASSED                                                                                [ 41%]
tests/unit/test_auth_api.py::test_protected_route_401_without_session PASSED                                                               [ 41%]
tests/unit/test_auth_api.py::test_portfolio_401_without_session PASSED                                                                     [ 42%]
tests/unit/test_auth_api.py::test_setup_status_after_registration PASSED                                                                   [ 42%]
tests/unit/test_auth_api.py::test_no_secret_in_user_response PASSED                                                                        [ 42%]
tests/unit/test_auth_api.py::test_change_password PASSED                                                                                   [ 43%]
tests/unit/test_auth_api.py::test_change_password_wrong_old PASSED                                                                         [ 43%]
tests/unit/test_dsl_parser.py::test_parse_valid_spec PASSED                                                                                [ 44%]
tests/unit/test_dsl_parser.py::test_parse_missing_thesis PASSED                                                                            [ 44%]
tests/unit/test_dsl_parser.py::test_parse_missing_stop_loss PASSED                                                                         [ 45%]
tests/unit/test_dsl_parser.py::test_parse_empty_regime PASSED                                                                              [ 45%]
tests/unit/test_health.py::test_health_endpoint PASSED                                                                                     [ 46%]
tests/unit/test_library_loader.py::TestLibraryLoader::test_all_archetypes_load PASSED                                                      [ 46%]
tests/unit/test_library_loader.py::TestLibraryLoader::test_all_archetypes_have_required_fields PASSED                                      [ 47%]
tests/unit/test_library_loader.py::TestLibraryLoader::test_all_templates_pass_dsl_parser PASSED                                            [ 47%]
tests/unit/test_library_loader.py::TestLibraryLoader::test_all_families_represented PASSED                                                 [ 47%]
tests/unit/test_library_loader.py::TestLibraryLoader::test_stop_loss_required_in_every_template PASSED                                     [ 48%]
tests/unit/test_library_loader.py::TestLibraryLoader::test_regime_non_empty_in_every_template PASSED                                       [ 48%]
tests/unit/test_library_loader.py::TestLibraryLoader::test_risk_within_guardrails PASSED                                                   [ 49%]
tests/unit/test_library_loader.py::TestParamBindings::test_all_param_bindings_valid PASSED                                                 [ 49%]
tests/unit/test_library_loader.py::TestParamBindings::test_all_variants_distinct PASSED                                                    [ 50%]
tests/unit/test_library_loader.py::TestParamBindings::test_all_filled_templates_pass_dsl PASSED                                            [ 50%]
tests/unit/test_library_loader.py::TestParamBindings::test_malformed_archetype_excluded PASSED                                             [ 51%]
tests/unit/test_library_loader.py::TestParamBindings::test_missing_default_excluded PASSED                                                 [ 51%]
tests/unit/test_library_loader.py::TestParamBindings::test_int_period_no_float_leak PASSED                                                 [ 52%]
tests/unit/test_library_loader.py::TestParamBindings::test_fractional_params_never_truncated PASSED                                        [ 52%]
tests/unit/test_m2_gate.py::test_backtest_hand_written_spec PASSED                                                                         [ 52%]
tests/unit/test_m2_gate.py::test_interpreter_produces_valid_signals PASSED                                                                 [ 53%]
tests/unit/test_m2_gate.py::test_frictionless_vs_net_edge_reported PASSED                                                                  [ 53%]
tests/unit/test_m2_gate.py::test_cost_model_reduces_edge PASSED                                                                            [ 54%]
tests/unit/test_m2_gate.py::test_lookahead_guard_detects_future_bars PASSED                                                                [ 54%]
tests/unit/test_m2_gate.py::test_lookahead_guard_passes_clean_bars PASSED                                                                  [ 55%]
tests/unit/test_m2_gate.py::test_provider_enforces_point_in_time PASSED                                                                    [ 55%]
tests/unit/test_m2_gate.py::test_universe_survivorship_free PASSED                                                                         [ 56%]
tests/unit/test_m2_gate.py::test_sma_correctness PASSED                                                                                    [ 56%]
tests/unit/test_m2_gate.py::test_rsi_bounded PASSED                                                                                        [ 57%]
tests/unit/test_m2_gate.py::test_backtest_deterministic PASSED                                                                             [ 57%]
tests/unit/test_m4_gate.py::test_valid_spec_passes PASSED                                                                                  [ 57%]
tests/unit/test_m4_gate.py::test_unknown_top_level_field_rejected PASSED                                                                   [ 58%]
tests/unit/test_m4_gate.py::test_missing_thesis_rejected PASSED                                                                            [ 58%]
tests/unit/test_m4_gate.py::test_empty_thesis_rejected PASSED                                                                              [ 59%]
tests/unit/test_m4_gate.py::test_empty_regime_rejected PASSED                                                                              [ 59%]
tests/unit/test_m4_gate.py::test_missing_stop_loss_rejected PASSED                                                                         [ 60%]
tests/unit/test_m4_gate.py::test_unknown_condition_operator_rejected PASSED                                                                [ 60%]
tests/unit/test_m4_gate.py::test_unknown_action_rejected PASSED                                                                            [ 61%]
tests/unit/test_m4_gate.py::test_risk_exceeding_guardrails_rejected PASSED                                                                 [ 61%]
tests/unit/test_m4_gate.py::test_risk_stop_pct_exceeding_guardrails_rejected PASSED                                                        [ 61%]
tests/unit/test_m4_gate.py::test_risk_gross_exposure_exceeding_guardrails_rejected PASSED                                                  [ 62%]
tests/unit/test_m4_gate.py::test_unknown_exit_type_rejected PASSED                                                                         [ 62%]
tests/unit/test_m4_gate.py::test_unknown_primitive_rejected PASSED                                                                         [ 63%]
tests/unit/test_m4_gate.py::test_primitive_wrong_arity_rejected PASSED                                                                     [ 63%]
tests/unit/test_m4_gate.py::test_primitive_param_out_of_range_rejected PASSED                                                              [ 64%]
tests/unit/test_m4_gate.py::test_primitive_param_above_max_rejected PASSED                                                                 [ 64%]
tests/unit/test_m4_gate.py::test_record_field_access_valid PASSED                                                                          [ 65%]
tests/unit/test_m4_gate.py::test_record_field_access_invalid_field PASSED                                                                  [ 65%]
tests/unit/test_m4_gate.py::test_condition_gt_wrong_arg_count PASSED                                                                       [ 66%]
tests/unit/test_m4_gate.py::test_condition_between_wrong_arg_count PASSED                                                                  [ 66%]
tests/unit/test_m4_gate.py::test_unknown_entry_field_rejected PASSED                                                                       [ 66%]
tests/unit/test_m4_gate.py::test_unknown_sizing_method_rejected PASSED                                                                     [ 67%]
tests/unit/test_m4_gate.py::test_multiple_errors_collected PASSED                                                                          [ 67%]
tests/unit/test_m4_gate.py::test_held_for_condition_validated PASSED                                                                       [ 68%]
tests/unit/test_m4_gate.py::test_held_for_wrong_arity PASSED                                                                               [ 68%]
tests/unit/test_m4_gate.py::test_all_of_requires_list PASSED                                                                               [ 69%]
tests/unit/test_m4_gate.py::test_risk_at_guardrail_boundary_passes PASSED                                                                  [ 69%]
tests/unit/test_m4_gate.py::test_valid_spec_runs_through_backtest PASSED                                                                   [ 70%]
tests/unit/test_m6_gate.py::test_all_tools_registered PASSED                                                                               [ 70%]
tests/unit/test_m6_gate.py::test_agent_cannot_access_risk_increasing PASSED                                                                [ 71%]
tests/unit/test_m6_gate.py::test_agent_has_read_tools PASSED                                                                               [ 71%]
tests/unit/test_m6_gate.py::test_agent_has_risk_reducing_tools PASSED                                                                      [ 71%]
tests/unit/test_m6_gate.py::test_deploy_and_approve_are_risk_increasing PASSED                                                             [ 72%]
tests/unit/test_m6_gate.py::test_author_strategy_produces_spec PASSED                                                                      [ 72%]
tests/unit/test_m6_gate.py::test_red_team_finds_concerns PASSED                                                                            [ 73%]
tests/unit/test_m6_gate.py::test_domain_scan_returns_candidates PASSED                                                                     [ 73%]
tests/unit/test_m6_gate.py::test_author_tool_produces_ticker_specific_specs PASSED                                                         [ 74%]
tests/unit/test_m6_gate.py::test_author_tool_rejects_bad_spec PASSED                                                                       [ 74%]
tests/unit/test_m6_gate.py::test_author_tool_flags_fallback_template PASSED                                                                [ 75%]
tests/unit/test_m6_gate.py::test_author_tool_requires_thesis PASSED                                                                        [ 75%]
tests/unit/test_m6_gate.py::test_backtest_tool_works FAILED                                                                                [ 76%]
tests/unit/test_m6_gate.py::test_peer_test_tool_registered PASSED                                                                          [ 76%]
tests/unit/test_m6_gate.py::test_peer_test_generalizing_strategy PASSED                                                                    [ 76%]
tests/unit/test_m6_gate.py::test_peer_test_insufficient_data_fails_closed PASSED                                                           [ 77%]
tests/unit/test_m6_gate.py::test_peer_test_primary_no_data_fails PASSED                                                                    [ 77%]
tests/unit/test_m6_gate.py::test_harness_includes_peer_hit_gate PASSED                                                                     [ 78%]
tests/unit/test_m6_gate.py::test_harness_no_peers_fails_closed PASSED                                                                      [ 78%]
tests/unit/test_m6_gate.py::test_stale_report_invalidation PASSED                                                                          [ 79%]
tests/unit/test_m8_gate.py::test_tier1_runs PASSED                                                                                         [ 79%]
tests/unit/test_m8_gate.py::test_tier2_respects_budget PASSED                                                                              [ 80%]
tests/unit/test_m8_gate.py::test_tier3_requires_human_approval PASSED                                                                      [ 80%]
tests/unit/test_m8_gate.py::test_tier3_human_can_decide PASSED                                                                             [ 80%]
tests/unit/test_m8_gate.py::test_tier2_sweeps_param_grid PASSED                                                                            [ 81%]
tests/unit/test_m8_gate.py::test_param_grid_fallback_stop_loss PASSED                                                                      [ 81%]
tests/unit/test_m8_gate.py::test_archetype_grid_varies_entry_params PASSED                                                                 [ 82%]
tests/unit/test_m8_gate.py::test_archetype_grid_caps_combinatorial_blowup PASSED                                                           [ 82%]
tests/unit/test_m8_gate.py::test_dedup_before_cap_even_spread PASSED                                                                       [ 83%]
tests/unit/test_m8_gate.py::test_collapse_to_single_distinct PASSED                                                                        [ 83%]
tests/unit/test_m8_gate.py::test_base_spec_counted_exactly_once PASSED                                                                     [ 84%]
tests/unit/test_m8_gate.py::test_fallback_single_variant_returns_one PASSED                                                                [ 84%]
tests/unit/test_m8_gate.py::test_nothing_self_deploys PASSED                                                                               [ 85%]
tests/unit/test_m8_gate.py::test_digest PASSED                                                                                             [ 85%]
tests/unit/test_m8_gate.py::TestMonitoring::test_record_and_check_decay PASSED                                                             [ 85%]
tests/unit/test_m8_gate.py::TestMonitoring::test_no_decay_with_stable_performance PASSED                                                   [ 86%]
tests/unit/test_m8_gate.py::TestAuditLog::test_log_and_query PASSED                                                                        [ 86%]
tests/unit/test_m8_gate.py::TestAuditLog::test_audit_log_immutable PASSED                                                                  [ 87%]
tests/unit/test_m8_gate.py::TestCalibration::test_calibration_recording PASSED                                                             [ 87%]
tests/unit/test_secrets.py::TestRedactForClient::test_strips_secret_key PASSED                                                             [ 88%]
tests/unit/test_secrets.py::TestRedactForClient::test_strips_broker_keys PASSED                                                            [ 88%]
tests/unit/test_secrets.py::TestRedactForClient::test_masks_key_like_fields PASSED                                                         [ 89%]
tests/unit/test_secrets.py::TestRedactForClient::test_recursive_redaction PASSED                                                           [ 89%]
tests/unit/test_secrets.py::TestRedactForClient::test_empty_key_shows_empty PASSED                                                         [ 90%]
tests/unit/test_secrets.py::TestRedactForClient::test_no_secret_fields_passes_through PASSED                                               [ 90%]
tests/unit/test_secrets.py::TestMaskConnectionValue::test_masks_long_value PASSED                                                          [ 90%]
tests/unit/test_secrets.py::TestMaskConnectionValue::test_masks_short_value PASSED                                                         [ 91%]
tests/unit/test_secrets.py::TestMaskConnectionValue::test_masks_empty PASSED                                                               [ 91%]
tests/unit/test_tool_registry.py::test_register_and_get PASSED                                                                             [ 92%]
tests/unit/test_tool_registry.py::test_list_by_permission PASSED                                                                           [ 92%]
tests/unit/test_tool_registry.py::test_agent_cannot_access_risk_increasing PASSED                                                          [ 93%]
tests/unit/test_tool_registry.py::test_deregister PASSED                                                                                   [ 93%]
tests/validation_suite/test_verification.py::TestPBO::test_pbo_on_noise_approx_half PASSED                                                 [ 94%]
tests/validation_suite/test_verification.py::TestPBO::test_pbo_on_seeded_edge_low PASSED                                                   [ 94%]
tests/validation_suite/test_verification.py::TestPBO::test_pbo_single_config_returns_none PASSED                                           [ 95%]
tests/validation_suite/test_verification.py::TestPBO::test_pbo_1d_input_returns_none PASSED                                                [ 95%]
tests/validation_suite/test_verification.py::TestDSR::test_dsr_monotonic_in_n_eff PASSED                                                   [ 95%]
tests/validation_suite/test_verification.py::TestDSR::test_dsr_skew_penalty PASSED                                                         [ 96%]
tests/validation_suite/test_verification.py::TestDSR::test_psr_computation PASSED                                                          [ 96%]
tests/validation_suite/test_verification.py::TestDSR::test_expected_max_sharpe_increases_with_trials PASSED                                [ 97%]
tests/validation_suite/test_verification.py::TestWalkForward::test_walk_forward_produces_oos_folds PASSED                                  [ 97%]
tests/validation_suite/test_verification.py::TestPBOGateIntegration::test_overfit_sweep_rejected_by_pbo_gate PASSED                        [ 98%]
tests/validation_suite/test_verification.py::TestPBOGateIntegration::test_entry_param_overfit_rejected PASSED                              [ 98%]
tests/validation_suite/test_verification.py::TestPBOGateIntegration::test_robust_entry_param_passes PASSED                                 [ 99%]
tests/validation_suite/test_verification.py::TestEndToEnd::test_known_good_spec PASSED                                                     [ 99%]
tests/validation_suite/test_verification.py::TestEndToEnd::test_confidence_metric_sanity PASSED                                            [100%]

===================================================================== ERRORS =====================================================================
__________________________________________ ERROR at setup of TestT2Cycle.test_trials_run_within_budget ___________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:288: in grouped_daily
    resp.raise_for_status()
/usr/local/lib/python3.12/site-packages/httpx/_models.py:829: in raise_for_status
    raise HTTPStatusError(message, request=request, response=self)
E   httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjusted=true&apiKey=8jCRV_Ak3Q75HRlYIJupcozYGJqedYFu'
E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
______________________________________________ ERROR at setup of TestT2Cycle.test_ledger_populated _______________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:288: in grouped_daily
    resp.raise_for_status()
/usr/local/lib/python3.12/site-packages/httpx/_models.py:829: in raise_for_status
    raise HTTPStatusError(message, request=request, response=self)
E   httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjusted=true&apiKey=8jCRV_Ak3Q75HRlYIJupcozYGJqedYFu'
E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
________________________________________ ERROR at setup of TestT2Cycle.test_ledger_has_hypothesis_family _________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:288: in grouped_daily
    resp.raise_for_status()
/usr/local/lib/python3.12/site-packages/httpx/_models.py:829: in raise_for_status
    raise HTTPStatusError(message, request=request, response=self)
E   httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjusted=true&apiKey=8jCRV_Ak3Q75HRlYIJupcozYGJqedYFu'
E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
___________________________________________ ERROR at setup of TestT2Cycle.test_n_configs_distinct_gt_1 ___________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
____________________________________________ ERROR at setup of TestT2Cycle.test_n_configs_swept_gt_1 _____________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
______________________________________ ERROR at setup of TestT2Cycle.test_families_seen_matches_archetypes _______________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
_____________________________________________ ERROR at setup of TestT2Cycle.test_is_sample_fallback ______________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
___________________________________________ ERROR at setup of TestT2Cycle.test_instance_ledger_matches ___________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
___________________________________________ ERROR at setup of TestT2Cycle.test_n_eff_equals_trials_run ___________________________________________
tests/integration/test_exploration_e2e.py:201: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
_______________________________ ERROR at setup of TestSurvivorSurfacing.test_zero_survivors_is_honest_suppression ________________________________
tests/integration/test_exploration_e2e.py:366: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
__________________________________ ERROR at setup of TestSurvivorSurfacing.test_survivors_have_gates_version_3 ___________________________________
tests/integration/test_exploration_e2e.py:366: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
_________________________________ ERROR at setup of TestSurvivorSurfacing.test_survivors_registered_in_registry __________________________________
tests/integration/test_exploration_e2e.py:366: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
________________________________________ ERROR at setup of TestSurvivorSurfacing.test_digest_reflects_run ________________________________________
tests/integration/test_exploration_e2e.py:366: in run_cycle
    self.result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
==================================================================== FAILURES ====================================================================
_________________________________________________ TestPreflight.test_sample_data_provider_active _________________________________________________
tests/integration/test_exploration_e2e.py:162: in test_sample_data_provider_active
    assert isinstance(provider, SampleDataProvider)
E   assert False
E    +  where False = isinstance(<app.modules.data.providers.PolygonDataProvider object at 0xffff64fdda60>, SampleDataProvider)
___________________________________________________ TestPreflight.test_scan_returns_candidates ___________________________________________________
tests/integration/test_exploration_e2e.py:188: in test_scan_returns_candidates
    result = await scan_universe(a, as_of=AS_OF)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:288: in grouped_daily
    resp.raise_for_status()
/usr/local/lib/python3.12/site-packages/httpx/_models.py:829: in raise_for_status
    raise HTTPStatusError(message, request=request, response=self)
E   httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjusted=true&apiKey=8jCRV_Ak3Q75HRlYIJupcozYGJqedYFu'
E   For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
___________________________________ TestArchetypePathRegression.test_ledger_entries_trace_to_loaded_archetypes ___________________________________
tests/integration/test_exploration_e2e.py:266: in test_ledger_entries_trace_to_loaded_archetypes
    result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
_________________________________________ TestDeflation.test_n_eff_increments_per_family_not_per_config __________________________________________
tests/integration/test_exploration_e2e.py:331: in test_n_eff_increments_per_family_not_per_config
    result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
________________________________________________ TestDeflation.test_budget_cap_pauses_exploration ________________________________________________
tests/integration/test_exploration_e2e.py:349: in test_budget_cap_pauses_exploration
    result = await evolution.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
____________________________________________ TestDeterminism.test_two_runs_produce_identical_results _____________________________________________
tests/integration/test_exploration_e2e.py:518: in test_two_runs_produce_identical_results
    r1 = await evo1.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
______________________________________ TestApproveDeployPath.test_discovered_strategy_through_approve_paper ______________________________________
tests/integration/test_exploration_e2e.py:563: in test_discovered_strategy_through_approve_paper
    result = await evo.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
______________________________________ TestNegativeControlStillZero.test_sample_data_yields_zero_survivors _______________________________________
tests/integration/test_exploration_e2e.py:726: in test_sample_data_yields_zero_survivors
    result = await evo.run_tier2(
app/modules/evolution/service.py:312: in run_tier2
    scan_result = await scan_universe(archetype, as_of=as_of_dt)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:440: in scan_universe
    tickers = await provider.filtered_universe(
app/modules/data/providers.py:323: in filtered_universe
    rows = await self.grouped_daily(d)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:287: in grouped_daily
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
____________________________________________________________ test_backtest_tool_works ____________________________________________________________
tests/unit/test_m6_gate.py:211: in test_backtest_tool_works
    result = await tool.invoke({"spec": spec}, ctx)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/core/tools/catalog.py:180: in invoke
    bars = await provider.bars(ticker, start, end)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/modules/data/providers.py:232: in bars
    raise RuntimeError("Polygon rate limit exceeded — retry later or upgrade plan")
E   RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
============================================================ short test summary info =============================================================
FAILED tests/integration/test_exploration_e2e.py::TestPreflight::test_sample_data_provider_active - assert False
FAILED tests/integration/test_exploration_e2e.py::TestPreflight::test_scan_returns_candidates - httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjust...
FAILED tests/integration/test_exploration_e2e.py::TestArchetypePathRegression::test_ledger_entries_trace_to_loaded_archetypes - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/integration/test_exploration_e2e.py::TestDeflation::test_n_eff_increments_per_family_not_per_config - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/integration/test_exploration_e2e.py::TestDeflation::test_budget_cap_pauses_exploration - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/integration/test_exploration_e2e.py::TestDeterminism::test_two_runs_produce_identical_results - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/integration/test_exploration_e2e.py::TestApproveDeployPath::test_discovered_strategy_through_approve_paper - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/integration/test_exploration_e2e.py::TestNegativeControlStillZero::test_sample_data_yields_zero_survivors - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
FAILED tests/unit/test_m6_gate.py::test_backtest_tool_works - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_trials_run_within_budget - httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjust...
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_ledger_populated - httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjust...
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_ledger_has_hypothesis_family - httpx.HTTPStatusError: Client error '403 Forbidden' for url 'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2024-05-06?adjust...
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_n_configs_distinct_gt_1 - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_n_configs_swept_gt_1 - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_families_seen_matches_archetypes - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_is_sample_fallback - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_instance_ledger_matches - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestT2Cycle::test_n_eff_equals_trials_run - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_zero_survivors_is_honest_suppression - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_survivors_have_gates_version_3 - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_survivors_registered_in_registry - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
ERROR tests/integration/test_exploration_e2e.py::TestSurvivorSurfacing::test_digest_reflects_run - RuntimeError: Polygon rate limit exceeded — retry later or upgrade plan
=================================================== 9 failed, 199 passed, 13 errors in 28.81s ================================================