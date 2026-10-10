const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});
text(ACTUAL_RESULT);
store("verislop.cc019.collector.pending", {nested_result: ACTUAL_RESULT, cmd, view: VIEW, prefix: PREFIX});
