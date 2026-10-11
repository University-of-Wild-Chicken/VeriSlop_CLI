
const ref={path:'/synthetic/reviewer-own.json',sha256:'sha256:'+'a'.repeat(64),request_sha256:'sha256:'+'b'.repeat(64)};
const view={operation:'inventory',output_cap_bytes:8192,metadata_reserve_bytes:2048};
const output={format:'verislop.exact-carrier-view/0.1',status:'ok',carrier_path:ref.path,carrier_raw_bytes:12345,carrier_sha256:ref.sha256,request_sha256:ref.request_sha256,request_id:'',char_unit:'decoded_unicode_code_points',byte_unit:'decoded_field_utf8',output_cap_bytes:8192,metadata_reserve_bytes:2048,operation:'inventory',navigation:'complete_linear_fields_only',fields:[{selector:'/system',field_chars:0,field_utf8_bytes:0,start_char:0,end_char:0},{selector:'/user',field_chars:0,field_utf8_bytes:0,start_char:0,end_char:0}]};
const result={chunk_id:'empty-id-generic-chunk',exit_code:0,original_token_count:100,wall_time_seconds:0.001,output:checkpointWire(output)+'\n'};
let error=null;try{checkpointConfirm(undefined,{reference:ref,view,result},{chunk_id:result.chunk_id,outer_output_intact:true},ref);}catch(failure){error=failure.message;}
if(error!=='ACTUAL_VIEW_IDENTITY_MISMATCH')throw new Error('Unexpected empty ID observation: '+error);
console.log(JSON.stringify({format:'verislop.carrier003-empty-id-source-counterexample/1',reference:ref,view,result,confirmation:{chunk_id:result.chunk_id,outer_output_intact:true},checkpoint_error:error,actual_VIEW_calls:0,model_calls:0,Lean_calls:0,runtime_authority:false}));
