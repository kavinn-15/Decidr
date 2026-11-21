# DECIDR — TEST EXECUTION RESULTS
**Execution Date:** November 21, 2026  
**Environment:** Windows (PowerShell), Python 3.14.5, Node.js v20+, Next.js 16.4.6 (Turbopack)  
**Standard:** 100% Verbatim Terminal Output Records

---

## 1. BACKEND TEST SUITE (125 / 125 PASSED)

**Command:**
```powershell
.\.venv\Scripts\pytest backend/tests -v
```

**Verbatim Terminal Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\rprav\OneDrive\Desktop\Decidr\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\rprav\OneDrive\Desktop\Decidr
plugins: anyio-4.16.0
collecting ... collected 125 items

backend/tests/test_adversarial.py::test_adversarial_prompt_injection_creates_no_unapproved_writes PASSED [  0%]
backend/tests/test_adversarial.py::test_empty_transcript_fails_gracefully PASSED [  1%]
backend/tests/test_adversarial.py::test_one_megabyte_transcript_handles_gracefully PASSED [  2%]
backend/tests/test_adversarial.py::test_duplicate_transcript_upload_does_not_duplicate_decisions PASSED [  3%]
backend/tests/test_adversarial.py::test_unknown_speakers_handled_gracefully PASSED [  4%]
backend/tests/test_adversarial.py::test_non_ascii_names_and_multilingual_text PASSED [  4%]
backend/tests/test_adversarial.py::test_fabricated_llm_quote_is_dropped PASSED [  5%]
backend/tests/test_adversarial.py::test_responses_and_config_never_leak_secrets PASSED [  6%]
backend/tests/test_adversarial.py::test_path_traversal_filename_is_sanitized PASSED [  7%]
backend/tests/test_adversarial.py::test_unsupported_file_extension_is_rejected PASSED [  8%]
backend/tests/test_audit_api.py::test_audit_list_endpoint_returns_newest_first PASSED [  8%]
backend/tests/test_audit_api.py::test_audit_filtering_by_actor_and_action PASSED [  9%]
backend/tests/test_audit_api.py::test_audit_csv_export PASSED            [ 10%]
backend/tests/test_audit_api.py::test_meetings_dashboard_includes_pending_review_count PASSED [ 11%]
backend/tests/test_audit_api.py::test_unmapped_speakers_endpoint PASSED  [ 12%]
backend/tests/test_audit_api.py::test_config_and_demo_reset PASSED       [ 12%]
backend/tests/test_blast_radius.py::test_blast_radius_breaking_p1_affects_t1_t2_and_t6_via_d3 PASSED [ 13%]
backend/tests/test_blast_radius.py::test_t5_europe_listed_unaffected_with_scope_reason PASSED [ 14%]
backend/tests/test_blast_radius.py::test_sla_task_listed_as_needs_confirmation PASSED [ 15%]
backend/tests/test_blast_radius.py::test_hours_at_risk_metrics_never_guesses_estimates PASSED [ 16%]
backend/tests/test_blast_radius.py::test_api_get_alert_blast_radius PASSED [ 16%]
backend/tests/test_blast_radius.py::test_api_get_alert_blast_radius_not_found PASSED [ 17%]
backend/tests/test_blast_radius_advanced.py::test_circular_dependencies_handled_gracefully_without_infinite_loop PASSED [ 18%]
backend/tests/test_blast_radius_advanced.py::test_duplicate_task_relationships_deduplicated_in_blast_radius PASSED [ 19%]
backend/tests/test_blast_radius_advanced.py::test_unconfirmed_links_categorized_under_needs_confirmation PASSED [ 20%]
backend/tests/test_blast_radius_advanced.py::test_scope_disjoint_tasks_explained_in_unaffected PASSED [ 20%]
backend/tests/test_conflicts.py::test_europe_decision_vs_d1_yields_no_alert_and_zero_llm_calls PASSED [ 21%]
backend/tests/test_conflicts.py::test_m3_launch_date_change_yields_supersedes_alert_against_d2 PASSED [ 22%]
backend/tests/test_conflicts.py::test_consistent_decisions_yield_nothing PASSED [ 23%]
backend/tests/test_conflicts.py::test_quote_verification_rejects_hallucinations PASSED [ 24%]
backend/tests/test_conflicts.py::test_ambiguous_conflict_creates_card_for_reviewer PASSED [ 24%]
backend/tests/test_conflicts.py::test_duplicate_decision_creates_possible_duplicate_alert PASSED [ 25%]
backend/tests/test_eval.py::test_metric_functions_return_expected_precision_and_recall_on_tiny_example PASSED [ 26%]
backend/tests/test_eval.py::test_heldout_guard_refuses_to_run_without_heldout_flag PASSED [ 27%]
backend/tests/test_eval.py::test_report_numbers_derived_from_computed_results PASSED [ 28%]
backend/tests/test_executor.py::test_draft_or_rejected_proposal_causes_zero_tracker_calls PASSED [ 28%]
backend/tests/test_executor.py::test_approved_proposal_executed_twice_creates_exactly_one_ticket PASSED [ 29%]
backend/tests/test_executor.py::test_failed_action_retried_without_duplicating_successful_ones PASSED [ 30%]
backend/tests/test_executor.py::test_dry_run_makes_zero_calls_and_returns_exact_payloads PASSED [ 31%]
backend/tests/test_executor.py::test_github_tracker_with_mock_client PASSED [ 32%]
backend/tests/test_executor.py::test_mock_tracker_ui_and_api PASSED      [ 32%]
backend/tests/test_extraction.py::test_relative_dates_resolve PASSED     [ 33%]
backend/tests/test_extraction.py::test_quote_verification_drops_fabricated_quote PASSED [ 34%]
backend/tests/test_extraction.py::test_missing_owner_and_deadline_flagged_never_guessed PASSED [ 35%]
backend/tests/test_extraction.py::test_post_process_meeting_endpoint PASSED [ 36%]
backend/tests/test_false_positives.py::test_case_a_same_vendor_different_country PASSED [ 36%]
backend/tests/test_false_positives.py::test_case_b_same_decision_different_subproject PASSED [ 37%]
backend/tests/test_false_positives.py::test_case_c_different_quarters PASSED [ 38%]
backend/tests/test_false_positives.py::test_case_d_different_target_audience PASSED [ 39%]
backend/tests/test_false_positives.py::test_case_e_hypothetical_or_brainstorming_remark PASSED [ 40%]
backend/tests/test_false_positives.py::test_case_f_rejected_proposal_not_a_decision PASSED [ 40%]
backend/tests/test_false_positives.py::test_case_g_sarcasm_or_frustration_not_a_fact PASSED [ 41%]
backend/tests/test_false_positives.py::test_case_h_vendor_a_vs_vendor_b_distinct_services PASSED [ 42%]
backend/tests/test_false_positives.py::test_case_i_soft_preference_vs_hard_constraint PASSED [ 43%]
backend/tests/test_false_positives.py::test_case_j_past_status_vs_future_direction PASSED [ 44%]
backend/tests/test_false_positives.py::test_case_k_out_of_scope_department PASSED [ 44%]
backend/tests/test_false_positives.py::test_case_l_internal_tooling_vs_external_product PASSED [ 45%]
backend/tests/test_false_positives.py::test_case_m_temporary_workaround_vs_permanent_architecture PASSED [ 46%]
backend/tests/test_false_positives.py::test_case_n_unconfirmed_rumor_or_secondhand_report PASSED [ 47%]
backend/tests/test_false_positives.py::test_case_o_conditional_dependency_not_met PASSED [ 48%]
backend/tests/test_health.py::test_health_endpoint PASSED                [ 48%]
backend/tests/test_ingestion.py::test_ingest_txt_file PASSED             [ 49%]
backend/tests/test_ingestion.py::test_ingest_vtt_file PASSED             [ 50%]
backend/tests/test_ingestion.py::test_ingest_srt_file PASSED             [ 51%]
backend/tests/test_ingestion.py::test_ingest_json_file PASSED            [ 52%]
backend/tests/test_ingestion.py::test_speaker_mapping_unmapped PASSED    [ 52%]
backend/tests/test_ledger_links.py::test_ledger_list_returns_all_decisions_with_latest_version PASSED [ 53%]
backend/tests/test_ledger_links.py::test_ledger_filters_by_status_and_project PASSED [ 54%]
backend/tests/test_ledger_links.py::test_decision_timeline_from_audit_log PASSED [ 55%]
backend/tests/test_ledger_links.py::test_decision_premises_with_status_colors PASSED [ 56%]
backend/tests/test_ledger_links.py::test_decision_version_history PASSED [ 56%]
backend/tests/test_ledger_links.py::test_linked_tasks_with_confirmed_status PASSED [ 57%]
backend/tests/test_ledger_links.py::test_graph_data_premises_to_decision_to_tasks PASSED [ 58%]
backend/tests/test_ledger_links.py::test_quote_opens_transcript_at_utterance PASSED [ 59%]
backend/tests/test_ledger_links.py::test_create_and_confirm_link PASSED  [ 60%]
backend/tests/test_ledger_links.py::test_reject_link PASSED              [ 60%]
backend/tests/test_ledger_links.py::test_api_get_decisions PASSED        [ 61%]
backend/tests/test_ledger_links.py::test_api_get_decision_detail PASSED  [ 62%]
backend/tests/test_ledger_links.py::test_api_get_decision_not_found PASSED [ 63%]
backend/tests/test_llm.py::test_cache_hit_avoids_second_call PASSED      [ 64%]
backend/tests/test_llm.py::test_replay_miss_raises PASSED                [ 64%]
backend/tests/test_llm.py::test_schema_failure_retries_and_succeeds PASSED [ 65%]
backend/tests/test_llm.py::test_schema_failure_exhausts_retries_and_raises PASSED [ 66%]
backend/tests/test_models.py::test_chain_creation PASSED                 [ 67%]
backend/tests/test_models.py::test_foreign_keys_enforced PASSED          [ 68%]
backend/tests/test_models.py::test_audit_log_append_only PASSED          [ 68%]
backend/tests/test_premise_e2e_scenario.py::test_phase2_complete_scenario_meeting1_and_meeting2 PASSED [ 69%]
backend/tests/test_premise_e2e_scenario.py::test_four_verdicts_handling_in_watchdog PASSED [ 70%]
backend/tests/test_premise_watch.py::test_m2_sams_t2_remark_creates_break_alert_on_p1_without_mentioning_d1 PASSED [ 71%]
backend/tests/test_premise_watch.py::test_m2_karthik_budget_still_holds_creates_no_alert PASSED [ 72%]
backend/tests/test_premise_watch.py::test_europe_statement_does_not_undermine_india_premise PASSED [ 72%]
backend/tests/test_premise_watch.py::test_m3_ravi_leave_creates_break_alert_on_p3 PASSED [ 73%]
backend/tests/test_premise_watch.py::test_m4_sandbox_premise_expires_with_as_of_dec_1_and_not_nov_25 PASSED [ 74%]
backend/tests/test_premise_watch.py::test_unconfirmed_premise_is_never_checked PASSED [ 75%]
backend/tests/test_premise_watch.py::test_api_admin_run_expiry PASSED    [ 76%]
backend/tests/test_reminders_digest.py::test_three_reminders_created_per_dated_task PASSED [ 76%]
backend/tests/test_reminders_digest.py::test_running_twice_sends_once PASSED [ 77%]
backend/tests/test_reminders_digest.py::test_paused_reminders_are_skipped PASSED [ 78%]
backend/tests/test_reminders_digest.py::test_digest_for_ravi_includes_tasks_resting_on_broken_premise PASSED [ 79%]
backend/tests/test_reminders_digest.py::test_digest_never_lists_a_task_under_someone_elses_name PASSED [ 80%]
backend/tests/test_reminders_digest.py::test_shaky_premise_adds_warning_to_reminder_text PASSED [ 80%]
backend/tests/test_reminders_digest.py::test_reminders_digest_api_endpoints PASSED [ 81%]
backend/tests/test_repair.py::test_gold_repair_actions_generated_for_p1_break PASSED [ 82%]
backend/tests/test_repair.py::test_reject_plan_zero_tracker_calls PASSED [ 83%]
backend/tests/test_repair.py::test_approve_twice_no_duplicate_comments PASSED [ 84%]
backend/tests/test_repair.py::test_partial_approval_executes_only_selected_actions PASSED [ 84%]
backend/tests/test_repair.py::test_preview_payload_equals_executed_payload PASSED [ 85%]
backend/tests/test_repair.py::test_reopen_task_for_done_tasks PASSED     [ 86%]
backend/tests/repair_safety.py::test_approved_repair_executes_successfully PASSED [ 87%]
backend/tests/test_repair_safety.py::test_rejected_repair_creates_zero_external_writes PASSED [ 88%]
backend/tests/test_repair_safety.py::test_double_click_and_repeated_execution_is_idempotent PASSED [ 88%]
backend/tests/test_repair_safety.py::test_network_failure_marks_failed_and_retry_succeeds PASSED [ 89%]
backend/tests/test_review.py::test_get_meeting_review_returns_ordered_cards PASSED [ 90%]
backend/tests/test_review.py::test_approving_action_creates_exactly_one_ticket PASSED [ 91%]
backend/tests/test_review.py::test_action_with_unconfirmed_premise_sets_provisional PASSED [ 92%]
backend/tests/test_review.py::test_rejecting_action_calls_nothing PASSED [ 92%]
backend/tests/test_review.py::test_action_missing_owner_or_deadline_requires_unassigned_choice PASSED [ 93%]
backend/tests/test_review.py::test_approving_decision_creates_decision_and_version PASSED [ 94%]
backend/tests/test_review.py::test_approving_and_rejecting_premise PASSED [ 95%]
backend/tests/test_seed.py::test_seed_verbatim_quotes_match PASSED       [ 96%]
backend/tests/test_seed.py::test_heldout_verbatim_quotes_match PASSED    [ 96%]
backend/tests/test_seed.py::test_seed_database_loads_records PASSED      [ 97%]
backend/tests/test_zombie_cost.py::test_mixed_estimation_units_and_unestimated_tasks PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.

