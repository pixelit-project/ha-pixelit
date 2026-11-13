// Exercise the shipped card/editor logic with a minimal Lit/DOM test double.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const source=readFileSync(resolve(__dirname,'../../custom_components/pixelit/www/pixelit-card.js'),'utf8');
const registry=new Map();
const html=(strings,...values)=>strings.reduce((result,part,i)=>result+part+(values[i]??''),'');
class Element extends EventTarget{getBoundingClientRect(){return {height:0};}}
const context=vm.createContext({
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
