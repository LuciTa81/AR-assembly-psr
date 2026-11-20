const {test}=require('node:test');
const assert=require('node:assert/strict');
const {parseAppearance,resolveAppearance,routeFromHash}=require('../../web_overlay/supervisor_shell.js');
test('appearance validates storage and defaults to dark',()=>{
  const defaults={theme:'dark',motion:true,highlight:true};
  assert.deepEqual(parseAppearance(null),defaults);
  assert.deepEqual(parseAppearance('bad json'),defaults);
  assert.deepEqual(parseAppearance('{"theme":"purple","motion":"false"}'),defaults);
  assert.deepEqual(parseAppearance('{"theme":"light","motion":false,"highlight":false}'),{theme:'light',motion:false,highlight:false});
  assert.deepEqual(parseAppearance('null'),defaults);
  assert.equal(resolveAppearance(parseAppearance(null),false,false).theme,'dark');
  assert.equal(parseAppearance('{"theme":"system"}').theme,'system');
});
test('explicit theme wins; reduced-motion overrides animated highlights',()=>{
  assert.deepEqual(resolveAppearance({theme:'system',motion:true,highlight:true},true,false),{theme:'dark',motion:true,highlight:true});
  assert.deepEqual(resolveAppearance({theme:'light',motion:true,highlight:true},true,true),{theme:'light',motion:false,highlight:false});
  assert.equal(resolveAppearance({theme:'dark',motion:false,highlight:true},false,false).highlight,false);
});
test('only implemented hash routes are accepted',()=>{
  for(const route of ['live','history','tracking','settings']) assert.equal(routeFromHash('#'+route),route);
  for(const hash of ['','#actionSurface','#unknown','#<script>']) assert.equal(routeFromHash(hash),'live');
});
