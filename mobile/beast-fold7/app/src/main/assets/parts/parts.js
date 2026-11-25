import * as THREE from './three.module.min.js';

const canvas = document.querySelector('canvas');
const renderer = new THREE.WebGLRenderer({canvas, alpha:true, antialias:true, preserveDrawingBuffer:true});
renderer.setPixelRatio(1);
renderer.setClearColor(0, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.25;
renderer.autoClear = false;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(33, 310/270, .1, 20);
camera.position.set(2.1, 2.0, 2.9); camera.lookAt(0, .1, 0);
// Invisible faces only occlude rear edges; no surface color or triangle wireframe is drawn.
const bodyMaterial = new THREE.MeshBasicMaterial({colorWrite:false,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1});
const lidMaterial=bodyMaterial,metal=bodyMaterial,dark=bodyMaterial;
// Unity DrawBoxStrokes level 2: (.55, .95, .85) * .55, rounded to sRGB bytes.
const outlineColor=0x4d8577;
const accent = new THREE.LineBasicMaterial({color:outlineColor,toneMapped:false});

function roundPath(path, half, radius, halfY=half) {
  const h=half,r=radius,y=halfY;
  path.moveTo(-h+r,-y); path.lineTo(h-r,-y); path.quadraticCurveTo(h,-y,h,-y+r);
  path.lineTo(h,y-r); path.quadraticCurveTo(h,y,h-r,y);
  path.lineTo(-h+r,y); path.quadraticCurveTo(-h,y,-h,y-r);
  path.lineTo(-h,-y+r); path.quadraticCurveTo(-h,-y,-h+r,-y);
  return path;
}
function slab(half, height, material, hollow=false) {
  const shape=roundPath(new THREE.Shape(),half,.065);
  if(hollow)shape.holes.push(roundPath(new THREE.Path(),half-.055,.035));
  const geometry=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:true,bevelSize:.009,bevelThickness:.009,bevelSegments:2,steps:1,curveSegments:5});
  geometry.rotateX(-Math.PI/2);
  const mesh=new THREE.Mesh(geometry,material);
  return mesh;
}
function cylinder(radius,height,material) {
  return new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,height,28),material);
}
function box() {
  const group=new THREE.Group();
  group.add(slab(.62,.05,bodyMaterial),slab(.62,.49,bodyMaterial,true));
  // Floor-wall junction sits just above the base bevel; walls still occlude it.
  const floorPoints=roundPath(new THREE.Path(),.563,.035).getPoints(40)
    .map(point=>new THREE.Vector3(point.x,.062,-point.y));
  const floorEdge=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(floorPoints),accent);
  floorEdge.renderOrder=1;group.add(floorEdge);
  group.position.y=-.27; return group;
}
function lid() {
  const group=new THREE.Group();group.add(slab(.62,.1,lidMaterial));
  for(const x of [-.49,.49])for(const z of [-.49,.49]){
    const recess=cylinder(.061,.005,dark);recess.position.set(x,.114,z);group.add(recess);
    const ring=new THREE.Mesh(new THREE.TorusGeometry(.06,.008,8,28),metal);
    ring.rotation.x=-Math.PI/2;ring.position.set(x,.118,z);group.add(ring);
  }
  group.position.y=-.05;return group;
}
function screw() {
  const group=new THREE.Group();
  const shaft=cylinder(.10,.86,metal);shaft.position.y=-.12;group.add(shaft);
  const head=cylinder(.24,.15,metal);head.position.y=.39;group.add(head);
  for(const rotate of [0,Math.PI/2]){
    const slot=new THREE.Mesh(new THREE.BoxGeometry(.31,.012,.055),dark);
    slot.position.y=.472;slot.rotation.y=rotate;group.add(slot);
  }
  class ThreadCurve extends THREE.Curve {
    getPoint(t,target=new THREE.Vector3()) {
      const angle=t*Math.PI*2*8;
      return target.set(.108*Math.cos(angle),-.53+t*.78,.108*Math.sin(angle));
    }
  }
  group.add(new THREE.Mesh(new THREE.TubeGeometry(new ThreadCurve(),192,.022,6,false),metal));
  const tip=new THREE.Mesh(new THREE.ConeGeometry(.1,.14,28),metal);
  tip.rotation.z=Math.PI;tip.position.y=-.62;group.add(tip);
  group.rotation.z=-.32;group.scale.setScalar(1.35);return group;
}
const models=[box(),lid(),screw(),new THREE.Group()];
models[3].add(box());
const closedLid=lid();closedLid.position.y=.23;models[3].add(closedLid);
for(const x of [-.49,.49])for(const z of [-.49,.49]){
  const fastener=cylinder(.053,.025,metal);fastener.position.set(x,.355,z);models[3].add(fastener);
}
for(const model of models){
  const meshes=[];model.traverse(node=>{if(node.isMesh)meshes.push(node);});
  for(const mesh of meshes){
    const threshold=mesh.geometry.type==='ExtrudeGeometry'?8:mesh.geometry.type==='CylinderGeometry'?10:35;
    const edges=new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry,threshold),accent);
    edges.renderOrder=1;mesh.add(edges);
  }
}
const root=new THREE.Group();scene.add(root);
const frameScene=new THREE.Scene();
const frameCamera=new THREE.OrthographicCamera(0,1920,1080,0,.1,10);
frameCamera.position.z=1;
const frameShape=roundPath(new THREE.Shape(),130,12,116);
frameShape.holes.push(roundPath(new THREE.Path(),128,10,114));
const frameMesh=new THREE.Mesh(new THREE.ShapeGeometry(frameShape,12),
  new THREE.MeshBasicMaterial({color:outlineColor,toneMapped:false,transparent:true,opacity:.45,depthTest:false,depthWrite:false}));
