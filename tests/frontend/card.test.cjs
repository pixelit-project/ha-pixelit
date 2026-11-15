// Exercise the shipped card/editor logic with a minimal Lit/DOM test double.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const source=readFileSync(resolve(__dirname,'../../custom_components/pixelit/www/pixelit-card.js'),'utf8');
const registry=new Map();
const html=(strings,...values)=>strings.reduce((result,part,i)=>result+part+(values[i]??''),'');
class Element extends EventTarget{disconnectedCallback(){} getBoundingClientRect(){return {height:0};}}
const context=vm.createContext({
  setTimeout,clearTimeout,
  re:Element,V:html,a:html,W:'',
  e:(decorators,target,...args)=>{for(const decorate of decorators){target=decorate(target,...args)||target;}return target;},
  ce:name=>type=>{registry.set(name,type);return type;},
  pe:()=>()=>{},ue:()=>()=>{},
  CustomEvent:class extends Event{constructor(name,options){super(name,options);this.detail=options.detail;}},
  customElements:{get:name=>registry.get(name),define:(name,type)=>registry.set(name,type)},
  document:{createElement:name=>new (registry.get(name))()},window:{customCards:[]},
});
vm.runInContext(source.slice(source.indexOf('const CARD_NAME=')).replace(/export\{[^}]+\};?\s*$/,''),context);
const Card=registry.get('pixelit-card'),Editor=registry.get('pixelit-card-editor');
const hass={language:'de',entities:{
 'sensor.live':{entity_id:'sensor.live',platform:'pixelit'},
 'light.display':{entity_id:'light.display',platform:'pixelit'},
},states:{
 'sensor.live':{state:'connected',attributes:{width:32,height:8,hex:'FF0000'.repeat(256)}},
 'light.display':{state:'on',attributes:{}},
}};
function card(config={}){const instance=new Card();instance.setConfig({entity:'sensor.live',...config});instance.hass=hass;return instance;}

test('preselects the liveview sensor when the same device also has a light',()=>{
 assert.equal(Card.getStubConfig(hass).entity,'sensor.live');
 const multiple={...hass,entities:{...hass.entities,'sensor.other':{entity_id:'sensor.other',platform:'pixelit'}},states:{...hass.states,'sensor.other':hass.states['sensor.live']}};
 assert.equal(Card.getStubConfig(multiple).entity,'');
});
test('status remains visible with title hidden',()=>{
 const output=card({show_header:false}).render();
 assert.match(output,/Verbunden/);assert.doesNotMatch(output,/class="plc-title"/);
 assert.doesNotMatch(card({show_header:false,show_status:false}).render(),/plc-status/);
});
test('theme card is default and transparency is explicit',()=>{
 assert.match(card().render(),/class=plc>/);
 assert.match(card({transparent:true}).render(),/class=plc transparent>/);
});
test('missing frames show a useful message without an empty pixel grid',()=>{
 const instance=card({entity:''});assert.match(instance.render(),/Kein PixelIt-Sensor/);assert.doesNotMatch(instance.render(),/class="plc-grid"/);
 instance.setConfig({entity:'sensor.missing'});assert.match(instance.render(),/nicht verfügbar/);
});
test('disconnected frame has explicit status, even without a title',()=>{
 const instance=card({show_header:false});instance.hass={...hass,states:{'sensor.live':{...hass.states['sensor.live'],state:'disconnected'}}};
 assert.match(instance.render(),/Getrennt/);
 assert.match(instance.render(),/class="plc-grid"/);
});
test('editor and YAML share bounds and validation',()=>{
 for(const config of [{gap:-1},{gap:17},{gap:1.5},{gap:'2'},{show_status:'false'},{entity:'light.display'}]){
  assert.throws(()=>card(config));assert.throws(()=>new Editor().setConfig(config));
 }
 assert.doesNotThrow(()=>card({gap:0}));assert.doesNotThrow(()=>card({gap:16}));
});
test('legacy configurations and card type remain supported',()=>{
 const instance=card({type:'custom:pixelit-liveview-card',width:64,height:8});
 assert.equal(instance._config.width,64);assert.equal(instance._config.type,'custom:pixelit-liveview-card');
 assert.ok(registry.get('pixelit-liveview-card'));
});
test('native form exposes advanced gap and localized labels, preserves other configuration',()=>{
 const editor=new Editor();editor.hass=hass;editor.setConfig({entity:'sensor.live',grid_options:{columns:6}});
 assert.match(editor.render(),/<ha-form/);assert.equal(editor._computeLabel({name:'transparent'}),'Transparenter Hintergrund');
 let emitted;editor.addEventListener('config-changed',event=>emitted=event.detail.config);
 let stopped=false;editor._valueChanged({stopPropagation(){stopped=true;},detail:{value:{show_header:false}}});
 assert.equal(stopped,true);assert.equal(emitted.show_header,false);assert.equal(emitted.grid_options.columns,6);
});
test('sizing follows actual height and status-only cards need less space',()=>{
 const instance=card();const full=instance.getCardSize();
 assert.ok(card({show_pixels:false,show_header:false}).getCardSize()<full);
 instance.getBoundingClientRect=()=>({height:220});assert.equal(instance.getCardSize(),5);
 assert.equal(instance.getGridOptions().rows,'auto');
});