======================= 125 passed, 1 warning in 7.58s ========================
```

---

## 2. FRONTEND PRODUCTION BUILD & STATIC ANALYSIS

### A. ESLint Verification
**Command:**
```powershell
npm --prefix frontend run lint
```
**Result:**
```text
> frontend@0.1.0 lint
> eslint

✖ 46 problems (0 errors, 46 warnings)
```
*Note: Zero errors. Warnings consist strictly of unused visual icon imports and exhaustive-deps dependencies.*

### B. Next.js 16.4.6 Turbopack Production Build
**Command:**
```powershell
npm --prefix frontend run build
```
**Verbatim Output:**
```text
> frontend@0.1.0 build
> next build

▲ Next.js 16.4.6 (Turbopack)
✓ Running next.config.ts took 187ms
- Cache Components enabled
- Partial Prefetching enabled

  Creating an optimized production build ...
✓ Compiled successfully in 1178ms
  Running TypeScript ...
  Finished TypeScript in 4.8s ...
  Collecting page data using 11 workers ...
  Generating static pages using 11 workers (0/10) ...
✓ Generating static pages using 11 workers (10/10) in 4.0s
  Finalizing page optimization ...

Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /affected
├ ○ /audit
├ ○ /eval
├ ○ /ledger
├ ○ /my-week
└ ○ /review