frameMesh.position.set(1635,810,0);frameScene.add(frameMesh);
let current=4, animation=0, frames=0;
function draw(yaw=-.20) {
  root.rotation.y=yaw;
  renderer.setScissorTest(false);renderer.clear();
  if(current===4)return;
  const w=canvas.width,h=canvas.height;
  const ew=w/2,sw=ew*224/1920,sh=h*194/1080;
  camera.aspect=sw/sh;camera.updateProjectionMatrix();
  renderer.setScissorTest(true);
  // Identical eye-local previews stay on the display plane; no new binocular calibration.
  for(let eye=0;eye<2;eye++){
    renderer.setViewport(eye*ew,0,ew,h);renderer.setScissor(eye*ew,0,ew,h);
    renderer.render(frameScene,frameCamera);
    const x=eye*ew+ew*1523/1920,y=h-h*367/1080;
    renderer.setViewport(x,y,sw,sh);renderer.setScissor(x,y,sw,sh);
    renderer.render(scene,camera);
  }
  renderer.setScissorTest(false);frames++;
}
function resize(){renderer.setSize(Math.round(innerWidth*devicePixelRatio),Math.round(innerHeight*devicePixelRatio),false);draw();}
window.setPart=(part)=>{
  if(!Number.isInteger(part)||part<0||part>4)throw new Error('invalid_part');
  if(part===current)return;
  cancelAnimationFrame(animation);current=part;root.clear();
  if(part!==4)root.add(models[part]);
  const start=performance.now();let previous=-100;
  function animate(now){
    const t=Math.min(1,(now-start)/550);
    if(now-previous>=40||t===1){draw(-.20-.16*(1-t)**3);previous=now;}
    if(t<1)animation=requestAnimationFrame(animate);
    else console.info('PARTS_DRAWN '+JSON.stringify({part:current,frames,width:canvas.width,height:canvas.height}));
  }
  if(part===4)draw();else animation=requestAnimationFrame(animate);
};
window.partStats=()=>{
  const gl=renderer.getContext(),pixels=new Uint8Array(canvas.width*canvas.height*4);
  gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
  const counts=[0,0],modelCounts=[0,0],frameCounts=[0,0];let outside=0,nonMint=0,maxGreen=0;
  for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++){
    const i=(y*canvas.width+x)*4;
    if(pixels[i+3]<20)continue;
    maxGreen=Math.max(maxGreen,pixels[i+1]);
    if(pixels[i+1]<=pixels[i]*1.4||pixels[i+1]<=pixels[i+2]*1.04)nonMint++;
    const eye=x<canvas.width/2?0:1;counts[eye]++;
    const local=x-eye*canvas.width/2,eyew=canvas.width/2;
    if(local>=Math.floor(eyew*1523/1920)&&local<=Math.ceil(eyew*1747/1920)
      &&y>=Math.floor(canvas.height*713/1080)&&y<=Math.ceil(canvas.height*907/1080))modelCounts[eye]++;
    else frameCounts[eye]++;
    if(local<Math.floor(eyew*1505/1920)||local>Math.ceil(eyew*1765/1920)||y<Math.floor(canvas.height*694/1080)||y>Math.ceil(canvas.height*926/1080))outside++;
  }
  return {part:current,counts,modelCounts,frameCounts,outside,nonMint,maxGreen,frames,width:canvas.width,height:canvas.height,triangles:renderer.info.render.triangles};
};
window.addEventListener('resize',resize);
canvas.addEventListener('webglcontextlost',()=>console.error('PARTS_CONTEXT_LOST'));
resize();console.info('PARTS_READY');