test('diagnostic and environmental sensors are excluded from Liveview selection',()=>{
 const withReadings={...hass,entities:{...hass.entities,'sensor.temp':{entity_id:'sensor.temp',platform:'pixelit'}},states:{...hass.states,'sensor.temp':{state:'22',attributes:{unit_of_measurement:'°C'}}}};
 assert.equal(Card.getStubConfig(withReadings).entity,'sensor.live');
 const suggest=context.window.customCards[0].getEntitySuggestion;
 assert.equal(suggest(withReadings,'sensor.temp'),null);
 assert.equal(suggest(withReadings,'sensor.live').config.entity,'sensor.live');
 const editor=new Editor();editor.hass=withReadings;editor.setConfig({entity:'sensor.live'});editor.render();
 assert.deepEqual(Array.from(editor._schema[0].selector.entity.include_entities),['sensor.live']);
});

const pointer=(x=0)=>({button:0,pointerId:1,clientX:x,clientY:0});
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
test('actions follow HA sensor defaults and native editor exposes all three',()=>{
 const instance=card();assert.equal(instance._interactive(),true);
 for(const key of ['tap_action','hold_action','double_tap_action']){
  assert.equal(instance._config[key].action,key==='tap_action'?'more-info':'none');assert.throws(()=>card({[key]:'toggle'}));
 }
 const editor=new Editor();editor.hass=hass;editor.setConfig({entity:'sensor.live'});editor.render();
 const fields=editor._schema.flatMap(field=>field.schema||[]).filter(field=>field.selector?.ui_action);
 assert.deepEqual(Array.from(fields,field=>field.name),['tap_action','hold_action','double_tap_action']);
 assert.deepEqual(Array.from(fields,field=>field.selector.ui_action.default_action),['more-info','none','none']);
 let detail;instance.addEventListener('hass-action',event=>detail=event.detail);
 instance._pointerDown(pointer());instance._pointerUp(pointer());
 assert.equal(detail.config.tap_action.action,'more-info');
 assert.equal(detail.config.entity,'sensor.live');
});
test('tap forwards full action configuration to Home Assistant',()=>{
 const instance=card({tap_action:{action:'perform-action',perform_action:'light.toggle',target:{entity_id:'light.display'},confirmation:true}});
 let detail;instance.addEventListener('hass-action',event=>detail=event.detail);
 instance._pointerDown(pointer());instance._pointerUp(pointer());
 assert.equal(detail.action,'tap');assert.equal(detail.config.tap_action.target.entity_id,'light.display');
 assert.equal(detail.config.tap_action.confirmation,true);
});
test('double tap suppresses single tap and a single tap still works',async()=>{
 const instance=card({tap_action:{action:'more-info'},double_tap_action:{action:'navigate',navigation_path:'/test'}});
 const actions=[];instance.addEventListener('hass-action',event=>actions.push(event.detail.action));
 for(let i=0;i<2;i++){instance._pointerDown(pointer());instance._pointerUp(pointer());}
 await wait(280);assert.deepEqual(actions,['double_tap']);
 instance._pointerDown(pointer());instance._pointerUp(pointer());await wait(280);
 assert.deepEqual(actions,['double_tap','tap']);
});
test('hold suppresses tap, movement cancels and replacement clears pending gestures',async()=>{
 const instance=card({tap_action:{action:'more-info'},hold_action:{action:'toggle'}});
 const actions=[];instance.addEventListener('hass-action',event=>actions.push(event.detail.action));
 instance._pointerDown(pointer());await wait(530);instance._pointerUp(pointer());
 assert.deepEqual(actions,['hold']);
 instance._pointerDown(pointer());instance._pointerMove(pointer(20));instance._pointerUp(pointer(20));
 instance._pointerDown(pointer());instance.setConfig({entity:'sensor.live'});await wait(530);
 assert.deepEqual(actions,['hold']);
});
test('keyboard runs optional tap and shift-hold actions',()=>{
 const instance=card({tap_action:{action:'more-info'},hold_action:{action:'toggle'}});
 const actions=[];instance.addEventListener('hass-action',event=>actions.push(event.detail.action));
 instance._keyDown({key:'Enter',preventDefault(){}});
 instance._keyDown({key:' ',shiftKey:true,preventDefault(){}});
 assert.deepEqual(actions,['tap','hold']);
});