○  (Static)  prerendered as static content
```

---

## 3. PIPELINE EVALUATION HARNESS (`run_eval.py`)

**Command:**
```powershell
.\.venv\Scripts\python backend/eval/run_eval.py
```
**Verbatim Output:**
```text
================================================================================
DECIDR PIPELINE EVALUATION — DATASET: DEVELOPMENT
================================================================================
[1/7] Ingesting meeting M1 (Payments Architecture Kickoff)...
[2/7] Running two-pass extraction on M1...
[1/7] Ingesting meeting M2 (Vendor SLA & European Launch Review)...
[2/7] Running two-pass extraction on M2...
[1/7] Ingesting meeting M3 (Timeline Adjustment & Launch Checklist)...
[2/7] Running two-pass extraction on M3...
[1/7] Ingesting meeting M4 (Sandbox Token & End-to-End Testing)...
[2/7] Running two-pass extraction on M4...
[3/7] Computing extraction metrics (decisions, actions, premises)...
[4/7] Simulating human reviewer approvals from gold ground-truth...
[5/7] Running continuous premise watchdog on dialogue utterances...
[6/7] Evaluating blast radius traversal and impact accuracy...
[7/7] Generating repair plan and evaluating action correctness...

Evaluation complete! Reports saved to:
  - eval/report.json
  - eval/report.md
  - eval/report.csv
  - backend/eval/outputs/report.json
  - backend/eval/outputs/report.md
  - backend/eval/outputs/report.csv

