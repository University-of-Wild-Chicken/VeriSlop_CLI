// @exec: {"max_output_tokens": 20000}
const caseInput = load("support018_channel_case");
if (!caseInput || typeof caseInput.cmd !== "string" || typeof caseInput.id !== "string") {
  throw new Error("Frozen channel case input is missing");
}
const actualResult = await tools.exec_command({
  cmd: caseInput.cmd,
  max_output_tokens: caseInput.max_output_tokens,
  tty: false,
});
text(actualResult);
store("support018_channel_actual_" + caseInput.id, actualResult);