test('unload and pointer cancellation clear pending actions',async()=>{
 for(const cancel of [instance=>instance.disconnectedCallback(),instance=>instance._clearGestures()]){
  const instance=card({tap_action:{action:'more-info'},double_tap_action:{action:'navigate'}});
  let calls=0;instance.addEventListener('hass-action',()=>calls++);
  instance._pointerDown(pointer());instance._pointerUp(pointer());cancel(instance);
  await wait(280);assert.equal(calls,0);
 }
});
test('disabled actions never dispatch and action settings survive editor changes',()=>{
 const instance=card({tap_action:{action:'none'}});let calls=0;instance.addEventListener('hass-action',()=>calls++);
 instance._pointerDown(pointer());instance._pointerUp(pointer());instance._runAction('tap');
 assert.equal(calls,0);assert.match(instance.render(),/tabindex=-1/);
 const editor=new Editor();editor.hass=hass;editor.setConfig({tap_action:{action:'url',url_path:'https://example.com'}});
 editor._valueChanged({stopPropagation(){},detail:{value:{title:'New title'}}});
 assert.equal(editor._config.tap_action.url_path,'https://example.com');
});

function controlCard(config={},light={state:'on',attributes:{brightness:128,supported_color_modes:['brightness']}}){
 const instance=card({light_entity:'light.display',show_power:true,show_brightness:true,...config});
 const calls=[];instance.hass={...hass,states:{...hass.states,'light.display':light},callService:async(...args)=>{calls.push(args);}};
 return {instance,calls};
}
test('display controls are opt-in, independently selectable and validated',()=>{
 assert.equal(card()._config.show_power,false);assert.equal(card()._config.show_brightness,false);
 assert.equal(card()._renderControls(),'');
 assert.throws(()=>card({light_entity:'sensor.live'}));assert.throws(()=>card({show_power:'true'}));
 const {instance}=controlCard({show_brightness:false});
 assert.doesNotMatch(instance._renderControls(),/<input/);assert.match(instance._renderControls(),/<button/);
 assert.match(controlCard({show_power:false}).instance._renderControls(),/<input/);
 assert.doesNotMatch(controlCard({show_power:false}).instance._renderControls(),/<button/);
});
test('power and brightness call standard HA services without optimistic state',async()=>{
 const {instance,calls}=controlCard();let actions=0;instance.addEventListener('hass-action',()=>actions++);
 await instance._togglePower();await instance._brightnessChanged({target:{value:'200'}});
 assert.equal(calls[0][0],'light');assert.equal(calls[0][1],'turn_off');assert.equal(calls[0][2].entity_id,'light.display');
 assert.equal(calls[1][1],'turn_on');assert.equal(calls[1][2].brightness,200);
 assert.equal(instance._controlState().attributes.brightness,128);assert.equal(actions,0);
 const off=controlCard({}, {state:'off',attributes:{}});await off.instance._togglePower();assert.equal(off.calls[0][1],'turn_on');
 for(const value of ['NaN','-1','0','256','1.5'])await instance._brightnessChanged({target:{value}});
 assert.equal(calls.length,2);
});
test('unavailable lights cannot send commands and errors are displayed',async()=>{
 const {instance,calls}=controlCard({}, {state:'unavailable',attributes:{}});
 await instance._togglePower();await instance._brightnessChanged({target:{value:'100'}});assert.equal(calls.length,0);
 assert.match(instance._renderControls(),/nicht verfügbar/);
 const failed=controlCard().instance;failed.hass.callService=async()=>{throw new Error('Command rejected');};
 await failed._togglePower();assert.match(failed._controlError,/Command rejected/);assert.equal(failed._controlBusy,false);
 assert.match(failed._renderControls(),/role="alert"/);
});
test('pending controls block duplicate calls and light feedback triggers rendering',async()=>{
 const {instance}=controlCard();let release,calls=0;
 instance.hass.callService=()=>{calls++;return new Promise(resolve=>release=resolve);};
 const pending=instance._togglePower();await instance._togglePower();assert.equal(calls,1);
 release();await pending;assert.equal(instance._controlBusy,false);
 const previous=instance.hass;
 instance.hass={...previous,states:{...previous.states,'light.display':{state:'off',attributes:{}}}};
 assert.equal(instance.shouldUpdate(new Map([['hass',previous]])),true);
 assert.ok(instance.getCardSize()>card().getCardSize());
});
