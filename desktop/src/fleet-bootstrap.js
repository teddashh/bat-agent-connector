import {fleetBootstrap} from "./transport/index.ts";

// Local account-scoped receipts stay separate from central identity and event cursors.
export async function mountFleetBootstrap(main, {h, t}) {
  const panel=h("section",{class:"panel fleet-bootstrap","aria-label":t("bootstrap_title")});
  const content=h("div"), message=h("p",{class:"muted",role:"status"});
  panel.append(h("h2",{},t("bootstrap_title")),h("p",{class:"muted"},t("bootstrap_help")),content,message);
  if(!main.isConnected)return()=>{};
  main.prepend(panel);
  let disposed=false,busy=false,readable=false,snapshot,original,timer;
  const alive=()=>!disposed&&panel.isConnected;
  const storage="batc.desktop.fleet.bootstrap.original";
  const hex=(v,n)=>typeof v==="string"&&new RegExp(`^[0-9a-f]{${n}}$`).test(v);
  const valid=value=>value&&hex(value.recipe_binding,64)&&hex(value.status?.request_id,32)
    &&["querying","ensure_requested","needs_attention","service_running"].includes(value.status.phase)
    &&Number.isInteger(value.status.queries)&&value.status.queries>=0&&value.status.queries<=4
    &&typeof value.status.ensure_requested==="boolean"&&typeof value.status.ensure_accepted==="boolean"
    &&[null,"unknown","stopped","transitioning","owner_present","running"].includes(value.status.last_state)
    &&(!value.status.ensure_accepted||value.status.ensure_requested);
  const save=()=>{if(original)try{sessionStorage.setItem(storage,JSON.stringify({request_id:original.status.request_id,recipe_binding:original.recipe_binding}));}catch{/* The authoritative ID is already durable in native storage. */}};
  try{const value=JSON.parse(sessionStorage.getItem(storage)||"null");if(hex(value?.request_id,32)&&hex(value.recipe_binding,64))original={recipe_binding:value.recipe_binding,status:{request_id:value.request_id},unknown:true};}catch{/* No stored contents can authorize an effect. */}
  const accept=(value,expected)=>{
    if(!valid(value)||expected&&(value.status.request_id!==expected.status.request_id||value.recipe_binding!==expected.recipe_binding))throw new Error(t("bootstrap_unproven"));
    original=value;save();
  };
  const current=()=>readable&&snapshot?.configured&&snapshot.eligible&&original?.recipe_binding===snapshot.recipe_binding&&!original.unknown;
  const phase=()=>original?.unknown?"unknown":original?.status.queries===0?"prepared":original?.status.phase;
  const readOriginal=async()=>{
    if(!original)return;
    const expected=original;
    original={...original,unknown:true};save();
    const value=await fleetBootstrap({action:"receipt",request_id:expected.status.request_id});
    if(alive()){if(!value)throw new Error(t("bootstrap_unproven"));accept(value,expected);}
  };
  const read=async()=>{
    readable=false;
    const value=await fleetBootstrap({action:"overview"});
    if(!alive())return;
    if(value?.version!==1||typeof value.configured!=="boolean"||typeof value.auto_ensure!=="boolean"
      ||typeof value.eligible!=="boolean"||!(value.recipe_binding===null||hex(value.recipe_binding,64))
      ||value.latest!==null&&!valid(value.latest))throw new Error(t("bootstrap_unproven"));
    snapshot=value;readable=true;
    if(!original&&value.latest)accept(value.latest);
    await readOriginal();
  };
  const run=async(fn)=>{
    if(!alive()||busy)return;busy=true;message.textContent=t("bootstrap_working");render();
    try{await fn();if(alive())message.textContent="";}
    catch{if(alive())message.textContent=t("bootstrap_unknown");}
    finally{busy=false;if(alive())render();}
  };
  const prepare=()=>run(async()=>{
    const binding=snapshot.recipe_binding;
    const value=await fleetBootstrap({action:"prepare",recipe_binding:binding});
    if(alive()){if(!valid(value)||value.recipe_binding!==binding)throw new Error(t("bootstrap_unproven"));accept(value);}
  });
  const advance=()=>run(async()=>{
    if(!current())return;
    const expected=original;
    // Freeze the exact native durable ID before awaiting. Failure/reload only reads;
    // the native store already prevents a replacement request or repeated ensure.
    original={...original,unknown:true};save();
    const value=await fleetBootstrap({action:"advance",request_id:expected.status.request_id,recipe_binding:expected.recipe_binding});
    if(alive())accept(value,expected);
  });
  function render(){
    if(!alive())return;
    const button=(key,fn,disabled=false,primary=false)=>h("button",{class:primary?"primary":"secondary",disabled:busy||disabled,onclick:fn},t(key));
    content.replaceChildren(...[
      snapshot?h("p",{},t(snapshot.configured?"bootstrap_configured":"bootstrap_missing")," · ",t(snapshot.auto_ensure?"bootstrap_auto_on":"bootstrap_auto_off")):null,
      snapshot?.code?h("p",{class:"muted"},t(snapshot.code==="BOOTSTRAP_NOT_NEEDED"?"bootstrap_healthy":"bootstrap_blocked")):null,
      original?h("p",{class:"note"},t("bootstrap_"+(phase()||"unknown"))):null,
      original?h("p",{class:"muted bootstrap-receipt"},t("bootstrap_request")," ",h("code",{},original.status.request_id),
        Number.isInteger(original.status.queries)?` · ${t("bootstrap_queries",{count:original.status.queries})}`:null):null,
      original&&snapshot?.recipe_binding!==original.recipe_binding?h("p",{class:"muted"},t("bootstrap_changed")):null,
      h("div",{class:"actions"},
        button("bootstrap_prepare",prepare,!readable||!snapshot?.eligible||!!original&&phase()!=="service_running",!original),
        original&&!["service_running"].includes(phase())?button(original.status.ensure_requested?"bootstrap_reconcile":"bootstrap_ensure",advance,!current()||original.status.queries>=4,true):null,
        original?button("bootstrap_read",()=>run(readOriginal)):null,
        button("bootstrap_refresh",()=>run(read))),
      h("p",{class:"muted"},t("bootstrap_separate")),
    ].filter(Boolean));
  }
  render();await run(read);
  const poll=async()=>{if(!alive())return;if(!busy)await run(read);if(alive())timer=setTimeout(poll,5000);};
  timer=setTimeout(poll,5000);
  return()=>{disposed=true;clearTimeout(timer);panel.remove();};
}