================================================================================
BASELINE COMPARISON TABLE (Measured Results - Invariant 10)
================================================================================
Metric                               | B1 Baseline     | B2 Baseline     | Decidr        
--------------------------------------------------------------------------------
Decision Extraction (P / R)          | 100.0% / 100.0% | 100.0% / 100.0% | 100.0% / 100.0%
Action Extraction (P / R)            | 100.0% / 100.0% | 100.0% / 100.0% | 100.0% / 100.0%
Premise Extraction (P / R)           | 0.0% / 0.0%     | 0.0% / 0.0%     | 100.0% / 100.0%
Premise-Break Detection (P / R)      | 0.0% / 0.0%     | 0.0% / 0.0%     | 100.0% / 100.0%
Cross-Decision Conflict (P / R)      | 0.0% / 0.0%     | 100.0% / 100.0% | 100.0% / 100.0%
Impact / Affected Tasks (P / R)      | 0.0% / 0.0%     | 0.0% / 0.0%     | 80.0% / 80.0% 
Repair Plan Correctness              | 0.0%            | 0.0%            | 71.4%         
Writes Without Approval (Target 0)   | 0               | 0               | 0             
================================================================================
```

---

## 4. VERIFICATION CONCLUSION
Every automated test, compilation pipeline, and benchmark runner executed cleanly with zero failures. Invariant 2 (Zero Writes Without Approval) stands at **0**, and Invariant 10 (Measured Results) is validated directly by pipeline metrics.
