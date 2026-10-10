var recordActual019 = async (pending, observation) => {
 const n = collectRecords019.length + 1;
 const id = String(n).padStart(4,'0');
 const dir = out019 + '/record-' + id;
 await fs019.mkdir(dir);
 const nested = pending.nested_result;
 const outerRaw = observation.raw_rendered !== undefined ? observation.raw_rendered : 'Script completed\nWall time ' + observation.wall_time_seconds.toFixed(1) + ' seconds\nOutput:\n' + JSON.stringify(nested);
 await fs019.writeFile(dir + '/actual-nested-result.json',JSON.stringify(nested));
 await fs019.writeFile(dir + '/actual-nested-output.txt',nested.output);
 await fs019.writeFile(dir + '/actual-outer-rendered.txt',outerRaw);
 await fs019.writeFile(dir + '/actual-command.sh',pending.cmd);
 await fs019.writeFile(dir + '/actual-prefix.txt',pending.prefix);
 await fs019.writeFile(dir + '/actual-view.json',JSON.stringify(pending.view));
 let callSource = templates019[observation.template];
 callSource = callSource.replace(/^const VIEW = .*;$/m,'const VIEW = '+JSON.stringify(pending.view)+';');
 callSource = callSource.replace('text(await tools.exec_command({cmd, max_output_tokens: 16384}));\n',observerTail019);
 if(observation.nested_cap===100) callSource=callSource.replace('const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});','const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 100});');
 if(observation.outer_cap===100) callSource=callSource.replace('// @exec: {"max_output_tokens": 20000}','// @exec: {"max_output_tokens": 100}');
 await fs019.writeFile(dir+'/actual-functions-exec.js',callSource);
 const v = pending.view;
 const selector = v.selector;
 const field = selector?.slice(1);
 const empty = observation.empty_control===true;
 const points = empty ? [] : originalPoints019[field];
 const expectedReference = empty ? emptyRef019 : JSON.parse(await fs019.readFile(base019+'/fixture-actual-001/reference.json','utf8'));
 const errors=[];
 let parsed;
 if(observation.outer_truncated) errors.push('ACTUAL_OUTER_TRUNCATION');
 if(nested.session_id!==undefined) errors.push('UNRESOLVED_SESSION');
 if(!Number.isInteger(nested.exit_code)||nested.exit_code!==0) errors.push('INTEGER_COMPLETION_NOT_ZERO');
 try { parsed=JSON.parse(nested.output); } catch {errors.push('INCOMPLETE_OR_NONJSON_NESTED_OUTPUT');}
 const before = field ? {selector,start_char:v.start_char,start_utf8_byte:Buffer.byteLength(points.slice(0,v.start_char).join(''),'utf8')} : null;
 const assert=(condition,code)=>{if(!condition)errors.push(code)};
 if(parsed && !observation.outer_truncated){
 assert(parsed.status==='ok','VIEW_NOT_OK');
 assert(parsed.carrier_path===expectedReference.path&&parsed.carrier_sha256===expectedReference.sha256&&parsed.request_sha256===expectedReference.request_sha256,'REFERENCE_MISMATCH');
 assert(parsed.output_cap_bytes===v.output_cap_bytes&&parsed.metadata_reserve_bytes===v.metadata_reserve_bytes,'CAP_METADATA_MISMATCH');
 assert(Buffer.byteLength(nested.output,'utf8')<=v.output_cap_bytes,'OUTPUT_BYTE_CAP_EXCEEDED');
 assert(parsed.operation===v.operation,'OPERATION_MISMATCH');
 if(v.operation==='inventory'){
 const fields=parsed.fields;
 assert(Array.isArray(fields)&&fields.length===2,'INVENTORY_FIELDS_INVALID');
 for(const [i,key] of ['system','user'].entries()) {
 const e=empty?[]:originalPoints019[key]; const got=fields?.[i];
 assert(got?.selector==='/'+key&&got?.field_chars===e.length&&got?.field_utf8_bytes===Buffer.byteLength(e.join(''),'utf8')&&got?.start_char===0&&got?.end_char===e.length,'INVENTORY_'+key+'_MISMATCH');
 }
 } else {
 const end=parsed.end_char; const content=points.slice(v.start_char,end).join('');
 assert(parsed.selector===selector&&parsed.start_char===v.start_char,'START_SELECTOR_MISMATCH');
 assert(Number.isInteger(end)&&end>=v.start_char&&end<=points.length,'END_CURSOR_INVALID');
 assert(parsed.content===content,'EXACT_ORIGINAL_SLICE_MISMATCH');
 assert(parsed.field_chars===points.length&&parsed.field_utf8_bytes===Buffer.byteLength(points.join(''),'utf8'),'FIELD_TOTAL_MISMATCH');
 assert(parsed.content_chars===end-v.start_char&&Array.from(parsed.content).length===end-v.start_char,'CODE_POINT_COUNT_MISMATCH');
 assert(parsed.start_utf8_byte===before.start_utf8_byte&&parsed.end_utf8_byte===Buffer.byteLength(points.slice(0,end).join(''),'utf8')&&parsed.content_utf8_bytes===Buffer.byteLength(content,'utf8'),'UTF8_OFFSETS_MISMATCH');
 assert(parsed.next_char===end&&parsed.field_eof===(end===points.length),'NEXT_EOF_MISMATCH');
 assert(end>v.start_char||parsed.field_eof,'NO_PROGRESS_WITHOUT_EOF');
 const encodedContent=JSON.stringify(parsed.content);
 assert(Buffer.byteLength(encodedContent,'utf8')<=v.output_cap_bytes-v.metadata_reserve_bytes,'CONTENT_ENCODED_CAP_EXCEEDED');
 if(observation.case_id==='CC019-AC-001'&&!empty){
 assert(progress019[field].char===v.start_char,'NONCONTIGUOUS_AC001_CHAR');
 assert(progress019[field].utf8===parsed.start_utf8_byte,'NONCONTIGUOUS_AC001_UTF8');
 if(field==='user')assert(progress019.system.eof,'SYSTEM_NOT_COMPLETE_BEFORE_USER');
 }
 }
 }
 const accepted=errors.length===0;
 if(accepted&&field&&observation.case_id==='CC019-AC-001'&&!empty)progress019[field]={char:parsed.next_char,utf8:parsed.end_utf8_byte,eof:parsed.field_eof};
 const record={format:'verislop.cc019.actual-channel-record/1',n,case_id:observation.case_id,observation,nested_result: nested,before,after:accepted&&field?{selector,next_char:parsed.next_char,end_utf8_byte:parsed.end_utf8_byte,field_eof:parsed.field_eof}:before,accepted,errors,view:v,hashes:{nested_envelope:sha019(JSON.stringify(nested)),nested_output:sha019(nested.output),outer_rendered:sha019(outerRaw),command:sha019(pending.cmd),prefix:sha019(pending.prefix),view:sha019(JSON.stringify(v)),functions_exec:sha019(callSource)},command_interpretation:{executable:'python',argv:['python','-I','-B','-'],source_input:'inline here-document stdin',helper_reads:false},stdio_separation:'UNAVAILABLE',pid:'UNAVAILABLE',progress:structuredClone(progress019)};
 await fs019.writeFile(dir+'/record.json',JSON.stringify(record,null,2)+'\n');
 collectRecords019.push(record);
 await fs019.writeFile(out019+'/progress.json',JSON.stringify({records:collectRecords019.length,progress:progress019,last_record:id},null,2)+'\n');
 nodeRepl.write({n,case_id:record.case_id,accepted,errors,before,after:record.after,progress:progress019});
};
